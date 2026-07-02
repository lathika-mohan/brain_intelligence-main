"""
GraphRAG Engine router — powers `GraphRagPanel.tsx`.

Phase 0 scope: expose the FROZEN request/response contract behind a real,
runnable FastAPI route so Member 4 can bind against it today. The handler
returns a schema-valid stub payload; the actual vector+graph fusion
pipeline is out of scope for Phase 0 and lands in a later phase.
"""
from __future__ import annotations

import time

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.common import APIResponse
from app.models.graphrag import (
    Citation,
    GraphContextMap,
    GraphEdge,
    GraphNode,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    VectorContextChunk,
)

router = APIRouter(prefix="/graphrag", tags=["graphrag"])


@router.post("/query", response_model=APIResponse[GraphRagQueryResponse])
def query_graphrag(payload: GraphRagQueryRequest) -> APIResponse[GraphRagQueryResponse]:
    """
    Contract-frozen stub. Replace body with real vector+graph fusion in a
    later phase; the response SHAPE must not change without renegotiating
    with Member 4.
    """
    settings = get_settings()
    started = time.perf_counter()

    stub_chunk = VectorContextChunk(
        chunk_id="chunk-stub-0001",
        text=(
            "Stub context: bearing over-temperature events on this asset class are typically "
            "mitigated by lubrication interval reduction per SOP-114."
        ),
        source_document="SOP-114-Bearing-Maintenance.pdf",
        source_type="SOP",
        confidence_score=0.82,
        page_number=3,
    )
    graph_context = GraphContextMap(
        nodes=[
            GraphNode(id="asset-stub-1", label="Asset", display_name="Pump-101", properties={}),
            GraphNode(
                id="failuremode-stub-1",
                label="FailureMode",
                display_name="Bearing Overheat",
                properties={},
            ),
            GraphNode(id="sop-stub-1", label="SOP", display_name="SOP-114", properties={}),
        ],
        edges=[
            GraphEdge(
                source_id="asset-stub-1",
                target_id="failuremode-stub-1",
                relationship="INDICATES_FAILURE",
            ),
            GraphEdge(
                source_id="failuremode-stub-1",
                target_id="sop-stub-1",
                relationship="MITIGATED_BY",
            ),
        ],
        root_node_ids=["asset-stub-1"],
    )
    citation = Citation(
        citation_id="cite-stub-0001",
        claim_span="lubrication interval reduction",
        source_document="SOP-114-Bearing-Maintenance.pdf",
        source_type="SOP",
        source_node_id="sop-stub-1",
        confidence_score=0.82,
    )

    response = GraphRagQueryResponse(
        query=payload.query,
        answer=(
            "[STUB] Based on retrieved SOP context, the most likely mitigation for the queried "
            "asset condition is a lubrication interval reduction per SOP-114."
        ),
        vector_context=[stub_chunk] if payload.top_k_vector > 0 else [],
        graph_context=graph_context if payload.include_graph_context else None,
        citations=[citation] if payload.include_citations else [],
        overall_confidence=0.82,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return APIResponse[GraphRagQueryResponse](data=response)
