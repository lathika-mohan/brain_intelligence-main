"""
Phase 4 — Embedding Ingestion Pipeline
Idempotent vector ingestion: Chunk → Embedding → Qdrant
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client.http import models as qm

from .embedding_engine import EmbeddingEngine, get_embedding_engine
from .qdrant_manager import QdrantCollectionManager
from .models import ChunkPayload, EmbeddingBatchResult
from .client import get_qdrant_client
from .schema import DEFAULT_COLLECTION

logger = logging.getLogger(__name__)


def _stable_point_id(chunk_id: str) -> str:
    """
    Qdrant accepts UUID or int.
    Convert chunk_id (e.g. 'chunk:abc123…') to deterministic UUID5.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class VectorIngestionPipeline:
    """
    Batch-processing execution script core.
    - Pulls text chunks (from Neo4j repo or direct list)
    - Generates dense embeddings
    - Pairs with primary keys
    - Tracks token lengths
    - Avoids redundant execution
    """

    def __init__(
        self,
        *,
        embedding_engine: Optional[EmbeddingEngine] = None,
        collection_name: Optional[str] = None,
        batch_size: int = 64,
    ):
        self.embedding = embedding_engine or get_embedding_engine()
        self.client = get_qdrant_client()
        self.collection_name = collection_name or str(
            getattr(DEFAULT_COLLECTION, "value", DEFAULT_COLLECTION)
        )
        self.batch_size = batch_size
        self.collection_mgr = QdrantCollectionManager(
            client=self.client,
            collection_name=self.collection_name,
            vector_size=self.embedding.vector_dim,
        )
        # ensure collection exists
        try:
            self.collection_mgr.ensure_collection(recreate=False)
        except Exception as e:
            logger.warning("Collection ensure failed (may already exist): %s", e)

    # -------------------------------------------------------------------
    # Idempotency — check existing points
    # -------------------------------------------------------------------

    def existing_point_ids(self, chunk_ids: Sequence[str]) -> set[str]:
        """Return set of chunk_ids already present in Qdrant."""
        if not chunk_ids:
            return set()
        # Qdrant scroll with filter MatchAny
        try:
            # build filter
            filt = qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="chunk_id",
                        match=qm.MatchAny(any=list(chunk_ids))
                    )
                ]
            )
            # scroll — payload only chunk_id
            found = set()
            next_offset = None
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filt,
                    limit=256,
                    offset=next_offset,
                    with_payload=["chunk_id"],
                    with_vectors=False,
                )
                for p in points:
                    cid = (p.payload or {}).get("chunk_id")
                    if cid:
                        found.add(cid)
                if next_offset is None:
                    break
            return found
        except Exception as e:
            logger.debug("existing_point_ids lookup failed: %s", e)
            return set()

    # -------------------------------------------------------------------
    # Core upsert
    # -------------------------------------------------------------------

    async def ingest_chunks(
        self,
        chunks: List[Dict[str, Any]],
        *,
        skip_existing: bool = True,
        upsert_batch_size: int = 64,
    ) -> EmbeddingBatchResult:
        """
        chunks: list of dicts with keys:
          chunk_id, document_id, document_type, text, ...
        Returns EmbeddingBatchResult
        """
        t0 = time.perf_counter()
        total_requested = len(chunks)
        if total_requested == 0:
            return EmbeddingBatchResult(
                total_requested=0, embedded=0, skipped_existing=0,
                upserted=0, failed=0, latency_ms=0.0,
                collection=self.collection_name,
                vector_dim=self.embedding.vector_dim,
            )

        # idempotency
        chunk_ids = [c.get("chunk_id") for c in chunks if c.get("chunk_id")]
        existing = self.existing_point_ids(chunk_ids) if skip_existing else set()
        to_process = [c for c in chunks if c.get("chunk_id") not in existing]
        skipped = total_requested - len(to_process)

        embedded = 0
        upserted = 0
        failed = 0
        errors: List[str] = []

        # process in batches
        for i in range(0, len(to_process), self.batch_size):
            batch = to_process[i:i + self.batch_size]
            texts = [b.get("text", "") for b in batch]
            # guard empty
            valid_idx = [idx for idx, t in enumerate(texts) if t and t.strip()]
            if not valid_idx:
                continue
            valid_texts = [texts[j] for j in valid_idx]
            valid_chunks = [batch[j] for j in valid_idx]

            try:
                vectors = self.embedding.encode(valid_texts, batch_size=self.batch_size)
                embedded += len(valid_texts)

                # build points
                points: List[qm.PointStruct] = []
                for ch, vec in zip(valid_chunks, vectors):
                    try:
                        payload_dict = {
                            "chunk_id": ch.get("chunk_id"),
                            "document_id": ch.get("document_id", "unknown"),
                            "document_type": ch.get("document_type") or ch.get("source_type") or "MANUAL",
                            "asset_type": ch.get("asset_type"),
                            "section_title": ch.get("section_title"),
                            "source_filename": ch.get("source_filename") or ch.get("source_document"),
                            "chunk_index": ch.get("chunk_index", 0),
                            "token_count": ch.get("token_count"),
                            "char_count": ch.get("char_count") or len(ch.get("text", "")),
                            "page_start": ch.get("page_start"),
                            "page_end": ch.get("page_end"),
                            "text": ch.get("text", ""),
                            "hash": ch.get("hash"),
                            "embedding_model": self.embedding.model_name,
                            "embedding_timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                        }
                        # validate via Pydantic (will strip None gracefully)
                        cp = ChunkPayload(**{k: v for k, v in payload_dict.items() if v is not None or k in ("chunk_id","document_id","document_type","text")})
                        point_id = _stable_point_id(cp.chunk_id)
                        points.append(
                            qm.PointStruct(
                                id=point_id,
                                vector=vec.tolist(),
                                payload=cp.model_dump(mode="json"),
                            )
                        )
                    except Exception as pe:
                        failed += 1
                        errors.append(f"payload build {ch.get('chunk_id')}: {pe}")

                # upsert in sub-batches
                for u in range(0, len(points), upsert_batch_size):
                    sub = points[u:u+upsert_batch_size]
                    if not sub:
                        continue
                    try:
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=sub,
                            wait=True,
                        )
                        upserted += len(sub)
                    except Exception as ue:
                        failed += len(sub)
                        errors.append(str(ue)[:500])

            except Exception as e:
                failed += len(valid_texts)
                errors.append(str(e)[:500])
                logger.exception("Batch embedding failed: %s", e)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return EmbeddingBatchResult(
            total_requested=total_requested,
            embedded=embedded,
            skipped_existing=skipped,
            upserted=upserted,
            failed=failed,
            latency_ms=latency_ms,
            collection=self.collection_name,
            vector_dim=self.embedding.vector_dim,
            errors=errors[:10],
        )

    # -------------------------------------------------------------------
    # High-level: ingest from Neo4j repository
    # -------------------------------------------------------------------

    async def ingest_from_graph(
        self,
        graph_repository=None,
        *,
        limit: int = 2000,
        document_type: Optional[str] = None,
    ) -> EmbeddingBatchResult:
        from .repository import ChunkVectorRepository
        repo = ChunkVectorRepository(graph_repository)
        chunks = await repo.fetch_chunks(limit=limit, document_type=document_type)
        return await self.ingest_chunks(chunks, skip_existing=True)
