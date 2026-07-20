"""
Phase 4 — High-Performance Retrieval Service — hardened, optional qdrant.
Production-ready async semantic search with strict metadata filtering
and degraded stub when qdrant-client or embedding model missing.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from app.core.config import get_settings
from .client import get_qdrant_client, HAS_QDRANT
from .models import SearchFilters, VectorSearchResult, VectorSearchResponse
from .schema import DEFAULT_COLLECTION, DEFAULT_SCORE_THRESHOLD, DEFAULT_TOP_K, MAX_TOP_K

logger = logging.getLogger(__name__)

try:
    from qdrant_client.http import models as qm
    HAS_QDRANT_MODELS = True
except Exception:
    qm = Any  # type: ignore
    HAS_QDRANT_MODELS = False

try:
    from qdrant_client import QdrantClient
except Exception:
    QdrantClient = Any  # type: ignore

class VectorSearchService:
    def __init__(
        self,
        *,
        client: Optional[Any] = None,
        embedding_engine: Optional[Any] = None,
        collection_name: Optional[str] = None,
        default_top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ):
        self.client = client or get_qdrant_client()
        # embedding_engine lazy — may be stub
        try:
            from .embedding_engine import get_embedding_engine
            self.embedding = embedding_engine or get_embedding_engine()
        except Exception as e:
            logger.warning("Embedding engine fallback stub: %s", e)
            self.embedding = None

        self.collection_name = collection_name or str(
            getattr(DEFAULT_COLLECTION, "value", DEFAULT_COLLECTION)
        )
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold
        settings = get_settings()
        self.score_threshold = getattr(settings, "vector_score_threshold", self.score_threshold)

    @staticmethod
    def _normalize_list_filter(val: Union[str, List[str], None]) -> Optional[List[str]]:
        if val is None:
            return None
        if isinstance(val, str):
            return [val]
        return list(val)

    def build_qdrant_filter(self, filters: Optional[SearchFilters]) -> Optional[Any]:
        if not filters or filters.is_empty():
            return None
        if not HAS_QDRANT_MODELS:
            return None
        must_conditions: List[Any] = []

        def add_match(field: str, values: Union[str, List[str], None]):
            vals = self._normalize_list_filter(values)
            if not vals:
                return
            if len(vals) == 1:
                must_conditions.append(
                    qm.FieldCondition(key=field, match=qm.MatchValue(value=vals[0]))
                )
            else:
                must_conditions.append(
                    qm.FieldCondition(key=field, match=qm.MatchAny(any=vals))
                )

        add_match("document_type", filters.document_type)
        add_match("asset_type", filters.asset_type)
        add_match("document_id", filters.document_id)
        add_match("source_filename", filters.source_filename)
        if filters.chunk_ids:
            must_conditions.append(
                qm.FieldCondition(key="chunk_id", match=qm.MatchAny(any=filters.chunk_ids))
            )
        if filters.section_title:
            must_conditions.append(
                qm.FieldCondition(key="section_title", match=qm.MatchText(text=filters.section_title))
            )
        if filters.min_token_count is not None or filters.max_token_count is not None:
            rng = {}
            if filters.min_token_count is not None:
                rng["gte"] = filters.min_token_count
            if filters.max_token_count is not None:
                rng["lte"] = filters.max_token_count
            must_conditions.append(
                qm.FieldCondition(key="token_count", range=qm.Range(**rng))
            )
        if not must_conditions:
            return None
        return qm.Filter(must=must_conditions)

    async def semantic_search(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[SearchFilters | Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
        with_payload: bool = True,
        with_vectors: bool = False,
        *,
        collection: Optional[str] = None,
        exact: bool = False,
    ) -> VectorSearchResponse:
        t0 = time.perf_counter()
        if not query_text or not query_text.strip():
            raise ValueError("query_text must be non-empty")

        k = min(top_k or self.default_top_k, MAX_TOP_K)
        threshold = score_threshold if score_threshold is not None else self.score_threshold
        coll = collection or self.collection_name

        filt_obj: Optional[SearchFilters] = None
        if isinstance(filters, dict):
            filt_obj = SearchFilters(**filters)
        else:
            filt_obj = filters

        # Degraded stub path when no real qdrant or embedding
        if not HAS_QDRANT or self.embedding is None:
            logger.info("Vector search degraded stub for query: %s", query_text[:80])
            return VectorSearchResponse(
                query_text=query_text,
                results=[],
                total_found=0,
                score_threshold=threshold,
                collection=coll,
                latency_ms=(time.perf_counter()-t0)*1000.0,
            )

        qdrant_filter = self.build_qdrant_filter(filt_obj)

        loop = asyncio.get_running_loop()
        try:
            query_vector = await loop.run_in_executor(
                None, self.embedding.encode_query, query_text
            )
        except Exception as e:
            logger.exception("Query encoding failed: %s", e)
            raise

        def _do_search():
            return self.client.search(
                collection_name=coll,
                query_vector=query_vector.tolist(),
                query_filter=qdrant_filter,
                limit=k,
                score_threshold=threshold if threshold > 0 else None,
                with_payload=with_payload,
                with_vectors=with_vectors,
                search_params=qm.SearchParams(
                    exact=exact,
                    hnsw_ef=128,
                ),
            )

        try:
            scored_points = await loop.run_in_executor(None, _do_search)
        except Exception as e:
            logger.exception("Qdrant search failed on %s: %s", coll, e)
            raise

        results: List[VectorSearchResult] = []
        for pt in scored_points:
            payload = pt.payload or {}
            if pt.score < threshold:
                continue
            results.append(
                VectorSearchResult(
                    id=pt.id,
                    score=float(pt.score),
                    chunk_id=payload.get("chunk_id", str(pt.id)),
                    document_id=payload.get("document_id", "unknown"),
                    document_type=payload.get("document_type", "SOP"),
                    asset_type=payload.get("asset_type"),
                    section_title=payload.get("section_title"),
                    text=payload.get("text", "")[:2000],
                    source_filename=payload.get("source_filename"),
                    page_number=payload.get("page_number"),
                    token_count=payload.get("token_count", 0),
                )
            )

        return VectorSearchResponse(
            query_text=query_text,
            results=results,
            total_found=len(results),
            score_threshold=threshold,
            collection=coll,
            latency_ms=(time.perf_counter()-t0)*1000.0,
        )

_search_service: Optional[VectorSearchService] = None

def get_search_service() -> VectorSearchService:
    global _search_service
    if _search_service is None:
        _search_service = VectorSearchService()
    return _search_service
