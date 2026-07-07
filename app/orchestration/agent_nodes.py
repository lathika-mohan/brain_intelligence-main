"""LangGraph node implementations for Phase 9 specialized agents."""
from __future__ import annotations

from typing import Any

from app.models.graphrag import GraphRagQueryResponse
from app.orchestration.state import AgentName, AgentState
from app.orchestration.tools import (
    DecisionInput,
    ExplanationInput,
    KnowledgeQueryInput,
    PredictionInput,
    RetrievalQueryInput,
    ToolRegistry,
    fallback_history,
)
from app.orchestration.utils import ensure_state, export_state, with_retries


class AgentNodes:
    def __init__(self, tools: ToolRegistry | None = None) -> None:
        self.tools = tools or ToolRegistry()

    async def supervisor(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        from app.orchestration.routing import plan_route
        state = ensure_state(raw_state)
        state.active_agent = AgentName.SUPERVISOR
        state.append_trace(AgentName.SUPERVISOR.value)
        if not state.route_plan:
            state.route_plan = plan_route(state)
        state.compress()
        return export_state(state)

    async def knowledge_agent(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        state = ensure_state(raw_state)
        state.append_trace(AgentName.KNOWLEDGE.value)
        asset = state.active_asset_id or "unknown-asset"
        result = await with_retries(
            state=state,
            agent=AgentName.KNOWLEDGE.value,
            operation="query_knowledge_graph",
            call=lambda: self.tools.query_knowledge_graph(KnowledgeQueryInput(asset_id=asset)),
            max_retries=1,
        )
        if result:
            state.graph_nodes = result.graph_nodes
            state.graph_edges = result.graph_edges
            state.intermediate_payloads["knowledge"] = result.model_dump(mode="json")
        state.compress()
        return export_state(state)

    async def retrieval_agent(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        state = ensure_state(raw_state)
        state.append_trace(AgentName.RETRIEVAL.value)
        result = await with_retries(
            state=state,
            agent=AgentName.RETRIEVAL.value,
            operation="semantic_retrieve",
            call=lambda: self.tools.semantic_retrieve(
                RetrievalQueryInput(
                    query_text=state.query_text,
                    top_k=state.top_k,
                    asset_id=state.active_asset_id,
                )
            ),
            max_retries=1,
        )
        if result:
            state.context_chunks = result.context_chunks
            state.intermediate_payloads["retrieval"] = result.model_dump(mode="json")
        state.compress()
        return export_state(state)

    async def prediction_agent(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        state = ensure_state(raw_state)
        state.append_trace(AgentName.PREDICTION.value)
        asset = state.active_asset_id or "asset-unknown"
        history = state.telemetry_history or fallback_history(asset)
        state.telemetry_history = history
        result = await with_retries(
            state=state,
            agent=AgentName.PREDICTION.value,
            operation="predict",
            call=lambda: self.tools.predict(
                PredictionInput(
                    asset_id=asset,
                    component_id=state.component_id,
                    history=history,
                    horizon_hours=max(state.risk_horizon_days * 24, 24),
                )
            ),
            max_retries=1,
        )
        if result:
            state.prediction = result
            state.component_id = state.component_id or result.component_id
            state.current_anomaly = bool(result.anomalous_sensors)
            state.anomaly_flags = [flag.model_dump(mode="json") for flag in result.anomaly_flags]
            state.model_predictions["rul_days"] = result.rul.value_days
            state.model_predictions["failure_probability"] = result.failure_probability.probability
        state.compress()
        return export_state(state)

    async def explanation_agent(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        state = ensure_state(raw_state)
        state.append_trace(AgentName.EXPLANATION.value)
        asset = state.active_asset_id or "asset-unknown"
        history = state.telemetry_history or fallback_history(asset)
        explanation_id = state.prediction.explanation_id if state.prediction else None
        result = await with_retries(
            state=state,
            agent=AgentName.EXPLANATION.value,
            operation="explain",
            call=lambda: self.tools.explain(
                ExplanationInput(asset_id=asset, explanation_id=explanation_id, history=history)
            ),
            max_retries=1,
        )
        if result:
            state.explanation = result
            state.intermediate_payloads["top_features"] = [
                item.model_dump(mode="json") for item in result.local_feature_importance[:5]
            ]
        state.compress()
        return export_state(state)

    async def decision_agent(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        state = ensure_state(raw_state)
        state.append_trace(AgentName.DECISION.value)
        asset = state.active_asset_id or "asset-unknown"
        result = await with_retries(
            state=state,
            agent=AgentName.DECISION.value,
            operation="decide",
            call=lambda: self.tools.decide(
                DecisionInput(
                    asset_id=asset,
                    component_id=state.component_id,
                    risk_horizon_days=state.risk_horizon_days,
                    max_recommendations=state.max_recommendations,
                )
            ),
            max_retries=1,
        )
        if result:
            state.decision = result
            state.confidence = max(state.confidence, min(0.95, 0.55 + result.overall_risk_score * 0.35))
        state.compress()
        return export_state(state)

    async def finalizer(self, raw_state: AgentState | dict[str, Any]) -> dict[str, Any]:
        state = ensure_state(raw_state)
        state.append_trace(AgentName.FINALIZER.value)
        state.active_agent = AgentName.FINALIZER
        state.terminal = True

        state.graphrag = GraphRagQueryResponse(
            answer=None,
            context_chunks=state.context_chunks,
            graph_nodes=state.graph_nodes,
            graph_edges=state.graph_edges,
            overall_confidence=state.confidence or (0.65 if state.context_chunks or state.graph_nodes else 0.0),
            graph_nodes_expanded=len(state.graph_nodes),
            vector_hits=len(state.context_chunks),
            query_embedding_model=str(state.intermediate_payloads.get("retrieval", {}).get("query_embedding_model", ""))
            if isinstance(state.intermediate_payloads.get("retrieval"), dict) else "",
        )

        parts: list[str] = []
        if state.active_asset_id:
            parts.append(f"Asset: {state.active_asset_id}.")
        if state.context_chunks:
            parts.append(f"Retrieved {len(state.context_chunks)} documentation context block(s).")
        if state.graph_nodes:
            parts.append(f"Expanded {len(state.graph_nodes)} graph node(s).")
        if state.prediction:
            parts.append(
                f"Prediction: RUL {state.prediction.rul.value_days:.2f} days; "
                f"failure probability {state.prediction.failure_probability.probability:.2f}."
            )
        if state.explanation and state.explanation.local_feature_importance:
            top = state.explanation.local_feature_importance[0].feature_name
            parts.append(f"Top explanation driver: {top}.")
        if state.decision and state.decision.recommendations:
            rec = state.decision.recommendations[0]
            parts.append(f"Recommended action: {rec.priority.value} {rec.action_type.value} — {rec.description}")
        if state.errors:
            parts.append(f"Completed with {len(state.errors)} recovered tool error(s).")
        state.answer = " ".join(parts) if parts else "Request completed; no specialized evidence was available."
        state.confidence = state.confidence or state.graphrag.overall_confidence
        state.messages.append({"role": "assistant", "content": state.answer})
        state.estimate_tokens()
        return export_state(state)
