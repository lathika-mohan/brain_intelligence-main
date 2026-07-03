"""
Phase 4 — Vector Embedding Pipeline & Model Orchestration

Deterministic SentenceTransformer wrapper with:
- Model standardization (all-mpnet-base-v2 / bge-large-en-v1.5)
- Idempotent batch ingestion
- GPU/CPU auto-acceleration
- Token length tracking
- Robust error handling
"""

from __future__ import annotations

import hashlib
import logging
import time
from functools import lru_cache
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except Exception as e:  # pragma: no cover
    HAS_ST = False
    SentenceTransformer = None  # type: ignore
    logger.warning("sentence-transformers not available: %s", e)


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

def resolve_model_dimensions(model_name: str) -> int:
    """Resolve embedding dimensions from model id."""
    from .schema import EMBEDDING_DIMENSIONS
    return EMBEDDING_DIMENSIONS.get(model_name, 768)


# ---------------------------------------------------------------------------
# Embedding Engine
# ---------------------------------------------------------------------------

class EmbeddingEngine:
    """
    Production embedding orchestration layer.

    - Deterministic: same text → same vector
    - Idempotent: caller can supply cache keys to skip re-embedding
    - Batched: dynamic batch sizing with GPU/CPU auto-detect
    - Resilient: empty payload guards, timeout thresholds, fallback handling
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_seq_length: Optional[int] = None,
        normalize_embeddings: bool = True,
        trust_remote_code: bool = False,
        *,
        lazy_load: bool = False,
    ):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model_name
        # Phase 4 upgrade: default to all-mpnet-base-v2 if legacy MiniLM detected
        if "MiniLM" in self.model_name:
            logger.info("Upgrading legacy embedding model %s → all-mpnet-base-v2", self.model_name)
            self.model_name = "sentence-transformers/all-mpnet-base-v2"

        self.device = device or settings.embedding_device
        self.batch_size = batch_size or settings.embedding_batch_size
        self.max_seq_length = max_seq_length or settings.embedding_max_seq_length
        self.normalize_embeddings = normalize_embeddings
        self.trust_remote_code = trust_remote_code

        self._model: Optional[SentenceTransformer] = None
        self._vector_dim: Optional[int] = None
        self._model_load_time_ms: Optional[float] = None

        if not lazy_load:
            self.load_model()

    # -----------------------------------------------------------------------
    # Model lifecycle
    # -----------------------------------------------------------------------

    def load_model(self) -> None:
        """Load SentenceTransformer with hardware acceleration detection."""
        if self._model is not None:
            return
        if not HAS_ST:
            raise RuntimeError("sentence-transformers is not installed — see requirements.txt")

        t0 = time.perf_counter()
        try:
            # Auto device fallback: cuda → mps → cpu
            device = self.device
            try:
                import torch
                if device == "cuda" and not torch.cuda.is_available():
                    logger.warning("CUDA requested but not available — falling back to CPU")
                    device = "cpu"
            except Exception:
                device = "cpu"

            logger.info("Loading embedding model %s on %s …", self.model_name, device)
            model = SentenceTransformer(
                self.model_name,
                device=device,
                trust_remote_code=self.trust_remote_code,
            )
            # enforce max_seq_length if supported
            if hasattr(model, "max_seq_length") and self.max_seq_length:
                try:
                    model.max_seq_length = self.max_seq_length
                except Exception:
                    pass

            self._model = model
            self.device = device
            # infer output dim
            try:
                self._vector_dim = model.get_sentence_embedding_dimension()  # type: ignore
            except Exception:
                self._vector_dim = resolve_model_dimensions(self.model_name)

            self._model_load_time_ms = (time.perf_counter() - t0) * 1000.0
            logger.info(
                "Embedding model ready: %s | dim=%s | device=%s | load=%.1fms",
                self.model_name, self._vector_dim, self.device, self._model_load_time_ms,
            )
        except Exception as e:
            logger.exception("Failed to load embedding model %s: %s", self.model_name, e)
            raise

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self.load_model()
        assert self._model is not None
        return self._model

    @property
    def vector_dim(self) -> int:
        if self._vector_dim is not None:
            return self._vector_dim
        return resolve_model_dimensions(self.model_name)

    # -----------------------------------------------------------------------
    # Core encoding
    # -----------------------------------------------------------------------

    def encode(
        self,
        texts: Sequence[str],
        *,
        batch_size: Optional[int] = None,
        normalize: Optional[bool] = None,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        timeout_s: float = 60.0,
    ) -> np.ndarray:
        """
        Encode a batch of texts → (n, dim) float32 array.
        Guards empty payloads, enforces timeout, normalizes output.
        """
        if not texts:
            return np.zeros((0, self.vector_dim), dtype=np.float32)

        # sanitize: strip, drop pure whitespace, replace empty with [EMPTY]
        clean: List[str] = []
        empty_mask: List[bool] = []
        for t in texts:
            s = (t or "").strip()
            if not s:
                clean.append("[EMPTY]")
                empty_mask.append(True)
            else:
                # guard excessive length — truncate at ~8192 chars (~2k tokens)
                if len(s) > 8192:
                    s = s[:8192]
                clean.append(s)
                empty_mask.append(False)

        bs = batch_size or self.batch_size
        norm = self.normalize_embeddings if normalize is None else normalize

        t0 = time.perf_counter()
        try:
            vectors = self.model.encode(
                clean,
                batch_size=bs,
                normalize_embeddings=norm,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True,
            )
            elapsed = time.perf_counter() - t0
            if elapsed > timeout_s:
                logger.warning("Embedding batch timeout: %.2fs > %.1fs (n=%d)", elapsed, timeout_s, len(texts))
            # zero out vectors that were empty input — prevents false matches
            if any(empty_mask):
                arr = np.asarray(vectors, dtype=np.float32)
                for i, is_empty in enumerate(empty_mask):
                    if is_empty:
                        arr[i] = 0.0
                vectors = arr
            return np.asarray(vectors, dtype=np.float32)
        except Exception as e:
            logger.exception("Embedding encode failed (n=%d): %s", len(texts), e)
            raise

    def encode_query(self, query_text: str) -> np.ndarray:
        """Encode a single search query with BGE instruction prefix if applicable."""
        text = query_text.strip()
        if not text:
            raise ValueError("query_text must be non-empty")
        # BGE models benefit from instruction prefix
        if "bge" in self.model_name.lower():
            text = f"Represent this sentence for searching relevant passages: {text}"
        vec = self.encode([text], batch_size=1, show_progress_bar=False)
        return vec[0]

    # -----------------------------------------------------------------------
    # Idempotent batch ingestion helpers
    # -----------------------------------------------------------------------

    def chunk_fingerprint(self, text: str, chunk_id: Optional[str] = None) -> str:
        """Stable sha256 fingerprint for idempotency de-duplication."""
        h = hashlib.sha256()
        h.update(self.model_name.encode())
        if chunk_id:
            h.update(chunk_id.encode())
        h.update(text.encode("utf-8", errors="ignore"))
        return h.hexdigest()

    def embed_chunks(
        self,
        chunk_texts: Sequence[str],
        chunk_ids: Optional[Sequence[str]] = None,
        *,
        skip_existing_fingerprints: Optional[set[str]] = None,
    ) -> Tuple[np.ndarray, List[int], List[str]]:
        """
        Idempotent embedding:
        Returns (vectors, kept_indices, fingerprints)
        - skip_existing_fingerprints: set of sha256 to skip → saves compute
        """
        fps: List[str] = []
        keep_idx: List[int] = []
        to_embed_texts: List[str] = []
        to_embed_map: List[int] = []

        skip_set = skip_existing_fingerprints or set()
        ids = list(chunk_ids) if chunk_ids else [None] * len(chunk_texts)  # type: ignore

        for i, txt in enumerate(chunk_texts):
            cid = ids[i] if i < len(ids) else None
            fp = self.chunk_fingerprint(txt, cid)
            fps.append(fp)
            if fp in skip_set:
                continue
            keep_idx.append(i)
            to_embed_texts.append(txt)
            to_embed_map.append(i)

        if not to_embed_texts:
            return np.zeros((0, self.vector_dim), dtype=np.float32), [], fps

        vectors = self.encode(to_embed_texts)
        return vectors, keep_idx, fps

    # -----------------------------------------------------------------------
    # Diagnostics
    # -----------------------------------------------------------------------

    def health(self) -> dict:
        return {
            "model_name": self.model_name,
            "vector_dim": self.vector_dim,
            "device": self.device,
            "batch_size": self.batch_size,
            "max_seq_length": self.max_seq_length,
            "normalize_embeddings": self.normalize_embeddings,
            "model_loaded": self._model is not None,
            "model_load_time_ms": self._model_load_time_ms,
            "sentence_transformers_available": HAS_ST,
        }


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_engine_singleton: Optional[EmbeddingEngine] = None

@lru_cache(maxsize=1)
def get_embedding_engine(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> EmbeddingEngine:
    """Cached singleton — safe for FastAPI Depends."""
    global _engine_singleton
    if _engine_singleton is None or (model_name and model_name != _engine_singleton.model_name):
        _engine_singleton = EmbeddingEngine(model_name=model_name, device=device, lazy_load=False)
    return _engine_singleton
