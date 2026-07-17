"""Phase 10 lightweight adapter for Phase 9 LangGraph-style diagnostics.

The repository snapshot does not expose a concrete LangGraph package/module,
so this adapter provides a stable structured state API and delegates to the
Phase 5 GraphRAG and Phase 8 decision services when available. If a real
LangGraph workflow is later added, swap ``run_agent_chat`` internals without
changing the public router contract.
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, Callable, List, Optional

from app.ai_service.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentState,
    AgentStateName,
)
from app.models.decision import RecommendationRequest
from app.models.graphrag import GraphRagQueryRequest


def _last_user_text(request: AgentChatRequest) -> str:
    for message in reversed(request.messages):
        if message.role.value == "user":
            return message.content
    return request.messages[-1].content


async def run_agent_chat(
    request: AgentChatRequest,
    *,
    graphrag_engine: Optional[Any] = None,
    decision_engine: Optional[Any] = None,
) -> AgentChatResponse:
    """Run a structured diagnostic chat turn and return accumulated states."""

    session_id = request.session_id or f"agent-{uuid.uuid4()}"
    prompt = _last_user_text(request)
    states: List[AgentState] = [
        AgentState(state=AgentStateName.RECEIVED, message="Accepted diagnostic chat turn.", payload={"messages": len(request.messages)}),
        AgentState(state=AgentStateName.TRIAGED, message="Identified asset and selected GraphRAG/decision tools.", payload={"asset_id": request.asset_id}),
    ]

    graph_payload: dict[str, Any] = {}
    if request.include_graph_context and graphrag_engine is not None:
        try:
            graph_resp = await graphrag_engine.query(
                GraphRagQueryRequest(query_text=prompt, asset_id=request.asset_id, top_k=5)
            )
            graph_payload = graph_resp.model_dump(mode="json")
            states.append(
                AgentState(
                    state=AgentStateName.GRAPHRAG_RETRIEVED,
                    message="Retrieved fused vector/graph context.",
                    payload={
                        "answer_preview": (graph_resp.answer or "")[:280],
                        "vector_hits": graph_resp.vector_hits,
                        "graph_nodes": len(graph_resp.graph_nodes),
                        "citations": len(graph_resp.citations),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001 - agent states should explain degraded tools
            states.append(
                AgentState(
                    state=AgentStateName.GRAPHRAG_RETRIEVED,
                    message="GraphRAG tool degraded; continuing with diagnostic state.",
                    payload={"degraded": True, "reason": exc.__class__.__name__},
                )
            )

    decision_payload: dict[str, Any] = {}
    if request.include_recommendations and request.asset_id and decision_engine is not None:
        try:
            rec_resp = await decision_engine.recommend(RecommendationRequest(asset_id=request.asset_id, max_recommendations=3))
            decision_payload = rec_resp.model_dump(mode="json")
            states.append(
                AgentState(
                    state=AgentStateName.DECISION_EVALUATED,
                    message="Evaluated risk-ranked maintenance actions.",
                    payload={
                        "recommendations": len(rec_resp.recommendations),
                        "overall_risk_score": rec_resp.overall_risk_score,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            states.append(
                AgentState(
                    state=AgentStateName.DECISION_EVALUATED,
                    message="Decision engine degraded; returning available diagnostic context.",
                    payload={"degraded": True, "reason": exc.__class__.__name__},
                )
            )

    if graph_payload.get("answer"):
        final = graph_payload["answer"]
    elif decision_payload.get("recommendations"):
        first = decision_payload["recommendations"][0]
        final = f"Recommended next action: {first.get('description', 'review maintenance action')}"
    else:
        final = (
            "Diagnostic triage completed. Provide recent telemetry or an asset id to enrich the "
            "answer with GraphRAG context and risk-ranked recommendations."
        )

    states.append(AgentState(state=AgentStateName.FINAL, message="Diagnostic turn completed.", payload={"response_length": len(final)}))
    return AgentChatResponse(session_id=session_id, asset_id=request.asset_id, final_answer=final, states=states)


async def iter_agent_states(response_factory: Callable[[], Any]) -> AsyncIterator[str]:
    """Yield AgentState objects as NDJSON from a completed response factory."""

    response: AgentChatResponse = await response_factory()
    for state in response.states:
        yield state.model_dump_json() + "\n"
