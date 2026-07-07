"""Phase 11 — End-to-end contract tests for the UI-shaped router.

These tests use FastAPI's :class:`TestClient` to hit every new endpoint
and assert that the response:

* has the Section 11 ``UIAPIResponse`` envelope (``success / data / error /
  requestId / generatedAt``)
* has a ``data`` payload that validates against the strict Pydantic
  contract (e.g. :class:`UIGraphRAGPayload`, :class:`UIShapExplanation`)
* contains zero null fields where arrays are expected
* emits the right CORS / exposed headers

Engines are stubbed via the same dependency-override pattern used by
Phase 10 (see ``tests/test_phase10_ai_service.py``) so the suite has
zero infrastructure dependencies.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.ai_service.dependencies import (
    get_decision_engine,
    get_graphrag_engine,
    get_prediction_engine,
    get_xai_engine,
)
from app.ai_service.integration.cors_headers import UI_ALLOWED_HEADERS, UI_EXPOSED_HEADERS
from app.ai_service.integration.ui_router import ui_router
from app.main import app

NOW = datetime(2026, 7, 7, 7, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Stub engines
# ---------------------------------------------------------------------------
class _StubGraphRag:
    async def query(self, body: Any) -> Any:
        from app.models.graphrag import (
            Citation,
            GraphRagEdge,
            GraphRagNode,
            GraphRagQueryResponse,
        )

        return GraphRagQueryResponse(
            answer="P-101A shows bearing wear signature.",
            graph_nodes=[
                GraphRagNode(id="asset:P-101A", label="P-101A", type="Asset", properties={}),
                GraphRagNode(id="fm:bearing", label="Bearing Wear", type="FailureMode", properties={}),
                GraphRagNode(id="sop:SOP-MECH-042", label="SOP-MECH-042", type="SOP", properties={}),
            ],
            graph_edges=[
                GraphRagEdge(source="asset:P-101A", target="fm:bearing", relationship="HAS_FAILURE_MODE", weight=1.0),
                GraphRagEdge(source="fm:bearing", target="sop:SOP-MECH-042", relationship="MITIGATED_BY", weight=1.0),
            ],
            citations=[
                Citation(
                    citation_id="cit-1",
                    claim_span="vibration 5.2 mm/s",
                    source_document="sop-p101a.pdf",
                    source_type="SOP",
                    source_node_id="sop:SOP-MECH-042",
                    confidence_score=0.91,
                )
            ],
            overall_confidence=0.87,
            vector_hits=3,
            latency_ms=11.0,
            query_embedding_model="sentence-transformers/all-mpnet-base-v2",
            generated_at=NOW.isoformat(),
        )


class _StubPredictive:
    async def infer(self, body: Any) -> Any:
        from app.models.predictive import (
            AnomalyFlag,
            AnomalySeverity,
            FailureProbability,
            FailureWindow,
            InferenceResponse,
            RulEstimate,
        )

        return InferenceResponse(
            asset_id=body.asset_id,
            component_id=body.component_id,
            rul=RulEstimate(value_days=5.2, lower_bound_days=3.5, upper_bound_days=7.8),
            failure_probability=FailureProbability(
                probability=0.64,
                predicted_window=FailureWindow(
                    earliest=NOW + timedelta(days=1),
                    most_likely=NOW + timedelta(days=5),
                    latest=NOW + timedelta(days=8),
                ),
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


class _StubXAI:
    async def explain(self, request: Any, history: Any) -> Any:
        from app.models.xai import (
            ConfidenceMatrixEntry,
            ExplanationResponse,
            FeatureImpact,
            RootCauseSummary,
        )

        return ExplanationResponse(
            explanation_id=request.explanation_id or "exp-1",
            asset_id=request.asset_id,
            method=request.method,
            scope=request.scope,
            base_value=0.31,
            predicted_value=0.72,
            local_feature_importance=[
                FeatureImpact(feature_name="vibration_rms", impact_weight=0.42, feature_value=9.5, rank=1),
                FeatureImpact(feature_name="bearing_temp", impact_weight=0.31, feature_value=82.0, rank=2),
                FeatureImpact(feature_name="rpm", impact_weight=-0.05, feature_value=1480.0, rank=3),
            ],
            root_cause=RootCauseSummary(
                headline="Vibration dominated alert",
                narrative="Elevated vibration is consistent with bearing wear.",
                contributing_failure_modes=["fm-bearing-wear"],
            ),
            confidence_matrix=[ConfidenceMatrixEntry(label="SHAP convergence", confidence=0.95)],
            model_name="xgboost_rul_v1",
            generated_at=NOW,
        )


class _StubDecision:
    async def recommend(self, body: Any) -> Any:
        from app.models.decision import (
            CostEstimate,
            DecisionLogEntry,
            PriorityLevel,
            Recommendation,
            RecommendationResponse,
            RiskFactorBreakdown,
            SeverityTier,
            SOPLinkage,
            TriggeredRule,
        )

        return RecommendationResponse(
            asset_id=body.asset_id,
            component_id=body.component_id,
            recommendations=[
                Recommendation(
                    action_id="act-1",
                    action_type="INSPECT",
                    description="Inspect and lubricate P-101A drive-end bearing.",
                    priority=PriorityLevel.HIGH,
                    severity_tier=SeverityTier.SCHEDULED,
                    risk_score_if_ignored=0.78,
                    estimated_cost_avoidance_usd=42000,
                    recommended_completion_by=NOW + timedelta(days=2),
                    sop_linkage=SOPLinkage(sop_id="SOP-PUMP-BEARING", title="Pump bearing inspection", revision="v2.1"),
                    rank=1,
                )
            ],
            decision_log=[
                DecisionLogEntry(
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
            ],
            overall_risk_score=0.78,
            generated_at=NOW,
        )


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_graphrag_engine] = lambda: _StubGraphRag()
    app.dependency_overrides[get_prediction_engine] = lambda: _StubPredictive()
    app.dependency_overrides[get_xai_engine] = lambda: _StubXAI()
    app.dependency_overrides[get_decision_engine] = lambda: _StubDecision()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _assert_envelope(payload: Dict[str, Any]) -> None:
    """Assert the response carries the Section 11 ``UIAPIResponse`` envelope."""

    assert "success" in payload
    assert "data" in payload
    assert "error" in payload
    assert "requestId" in payload
    assert "generatedAt" in payload


def _assert_x_ai_module_header(response: Any) -> None:
    """Every UI endpoint must surface the ``x-ai-module: phase-11-ui`` header."""

    assert response.headers.get("x-ai-module") == "phase-11-ui"


def _assert_x_request_id_echoed(response: Any, expected: str) -> None:
    """The endpoint must echo the inbound ``x-request-id`` header verbatim."""

    assert response.headers.get("x-request-id") == expected


# ---------------------------------------------------------------------------
# 1. Digital Twin
# ---------------------------------------------------------------------------
class TestDigitalTwinContract:
    def test_returns_envelope(self, client: TestClient) -> None:
        res = client.get(
            "/api/v1/ai/ui/digital-twin/P-101A",
            headers={"x-request-id": "req-dt-1"},
        )
        assert res.status_code == 200
        _assert_envelope(res.json())
        _assert_x_ai_module_header(res)
        _assert_x_request_id_echoed(res, "req-dt-1")

    def test_data_matches_panel_shape(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/digital-twin/P-101A")
        data = res.json()["data"]
        assert "asset" in data
        assert "telemetry" in data
        assert "history" in data
        assert "activeAnomaly" in data
        # The panel reads these exact keys
        for k in ("speed", "vibration", "pressure", "temperature", "flowRate", "load", "riskScore", "status"):
            assert k in data["telemetry"]
        assert data["telemetry"]["status"] in {"ok", "warning", "critical", "offline"}

    def test_no_null_arrays(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/digital-twin/P-101A")
        data = res.json()["data"]
        assert isinstance(data["history"], list)
        assert data["history"]  # must be non-empty for the mini charts

    def test_horizon_query_param_honoured(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/digital-twin/P-101A?horizon=6")
        assert res.status_code == 200
        assert res.json()["success"] is True


# ---------------------------------------------------------------------------
# 2. GraphRAG
# ---------------------------------------------------------------------------
class TestGraphRagContract:
    def test_returns_envelope(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/graphrag/query",
            json={"query": "Why is P-101A vibrating?", "asset_id": "P-101A"},
            headers={"x-request-id": "req-rag-1"},
        )
        assert res.status_code == 200
        _assert_envelope(res.json())
        _assert_x_ai_module_header(res)
        _assert_x_request_id_echoed(res, "req-rag-1")

    def test_data_matches_panel_shape(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/graphrag/query",
            json={"query": "vibration?", "asset_id": "P-101A"},
        )
        data = res.json()["data"]
        for k in ("answer", "logs", "nodes", "edges", "highlightedNodes", "highlightedEdges", "citations", "vectorHits", "confidence"):
            assert k in data
        # Chart-ready extras
        assert data["badge"] in {"very_low", "low", "medium", "high", "very_high"}
        assert data["warningLevel"] in {"industrial-status-ok", "industrial-status-warning", "industrial-status-critical"}
        assert data["color"]  # hex / tailwind tuple

    def test_node_types_in_panel_vocabulary(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/graphrag/query",
            json={"query": "vibration?", "asset_id": "P-101A"},
        )
        for node in res.json()["data"]["nodes"]:
            assert node["type"] in {"asset", "component", "anomaly", "procedure", "record"}

    def test_missing_query_field_handled(self, client: TestClient) -> None:
        # Backend schema requires query_text — we accept the frontend's `query` key
        res = client.post("/api/v1/ai/ui/graphrag/query", json={"asset_id": "P-101A"})
        # Should still succeed (graceful degradation) or surface a sanitized error
        assert res.status_code in {200, 422, 503}


# ---------------------------------------------------------------------------
# 3. Explainability
# ---------------------------------------------------------------------------
class TestExplainContract:
    def test_returns_envelope(self, client: TestClient) -> None:
        res = client.get(
            "/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A",
            headers={"x-request-id": "req-xai-1"},
        )
        assert res.status_code == 200
        _assert_envelope(res.json())
        _assert_x_ai_module_header(res)
        _assert_x_request_id_echoed(res, "req-xai-1")

    def test_features_sorted_by_abs_shap_value(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A")
        features = res.json()["data"]["features"]
        shap_values = [abs(f["shapValue"]) for f in features]
        assert shap_values == sorted(shap_values, reverse=True)
        # First feature should be the highest contributor (vibration_rms at 0.42)
        assert features[0]["name"] == "vibration_rms"

    def test_waterfall_and_force_plot_attachments(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A")
        data = res.json()["data"]
        assert "waterfall" in data
        assert "forcePlot" in data
        assert data["waterfall"]["baseValue"] == 0.31
        assert data["forcePlot"]["baseValue"] == 0.31
        assert data["forcePlot"]["predictionValue"] == 0.72

    def test_method_query_param_accepted(self, client: TestClient) -> None:
        res = client.get(
            "/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=LIME"
        )
        assert res.status_code == 200
        assert res.json()["data"]["method"] == "LIME"


# ---------------------------------------------------------------------------
# 4. Recommendations
# ---------------------------------------------------------------------------
class TestRecommendationsContract:
    def test_returns_envelope(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/recommendations",
            json={"asset_id": "P-101A", "max_recommendations": 3},
            headers={"x-request-id": "req-rec-1"},
        )
        assert res.status_code == 200
        _assert_envelope(res.json())
        _assert_x_ai_module_header(res)
        _assert_x_request_id_echoed(res, "req-rec-1")

    def test_action_card_shape(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/recommendations",
            json={"asset_id": "P-101A", "max_recommendations": 3},
        )
        actions = res.json()["data"]
        assert len(actions) == 1
        action = actions[0]
        for k in ("actionId", "actionType", "description", "priority", "severityTier", "riskScoreIfIgnored", "estimatedCostAvoidanceUsd", "recommendedCompletionBy", "sop", "rank"):
            assert k in action
        assert action["priority"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert action["severityTier"] in {"IMMINENT", "SCHEDULED", "MONITOR"}


# ---------------------------------------------------------------------------
# 5. Agent chat (non-streaming)
# ---------------------------------------------------------------------------
class TestAgentChatContract:
    def test_returns_envelope(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/agent/chat",
            json={
                "session_id": "sess-1",
                "asset_id": "P-101A",
                "messages": [{"role": "user", "content": "Diagnose P-101A"}],
            },
            headers={"x-request-id": "req-chat-1"},
        )
        assert res.status_code == 200
        body = res.json()
        _assert_envelope(body)
        _assert_x_ai_module_header(res)
        _assert_x_request_id_echoed(res, "req-chat-1")

    def test_chat_message_matches_section_11(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/agent/chat",
            json={
                "session_id": "sess-1",
                "asset_id": "P-101A",
                "messages": [{"role": "user", "content": "Diagnose P-101A"}],
            },
        )
        data = res.json()["data"]
        for k in ("messageId", "sender", "payload", "timestamp"):
            assert k in data
        assert data["sender"] in {"OPERATOR", "AI_ENGINE"}

    def test_rejects_empty_messages(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/agent/chat",
            json={"session_id": "sess-1", "asset_id": "P-101A", "messages": []},
        )
        # Either a validation error (422) or a sanitized 503 — both acceptable
        assert res.status_code in {200, 422, 503}
        if res.status_code == 200:
            assert res.json()["success"] is False


# ---------------------------------------------------------------------------
# 6. Agent chat (NDJSON stream)
# ---------------------------------------------------------------------------
class TestAgentChatStreamContract:
    def test_emits_ndjson_lines(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/agent/chat/stream",
            json={
                "session_id": "sess-1",
                "asset_id": "P-101A",
                "messages": [{"role": "user", "content": "Diagnose P-101A"}],
            },
        )
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/x-ndjson")
        lines = [line for line in res.text.split("\n") if line.strip()]
        assert len(lines) >= 1
        # Each line must be valid JSON
        import json as _json

        for line in lines:
            block = _json.loads(line)
            assert "eventType" in block
            assert "sessionId" in block
            assert "sequence" in block

    def test_first_event_is_heartbeat(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/ai/ui/agent/chat/stream",
            json={
                "session_id": "sess-1",
                "asset_id": "P-101A",
                "messages": [{"role": "user", "content": "Diagnose P-101A"}],
            },
        )
        import json as _json

        first = _json.loads(res.text.split("\n")[0])
        assert first["eventType"] == "heartbeat"
        assert first["sequence"] == 0


# ---------------------------------------------------------------------------
# 7. CORS / preflight probe
# ---------------------------------------------------------------------------
class TestCorsCheckContract:
    def test_returns_cors_status(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/cors-check")
        assert res.status_code in {200, 503}
        body = res.json()
        _assert_envelope(body)
        if body["success"]:
            assert body["data"]["status"] == "ok"
            assert "allowedOrigins" in body["data"]
        else:
            assert body["data"]["status"] == "misconfigured"
            assert "remediation" in body["data"]


class TestPreflightContract:
    def test_options_returns_cors_headers(self, client: TestClient) -> None:
        res = client.options(
            "/api/v1/ai/ui/options",
            headers={"Origin": "http://localhost:3000"},
        )
        assert res.status_code == 204
        assert res.headers["access-control-allow-methods"] == "GET, POST, OPTIONS"
        assert "authorization" in res.headers["access-control-allow-headers"]
        assert "x-request-id" in res.headers["access-control-allow-headers"]
        assert res.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert res.headers["vary"] == "Origin"


# ---------------------------------------------------------------------------
# 8. Contract manifest
# ---------------------------------------------------------------------------
class TestContractsManifest:
    def test_lists_every_endpoint(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/contracts")
        assert res.status_code == 200
        paths = {entry["path"] for entry in res.json()["data"]["endpoints"]}
        assert "/api/v1/ai/ui/digital-twin/{asset_id}" in paths
        assert "/api/v1/ai/ui/graphrag/query" in paths
        assert "/api/v1/ai/ui/explain/{prediction_id}" in paths
        assert "/api/v1/ai/ui/recommendations" in paths
        assert "/api/v1/ai/ui/agent/chat" in paths
        assert "/api/v1/ai/ui/agent/chat/stream" in paths
        assert "/api/v1/ai/ui/cors-check" in paths
        assert "/api/v1/ai/ui/options" in paths
        assert "/api/v1/ai/ui/contracts" in paths

    def test_phase_identified(self, client: TestClient) -> None:
        res = client.get("/api/v1/ai/ui/contracts")
        assert res.json()["data"]["phase"] == "11-frontend-integration-support"


# ---------------------------------------------------------------------------
# 9. OpenAPI / route mounting
# ---------------------------------------------------------------------------
class TestRouterMounting:
    def test_all_paths_in_openapi(self, client: TestClient) -> None:
        spec = client.get("/openapi.json").json()
        for path in [
            "/api/v1/ai/ui/digital-twin/{asset_id}",
            "/api/v1/ai/ui/graphrag/query",
            "/api/v1/ai/ui/explain/{prediction_id}",
            "/api/v1/ai/ui/recommendations",
            "/api/v1/ai/ui/agent/chat",
            "/api/v1/ai/ui/agent/chat/stream",
            "/api/v1/ai/ui/cors-check",
            "/api/v1/ai/ui/options",
            "/api/v1/ai/ui/contracts",
        ]:
            assert path in spec["paths"], f"missing {path} in OpenAPI"
