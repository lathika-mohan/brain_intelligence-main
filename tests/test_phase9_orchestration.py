from __future__ import annotations

from datetime import timedelta

import asyncio

from app.models.common import utc_now
from app.models.decision import (
    MaintenanceActionType,
    PriorityLevel,
    Recommendation,
    RecommendationResponse,
)
from app.models.graphrag import GraphRagContextChunk, GraphRagNode
from app.models.predictive import (
    FailureProbability,
    FailureWindow,
    InferenceResponse,
    RulEstimate,
)
from app.models.xai import (
    ConfidenceMatrixEntry,
    ExplanationMethod,
    ExplanationResponse,
    ExplanationScope,
    FeatureImpact,
    RootCauseSummary,
)
from app.orchestration.service import OrchestrationService
from app.orchestration.state import OrchestratorRequest
from app.orchestration.tools import (
    DecisionInput,
    ExplanationInput,
    KnowledgeQueryInput,
    KnowledgeResult,
    PredictionInput,
    RetrievalQueryInput,
    RetrievalResult,
    ToolRegistry,
)


class FakeTools(ToolRegistry):
    async def query_knowledge_graph(self, payload: KnowledgeQueryInput) -> KnowledgeResult:
        return KnowledgeResult(
            graph_nodes=[GraphRagNode(id=payload.asset_id, label=payload.asset_id, type="Asset")],
            graph_nodes_expanded=1,
        )

    async def semantic_retrieve(self, payload: RetrievalQueryInput) -> RetrievalResult:
        return RetrievalResult(
            context_chunks=[
                GraphRagContextChunk(
                    chunk_id="c1",
                    text="Pressure high SOP: verify discharge valve and vibration.",
                    score=0.91,
                    document_type="SOP",
                    source="test",
                )
            ],
            vector_hits=1,
            query_embedding_model="fake-embedding",
        )

    async def predict(self, payload: PredictionInput) -> InferenceResponse:
        now = utc_now()
        return InferenceResponse(
            asset_id=payload.asset_id,
            component_id=payload.component_id or "cmp-1",
            rul=RulEstimate(value_days=5.0, lower_bound_days=3.5, upper_bound_days=6.5),
            failure_probability=FailureProbability(
                probability=0.72,
                predicted_window=FailureWindow(
                    earliest=now + timedelta(days=3),
                    latest=now + timedelta(days=7),
                    most_likely=now + timedelta(days=5),
                ),
                failure_mode_id="failuremode-bearing-overheat",
                failure_mode_label="Bearing Overheat",
            ),
            anomaly_flags=[],
            anomalous_sensors=[],
            explanation_id="exp-test",
        )

    async def explain(self, payload: ExplanationInput) -> ExplanationResponse:
        return ExplanationResponse(
            explanation_id=payload.explanation_id or "exp-test",
            asset_id=payload.asset_id,
            method=ExplanationMethod.SHAP,
            scope=ExplanationScope.LOCAL,
            base_value=0.2,
            predicted_value=0.8,
            local_feature_importance=[
                FeatureImpact(feature_name="pressure", impact_weight=0.42, feature_value=12.5, rank=1)
            ],
            root_cause=RootCauseSummary(
                headline="Pressure dominated anomaly",
                narrative="Pressure is the primary contributor.",
                contributing_failure_modes=["failuremode-bearing-overheat"],
            ),
            confidence_matrix=[ConfidenceMatrixEntry(label="stability", confidence=0.9)],
            model_name="test-model",
        )

    async def decide(self, payload: DecisionInput) -> RecommendationResponse:
        now = utc_now()
        return RecommendationResponse(
            asset_id=payload.asset_id,
            component_id=payload.component_id or "cmp-1",
            recommendations=[
                Recommendation(
                    action_id="a1",
                    action_type=MaintenanceActionType.INSPECT,
                    description="Inspect pressure control loop and discharge valve.",
                    priority=PriorityLevel.HIGH,
                    risk_score_if_ignored=0.82,
                    estimated_cost_avoidance_usd=10000.0,
                    recommended_completion_by=now + timedelta(days=2),
                    rank=1,
                )
            ],
            overall_risk_score=0.82,
        )


class FlakyRetrievalTools(FakeTools):
    def __init__(self) -> None:
        self.calls = 0

    async def semantic_retrieve(self, payload: RetrievalQueryInput) -> RetrievalResult:
        self.calls += 1
        raise TimeoutError("qdrant timeout")


def test_phase9_diagnostic_route_order_and_contract_projection():
    service = OrchestrationService(tool_registry=FakeTools())
    response = asyncio.run(service.execute(
        OrchestratorRequest(query_text="Why is the pressure high on Pump-2?", max_transitions=15)
    ))

    assert response.active_asset_id == "Pump-2"
    assert response.route_taken == [
        "supervisor",
        "retrieval_agent",
        "supervisor",
        "knowledge_agent",
        "supervisor",
        "prediction_agent",
        "supervisor",
        "explanation_agent",
        "supervisor",
        "decision_agent",
        "supervisor",
        "finalizer",
    ]
    assert response.graphrag is not None
    assert response.graphrag.vector_hits == 1
    assert response.prediction is not None
    assert response.explanation is not None
    assert response.decision is not None
    assert response.decision.recommendations[0].priority == PriorityLevel.HIGH
    assert "Recommended action" in response.answer


def test_phase9_retry_boundary_recovers_and_finalizes():
    service = OrchestrationService(tool_registry=FlakyRetrievalTools())
    response = asyncio.run(service.execute(
        OrchestratorRequest(query_text="Show documentation context for Pump-9", asset_id="Pump-9")
    ))

    assert response.route_taken[-1] == "finalizer"
    assert response.errors
    assert response.errors[0].agent == "retrieval_agent"
    assert response.graphrag is not None
    assert response.graphrag.vector_hits == 0


def test_phase9_recursion_limit_prevents_unbounded_execution():
    service = OrchestrationService(tool_registry=FakeTools())
    response = asyncio.run(service.execute(
        OrchestratorRequest(
            query_text="Generate a risk report for the main compressor",
            asset_id="main-compressor",
            max_transitions=6,
        )
    ))

    assert len(response.route_taken) <= 7  # 6 bounded transitions plus forced finalizer if needed
    assert response.answer
