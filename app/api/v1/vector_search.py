"""
Phase 4 — Vector Search API
FastAPI router exposing semantic_search endpoint
Preserves existing GraphRAG contracts — no UI changes
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.common import APIResponse
from app.vector.models import (
    SearchFilters,
    VectorSearchResponse,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
)
from app.vector.search_service import get_search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vector", tags=["vector-search"])


@router.post("/search", response_model=APIResponse[VectorSearchResponse])
async def semantic_search_endpoint(
    body: GraphRagQueryRequest,
):
    """
    POST /api/v1/vector/search
    Body: { query_text, top_k, filters?, min_score }
    """
    try:
        svc = get_search_service()
        resp = await svc.semantic_search(
            query_text=body.query_text,
            top_k=body.top_k,
            filters=body.filters,
            score_threshold=body.min_score,
        )
        return APIResponse(data=resp)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("vector search failed")
        raise HTTPException(status_code=500, detail=f"search failed: {e}")


@router.get("/search", response_model=APIResponse[VectorSearchResponse])
async def semantic_search_get(
    q: str = Query(..., min_length=1, description="query text"),
    top_k: int = Query(8, ge=1, le=50),
    document_type: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    min_score: float = Query(0.70, ge=0.0, le=1.0),
):
    filt = None
    if document_type or asset_type:
        filt = SearchFilters(document_type=document_type, asset_type=asset_type)
    svc = get_search_service()
    resp = await svc.semantic_search(q, top_k=top_k, filters=filt, score_threshold=min_score)
    return APIResponse(data=resp)


@router.get("/health")
async def vector_health():
    from app.vector.client import check_qdrant_health
    from app.vector.embedding_engine import get_embedding_engine
    try:
        eng = get_embedding_engine()
        qh = check_qdrant_health()
        return {
            "embedding_model": eng.model_name,
            "vector_dim": eng.vector_dim,
            "device": eng.device,
            "qdrant": qh,
            "status": "ok" if qh.get("status") == "ok" else "degraded",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
