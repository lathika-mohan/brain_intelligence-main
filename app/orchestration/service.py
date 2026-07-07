"""Public backend service facade for the Phase 9 orchestrator."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Optional

from app.orchestration.state import AgentState, OrchestratorRequest, OrchestratorResponse
from app.orchestration.tools import ToolRegistry
from app.orchestration.topology import build_agent_graph


class OrchestrationService:
    def __init__(self, *, tool_registry: ToolRegistry | None = None, compiled_graph: Any | None = None) -> None:
        self._tool_registry = tool_registry or ToolRegistry()
        self._graph = compiled_graph or build_agent_graph(self._tool_registry)

    async def execute(self, request: OrchestratorRequest) -> OrchestratorResponse:
        request_id = str(uuid.uuid4())
        state = AgentState.from_request(request, request_id=request_id)
        raw_result = await self._graph.ainvoke(
            state,
            config={"recursion_limit": min(request.max_transitions, 15)},
        )
        final_state = AgentState.model_validate(raw_result)
        if not final_state.answer:
            final_state.answer = "The orchestrator completed without a generated answer."
        return OrchestratorResponse(
            request_id=final_state.request_id,
            answer=final_state.answer,
            active_asset_id=final_state.active_asset_id,
            component_id=final_state.component_id,
            confidence=final_state.confidence,
            route_taken=final_state.visited_nodes,
            trace=final_state.trace if request.include_debug_trace else [],
            errors=final_state.errors,
            token_metrics=final_state.token_metrics,
            graphrag=final_state.graphrag,
            prediction=final_state.prediction,
            explanation=final_state.explanation,
            decision=final_state.decision,
            generated_at=final_state.generated_at,
        )


_service_lock = threading.Lock()
_service: Optional[OrchestrationService] = None


def get_orchestration_service() -> OrchestrationService:
    global _service
    with _service_lock:
        if _service is None:
            _service = OrchestrationService()
        return _service


def reset_orchestration_service() -> None:
    global _service
    with _service_lock:
        _service = None
