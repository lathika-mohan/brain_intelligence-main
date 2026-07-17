"""Phase 9 LangGraph topology and fallback executor."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from app.orchestration.agent_nodes import AgentNodes
from app.orchestration.routing import next_after_agent, supervisor_next
from app.orchestration.state import AgentName, AgentState
from app.orchestration.tools import ToolRegistry
from app.orchestration.utils import ensure_state, export_state

try:  # pragma: no cover - exercised when dependency is installed
    from langgraph.graph import END, StateGraph
except Exception:  # noqa: BLE001 - offline CI fallback
    END = "__end__"
    StateGraph = None  # type: ignore[assignment]


class FallbackCompiledGraph:
    """Small deterministic executor used only when langgraph is not installed.

    Production deployments use LangGraph; the fallback keeps offline pytest and
    static contract validation executable in constrained environments.
    """

    def __init__(self, nodes: AgentNodes) -> None:
        self.nodes = nodes
        self._node_map: Dict[str, Callable[[Any], Awaitable[dict[str, Any]]]] = {
            AgentName.SUPERVISOR.value: nodes.supervisor,
            AgentName.RETRIEVAL.value: nodes.retrieval_agent,
            AgentName.KNOWLEDGE.value: nodes.knowledge_agent,
            AgentName.PREDICTION.value: nodes.prediction_agent,
            AgentName.EXPLANATION.value: nodes.explanation_agent,
            AgentName.DECISION.value: nodes.decision_agent,
            AgentName.FINALIZER.value: nodes.finalizer,
        }

    async def ainvoke(self, initial_state: AgentState | dict[str, Any], config: Optional[dict] = None) -> dict[str, Any]:
        state = ensure_state(initial_state)
        limit = int((config or {}).get("recursion_limit", state.max_transitions))
        current = AgentName.SUPERVISOR.value
        while current != END and state.transition_count < limit:
            raw = await self._node_map[current](state)
            state = ensure_state(raw)
            if current == AgentName.SUPERVISOR.value:
                current = supervisor_next(state)
                if current == AgentName.END.value:
                    current = END
            elif current == AgentName.FINALIZER.value:
                current = END
            else:
                current = next_after_agent(state)
        if current != END and not state.terminal:
            raw = await self.nodes.finalizer(state)
            state = ensure_state(raw)
        return export_state(state)


def build_agent_graph(tool_registry: ToolRegistry | None = None):
    nodes = AgentNodes(tool_registry)
    if StateGraph is None:
        return FallbackCompiledGraph(nodes)

    workflow = StateGraph(AgentState)  # type: ignore[operator]
    workflow.add_node(AgentName.SUPERVISOR.value, nodes.supervisor)
    workflow.add_node(AgentName.RETRIEVAL.value, nodes.retrieval_agent)
    workflow.add_node(AgentName.KNOWLEDGE.value, nodes.knowledge_agent)
    workflow.add_node(AgentName.PREDICTION.value, nodes.prediction_agent)
    workflow.add_node(AgentName.EXPLANATION.value, nodes.explanation_agent)
    workflow.add_node(AgentName.DECISION.value, nodes.decision_agent)
    workflow.add_node(AgentName.FINALIZER.value, nodes.finalizer)

    workflow.set_entry_point(AgentName.SUPERVISOR.value)
    workflow.add_conditional_edges(
        AgentName.SUPERVISOR.value,
        supervisor_next,
        {
            AgentName.RETRIEVAL.value: AgentName.RETRIEVAL.value,
            AgentName.KNOWLEDGE.value: AgentName.KNOWLEDGE.value,
            AgentName.PREDICTION.value: AgentName.PREDICTION.value,
            AgentName.EXPLANATION.value: AgentName.EXPLANATION.value,
            AgentName.DECISION.value: AgentName.DECISION.value,
            AgentName.FINALIZER.value: AgentName.FINALIZER.value,
            AgentName.END.value: END,
        },
    )
    for agent in [
        AgentName.RETRIEVAL,
        AgentName.KNOWLEDGE,
        AgentName.PREDICTION,
        AgentName.EXPLANATION,
        AgentName.DECISION,
    ]:
        workflow.add_conditional_edges(
            agent.value,
            next_after_agent,
            {
                AgentName.SUPERVISOR.value: AgentName.SUPERVISOR.value,
                AgentName.FINALIZER.value: AgentName.FINALIZER.value,
            },
        )
    workflow.add_edge(AgentName.FINALIZER.value, END)
    return workflow.compile()
