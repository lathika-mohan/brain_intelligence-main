"""Phase 10 contract tests for the isolated /api/v1/ai router."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.ai_service.dependencies import (
    get_decision_engine,
    get_graphrag_engine,
    get_prediction_engine,
    get_xai_engine,
)
from app.ai_service.schemas import AgentChatResponse
from app.main import app
from app.models.decision import (
    CostEstimate,
    DecisionLogEntry,
    MaintenanceActionType,
    PriorityLevel,
    Recommendation,
    RecommendationResponse,
    RiskFactorBreakdown,
    SeverityTier,
    SOPLinkage,
    TriggeredRule,
)
from app.models.graphrag import GraphRagContextChunk, GraphRagEdge, GraphRagNode, GraphRagQueryResponse
from app.models.predictive import (
    AnomalyFlag,
    AnomalySeverity,
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


NOW = datetime(2026, 7, 7, 7, 15, tzinfo=timezone.utc)


class DummyGraphRag:
    async def query(self, body):
        return GraphRagQueryResponse(
            answer=f"Grounded answer for {body.query_text}",
            context_chunks=[
                GraphRagContextChunk(
                    chunk_id="chunk-1",
                    text="P-101A bearing temperature SOP excerpt",
                    score=0.91,
                    document_type="SOP",
                    source="sop-p101a.pdf",
                )
            ],
            graph_nodes=[GraphRagNode(id="asset:P-101A", label="P-101A", type="Asset")],
            graph_edges=[GraphRagEdge(source="asset:P-101A", target="fm:bearing", relationship="HAS_FAILURE_MODE")],
            overall_confidence=0.87,
            graph_nodes_expanded=1,
            vector_hits=1,
            latency_ms=12.3,
            query_embedding_model="sentence-transformers/all-mpnet-base-v2",
            generated_at=NOW.isoformat(),
        )


class DummyPredictive:
    async def infer(self, body):
        window = FailureWindow(
            earliest=NOW + timedelta(days=1),
            most_likely=NOW + timedelta(days=5),
            latest=NOW + timedelta(days=8),
        )
        return InferenceResponse(
            asset_id=body.asset_id,
            component_id=body.component_id,
            rul=RulEstimate(value_days=5.2, lower_bound_days=3.5, upper_bound_days=7.8),
            failure_probability=FailureProbability(
                probability=0.64,
                predicted_window=window,
                failure_mode_id="fm-bearing-wear",
                failure_mode_label="Bearing wear",
            ),
            anomaly_flags=[
                AnomalyFlag(
                    sensor_id="sns-vib-1",
                    metric="vibration_rms",
                    anomaly_score=-0.42,
                    is_anomalous=True,
                    severity=AnomalySeverity.HIGH,
                    detected_at=NOW,
                )
            ],
            anomalous_sensors=["sns-vib-1"],
            explanation_id="pred-p101a-001",
            inference_latency_ms=9.8,
            generated_at=NOW,
        )


class DummyXAI:
    async def explain(self, request, history):
        return ExplanationResponse(
            explanation_id=request.explanation_id or "exp-1",
            asset_id=request.asset_id,
            method=request.method,
            scope=request.scope,
            base_value=0.31,
            predicted_value=0.72,
            local_feature_importance=[FeatureImpact(feature_name="vibration_rms", impact_weight=0.42, feature_value=9.5, rank=1)],
            global_feature_importance=[FeatureImpact(feature_name="bearing_temp", impact_weight=0.33, feature_value=82.0, rank=1)],
            root_cause=RootCauseSummary(
                headline="Vibration dominated alert",
                narrative="Elevated vibration is consistent with bearing wear.",
                contributing_failure_modes=["fm-bearing-wear"],
            ),
            confidence_matrix=[ConfidenceMatrixEntry(label="SHAP convergence", confidence=0.95)],
            model_name="xgboost_rul_v1",
            generated_at=NOW,
        )


class DummyDecision:
    async def recommend(self, body):
        rec = Recommendation(
            action_id="act-1",
            action_type=MaintenanceActionType.INSPECT,
            description="Inspect and lubricate P-101A drive-end bearing.",
            priority=PriorityLevel.HIGH,
            risk_score_if_ignored=0.78,
            estimated_cost_avoidance_usd=42000,
            recommended_completion_by=NOW + timedelta(days=2),
            sop_linkage=SOPLinkage(sop_id="SOP-PUMP-BEARING", title="Pump bearing inspection"),
            severity_tier=SeverityTier.SCHEDULED,
            rank=1,
        )
        log = DecisionLogEntry(
            decision_id="dec-1",
            asset_id=body.asset_id,
            triggered_rules=[TriggeredRule(rule_name="rul_threshold", condition="RUL < 14d", fired=True, resulting_tier=SeverityTier.SCHEDULED)],
            risk_breakdown=RiskFactorBreakdown(
                probability_of_failure=0.64,
                probability_scaled=6.4,
                severity_scaled=7.0,
                detectability_scaled=5.0,
                criticality_weight=1.0,
                risk_priority_number=224.0,
                normalized_risk_score=0.78,
            ),
            cost_estimate=CostEstimate(
                unplanned_downtime_cost_usd=65000,
                planned_maintenance_cost_usd=23000,
                estimated_cost_avoidance_usd=42000,
                downtime_cost_per_hour_usd=2500,
                estimated_repair_hours=26,
            ),
            rationale="Scheduled intervention reduces bearing failure risk.",
            generated_at=NOW,
        )
        return RecommendationResponse(
            asset_id=body.asset_id,
            component_id=body.component_id,
            recommendations=[rec],
            decision_log=[log],
            overall_risk_score=0.78,
            generated_at=NOW,
        )


def sample_telemetry():
    return {
        "schema_version": "1.0.0",
        "asset_id": "P-101A",
        "component_id": "bearing-de",
        "timestamp": NOW.isoformat(),
        "operating_mode": "RUNNING",
        "readings": [
            {"sensor_id": "sns-temp-1", "metric": "bearing_temp", "value": 82.0, "unit": "C", "quality": 0.99},
            {"sensor_id": "sns-vib-1", "metric": "vibration_rms", "value": 9.5, "unit": "mm/s", "quality": 0.98},
            {"sensor_id": "sns-rpm-1", "metric": "rpm", "value": 1480.0, "unit": "rpm", "quality": 1.0},
        ],
        "metadata": {},
    }


def client():
    app.dependency_overrides[get_graphrag_engine] = lambda: DummyGraphRag()
    app.dependency_overrides[get_prediction_engine] = lambda: DummyPredictive()
    app.dependency_overrides[get_xai_engine] = lambda: DummyXAI()
    app.dependency_overrides[get_decision_engine] = lambda: DummyDecision()
    return TestClient(app)


def test_ai_health_and_openapi_paths():
    c = client()
    health = c.get("/api/v1/ai/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ready"

    spec = c.get("/openapi.json").json()
    for path in [
        "/api/v1/ai/query",
        "/api/v1/ai/predict",
        "/api/v1/ai/explain/{prediction_id}",
        "/api/v1/ai/recommend",
        "/api/v1/ai/agent/chat",
    ]:
        assert path in spec["paths"]


def test_graphrag_query_contract():
    res = client().post("/api/v1/ai/query", json={"query_text": "Why is P-101A vibrating?", "asset_id": "P-101A"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    assert payload["data"]["answer"].startswith("Grounded answer")
    assert payload["data"]["graph_nodes"][0]["id"] == "asset:P-101A"
    assert payload["data"]["vector_hits"] == 1


def test_predictive_contract():
    res = client().post(
        "/api/v1/ai/predict",
        json={"asset_id": "P-101A", "component_id": "bearing-de", "history": [sample_telemetry()], "horizon_hours": 72},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["rul"]["value_days"] == 5.2
    assert data["failure_probability"]["probability"] == 0.64
    assert data["anomaly_flags"][0]["severity"] == "HIGH"


def test_explain_contract():
    res = client().get("/api/v1/ai/explain/pred-p101a-001?asset_id=P-101A")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["prediction_id"] == "pred-p101a-001"
    assert data["explanation"]["local_feature_importance"][0]["feature_name"] == "vibration_rms"


def test_recommend_contract():
    res = client().post("/api/v1/ai/recommend", json={"asset_id": "P-101A", "max_recommendations": 3})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["recommendations"][0]["sop_linkage"]["sop_id"] == "SOP-PUMP-BEARING"
    assert data["decision_log"][0]["risk_breakdown"]["normalized_risk_score"] == 0.78


def test_agent_chat_contract():
    res = client().post(
        "/api/v1/ai/agent/chat",
        json={
            "session_id": "sess-1",
            "asset_id": "P-101A",
            "messages": [{"role": "user", "content": "Diagnose P-101A vibration."}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    parsed = AgentChatResponse.model_validate(body["data"])
    assert parsed.session_id == "sess-1"
    assert parsed.states[-1].state == "final"


def test_validation_error_sanitized_for_bad_predict_payload():
    res = client().post("/api/v1/ai/predict", json={"asset_id": "P-101A", "history": []})
    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False
    assert body["error_code"] == "VALIDATION_ERROR"
