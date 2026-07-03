"""
Phase 5 — GraphRAG API Router
===============================
Exposes the Phase 0 contract endpoint ``POST /api/v1/graphrag/query``
that powers ``src/components/GraphRagPanel.tsx``.

The router:
  • Accepts ``GraphRagQueryRequest`` (Phase 0 frozen contract)
  • Calls ``GraphRagService.query()`` for the full pipeline
  • Wraps the response in ``APIResponse[GraphRagQueryResponse]``
  • Also exposes health and diagnostics endpoints

No modification to the frontend is required — the response payload
conforms exactly to the contract the UI already expects.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.models.common import APIResponse
from app.models.graphrag import (
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagQueryEnvelope,
)
from app.graphrag.graph_rag_service import get_graphrag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphrag", tags=["graphrag"])


# ---------------------------------------------------------------------------
# POST /api/v1/graphrag/query — Main GraphRAG endpoint
# ---------------------------------------------------------------------------

@router.post("/query", response_model=APIResponse[GraphRagQueryResponse])
async def graphrag_query(body: GraphRagQueryRequest) -> APIResponse[GraphRagQueryResponse]:
    """
    Execute a hybrid GraphRAG query.

    Accepts a natural-language query, runs parallel retrieval from Qdrant
    (vector) and Neo4j (graph), fuses the context via RRF, builds a
    grounded LLM prompt, and returns the synthesised answer with full
    citation provenance and graph visualisation data.

    The response payload conforms to the Phase 0 contract and is consumed
    by ``GraphRagPanel.tsx`` on the frontend.
    """
    request_id = str(uuid.uuid4())

    try:
        service = get_graphrag_service()
        response_data = await service.query(body)

        return APIResponse(
            success=True,
            data=response_data,
            error=None,
            request_id=request_id,
        )
    except ValueError as ve:
        logger.warning("GraphRAG query validation error: %s", ve)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("GraphRAG query failed")
        # Return a degraded response rather than a 500
        fallback = GraphRagQueryResponse(
            answer=f"GraphRAG query failed: {e}. The system is experiencing degraded performance.",
            latency_ms=0.0,
        )
        return APIResponse(
            success=False,
            data=fallback,
            error=str(e),
            request_id=request_id,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/graphrag/health — Health check
# ---------------------------------------------------------------------------

@router.get("/health")
async def graphrag_health() -> Dict[str, Any]:
    """
    Health status of the GraphRAG pipeline and its dependencies.
    """
    try:
        service = get_graphrag_service()
        health = await service.health()
        return health
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "components": {},
        }


# ---------------------------------------------------------------------------
# POST /api/v1/graphrag/diagnose — Diagnostic endpoint
# ---------------------------------------------------------------------------

@router.post("/diagnose")
async def graphrag_diagnose(body: GraphRagQueryRequest) -> Dict[str, Any]:
    """
    Run the retrieval pipeline WITHOUT LLM synthesis.

    Returns raw retrieval metrics, fusion results, and provenance data
    for benchmarking and debugging.
    """
    try:
        service = get_graphrag_service()

        # Step 1: Retrieval only
        retrieval = await service.retriever.retrieve(
            query_text=body.query_text,
            top_k=body.top_k,
            min_score=body.min_score,
            max_graph_hops=body.max_graph_hops,
            asset_id=body.asset_id,
            filters=body.filters,
        )

        # Step 2: Fusion
        fusion_result = service.fusion.fuse(
            vector_hits=retrieval["vector_hits"],
            graph_hits=retrieval["graph_hits"],
            method="rrf",
            max_candidates=20,
        )

        # Step 3: Provenance
        provenance = service.citation.build(fusion_result.candidates)

        return {
            "retrieval": {
                "vector_hits": len(retrieval["vector_hits"]),
                "graph_hits": len(retrieval["graph_hits"]),
                "graph_nodes": len(retrieval["graph_nodes_raw"]),
                "graph_edges": len(retrieval["graph_edges_raw"]),
                "timing": retrieval["timing"],
            },
            "fusion": {
                "method": fusion_result.fusion_method,
                "total_candidates": len(fusion_result.candidates),
                "vector_candidates": fusion_result.total_vector_candidates,
                "graph_candidates": fusion_result.total_graph_candidates,
                "rrf_k": fusion_result.k_param,
                "overlap": service.fusion.compute_overlap(
                    retrieval["vector_hits"], retrieval["graph_hits"]
                ),
            },
            "provenance": {
                "records": len(provenance),
                "vector_records": sum(1 for p in provenance if p.source_type == "vector"),
                "graph_records": sum(1 for p in provenance if p.source_type == "graph"),
                "cross_modal": sum(1 for p in provenance if p.source_type == "both"),
                "hash": service.citation.compute_provenance_hash(provenance),
            },
            "top_candidates": [
                {
                    "id": c.candidate_id,
                    "label": c.label,
                    "source": c.fused_source_type,
                    "vector_score": round(c.score_vector, 4),
                    "graph_score": round(c.score_graph, 4),
                    "rrf_score": round(c.rrf_score, 6),
                }
                for c in fusion_result.candidates[:10]
            ],
        }
    except Exception as e:
        logger.exception("GraphRAG diagnostics failed")
        raise HTTPException(status_code=500, detail=str(e))
