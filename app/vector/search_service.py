"""
Phase 4 — High-Performance Retrieval Service
Production-ready async semantic search with strict metadata filtering
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings
from .client import get_qdrant_client
from .embedding_engine import EmbeddingEngine, get_embedding_engine
from .models import SearchFilters, VectorSearchResult, VectorSearchResponse
from .schema import DEFAULT_COLLECTION, DEFAULT_SCORE_THRESHOLD, DEFAULT_TOP_K, MAX_TOP_K

logger = logging.getLogger(__name__)


class VectorSearchService:
    """
    Encapsulates advanced vector search operations for GraphRAG consumption.

    - On-the-fly query encoding
    - Native Qdrant Filter / Must / Match
    - Score thresholding & normalization
    - Async interface
    """

    def __init__(
        self,
        *,
        client: Optional[QdrantClient] = None,
        embedding_engine: Optional[EmbeddingEngine] = None,
        collection_name: Optional[str] = None,
        default_top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ):
        self.client = client or get_qdrant_client()
        self.embedding = embedding_engine or get_embedding_engine()
        self.collection_name = collection_name or str(
            getattr(DEFAULT_COLLECTION, "value", DEFAULT_COLLECTION)
        )
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold
        settings = get_settings()
        # allow settings override
        self.score_threshold = getattr(settings, "vector_score_threshold", self.score_threshold)

    # -------------------------------------------------------------------
    # Filter builder — Qdrant native syntax
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_list_filter(val: Union[str, List[str], None]) -> Optional[List[str]]:
        if val is None:
            return None
        if isinstance(val, str):
            return [val]
        return list(val)

    def build_qdrant_filter(self, filters: Optional[SearchFilters]) -> Optional[qm.Filter]:
        """Translate SearchFilters → qm.Filter(must=[...])"""
        if not filters or filters.is_empty():
            return None

        must_conditions: List[qm.FieldCondition] = []

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
            # text match — qdrant text index
            must_conditions.append(
                qm.FieldCondition(key="section_title", match=qm.MatchText(text=filters.section_title))
            )

        # numeric ranges
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

    # -------------------------------------------------------------------
    # Core search
    # -------------------------------------------------------------------

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
        """
        Async semantic search:
        - encodes query_text on-the-fly
        - runs nearest-neighbor vector scan
        - applies strict metadata filtering
        - rejects matches below score_threshold
        """
        t0 = time.perf_counter()
        if not query_text or not query_text.strip():
            raise ValueError("query_text must be non-empty")

        k = min(top_k or self.default_top_k, MAX_TOP_K)
        threshold = score_threshold if score_threshold is not None else self.score_threshold
        coll = collection or self.collection_name

        # normalize filters
        filt_obj: Optional[SearchFilters] = None
        if isinstance(filters, dict):
            filt_obj = SearchFilters(**filters)
        else:
            filt_obj = filters

        qdrant_filter = self.build_qdrant_filter(filt_obj)

        # Encode query — run in threadpool to avoid blocking event loop
        loop = asyncio.get_running_loop()
        try:
            query_vector = await loop.run_in_executor(
                None, self.embedding.encode_query, query_text
            )
        except Exception as e:
            logger.exception("Query encoding failed: %s", e)
            raise

        # Qdrant search — qdrant_client is sync → run in executor
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
                    hnsw_ef=128,  # accuracy vs latency tunable
                ),
            )

        try:
            scored_points = await loop.run_in_executor(None, _do_search)
        except Exception as e:
            logger.exception("Qdrant search failed on %s: %s", coll, e)
            raise

        # Map to Pydantic
        results: List[VectorSearchResult] = []
        for pt in scored_points:
            payload = pt.payload or {}
            # cosine threshold already applied by Qdrant, double-check
            if pt.score < threshold:
                continue
            results.append(
                VectorSearchResult(
                    id=pt.id,
                    score=float(pt.score),
                    chunk_id=payload.get("chunk_id", str(pt.id)),
                    document_id=payload.get("document_id", "unknown"),
                    document_type=payload.get("document_type", "MANUAL"),
                    asset_type=payload.get("asset_type"),
                    section_title=payload.get("section_title"),
                    text=payload.get("text", ""),
                    token_count=payload.get("token_count"),
                    chunk_index=payload.get("chunk_index"),
                    source_filename=payload.get("source_filename"),
                    payload=payload,
                )
            )

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return VectorSearchResponse(
            query=query_text,
            top_k=k,
            returned=len(results),
            score_threshold=threshold,
            latency_ms=latency_ms,
            results=results,
            filters_applied=filt_obj,
            collection=coll,
            embedding_model=self.embedding.model_name,
            total_candidates_scanned=None,
        )

    # -------------------------------------------------------------------
    # Batch / multi-query
    # -------------------------------------------------------------------

    async def multi_search(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
        filters: Optional[SearchFilters] = None,
    ) -> List[VectorSearchResponse]:
        """Parallelize N queries — preserves order."""
        tasks = [
            self.semantic_search(q, top_k=top_k, filters=filters)
            for q in queries
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)

    # -------------------------------------------------------------------
    # Convenience: GraphRAG-compatible wrapper
    # -------------------------------------------------------------------

    async def graphrag_retrieve(
        self,
        query_text: str,
        *,
        top_k: int = 8,
        asset_id: Optional[str] = None,
        document_type: Optional[str] = None,
        min_score: float = 0.70,
    ) -> Dict[str, Any]:
        """Return structure compatible with app/models/graphrag.GraphRagQueryResponse"""
        filt = SearchFilters()
        if document_type:
            filt.document_type = document_type
        # asset_id is not a direct payload field — would need join via Neo4j in full GraphRAG
        resp = await self.semantic_search(
            query_text, top_k=top_k, filters=filt, score_threshold=min_score
        )
        # Map to GraphRAG context chunks
        context_chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "score": r.score,
                "document_type": r.document_type,
                "source": r.source_filename or r.document_id,
            }
            for r in resp.results
        ]
        return {
            "answer": None,  # LLM synthesis is Phase 5
            "context_chunks": context_chunks,
            "graph_nodes_expanded": 0,
            "vector_hits": resp.returned,
            "latency_ms": resp.latency_ms,
            "query_embedding_model": resp.embedding_model,
        }


# ---------------------------------------------------------------------------
# Singleton accessor for DI
# ---------------------------------------------------------------------------

_search_singleton: Optional[VectorSearchService] = None

def get_search_service(
    collection_name: Optional[str] = None,
) -> VectorSearchService:
    global _search_singleton
    if _search_singleton is None or (collection_name and collection_name != _search_singleton.collection_name):
        _search_singleton = VectorSearchService(collection_name=collection_name)
    return _search_singleton
