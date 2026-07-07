"""Phase 11 — Unit tests for the frontend adapter layer.

These tests assert the **byte-for-byte shape** of the JSON dicts the
adapters produce. They run in pure-Python mode (no FastAPI / network)
so they're fast enough to run on every save and stable enough to gate
Member 4's frontend PRs.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.ai_service.integration.adapters.frontend_adapters import (
    adapt_alert,
    adapt_asset,
    adapt_digital_twin_payload,
    adapt_explainability_payload,
    adapt_graphrag_payload,
    adapt_inference_to_prediction,
    adapt_recommendations_to_actions,
    api_error_to_ui_error,
    build_telemetry_chart_series,
    to_ui_api_envelope,
)
from app.ai_service.integration.schemas.ui_schemas import (
    UIActionPriority,
    UIAsset,
    UIAssetStatus,
    UIGraphRAGPayload,
    UISeverityTier,
    UIShapExplanation,
)

NOW = datetime(2026, 7, 7, 7, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
class _Stub:
    """Generic attribute container used to fake Pydantic models in unit tests."""

    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self, mode: str = "python") -> dict:
        return self.__dict__


@pytest.fixture
def inference_obj() -> _Stub:
    return _Stub(
        asset_id="P-101A",
        component_id="bearing-de",
        explanation_id="pred-p101a-001",
        inference_id=None,
        rul=_Stub(value_days=5.2, lower_bound_days=3.5, upper_bound_days=7.8),
        failure_probability=_Stub(
            probability=0.64,
            failure_mode_id="fm-bearing-wear",
            failure_mode_label="Bearing wear",
        ),
        anomaly_flags=[
            _Stub(
                sensor_id="sns-vib-1",
                metric="vibration_rms",
                anomaly_score=-0.42,
                is_anomalous=True,
                severity="HIGH",
            ),
            _Stub(
                sensor_id="sns-temp-1",
                metric="bearing_temp",
                anomaly_score=-0.15,
                is_anomalous=True,
                severity="MEDIUM",
            ),
        ],
        anomalous_sensors=["sns-vib-1", "sns-temp-1"],
    )


@pytest.fixture
def explanation_obj() -> _Stub:
    return _Stub(
        explanation_id="pred-p101a-001",
        asset_id="P-101A",
        method="SHAP",
        scope="LOCAL",
        base_value=0.31,
        predicted_value=0.72,
        local_feature_importance=[
            _Stub(feature_name="vibration_rms", impact_weight=0.42, feature_value=9.5, rank=1),
            _Stub(feature_name="bearing_temp", impact_weight=0.31, feature_value=82.0, rank=2),
            _Stub(feature_name="rpm", impact_weight=-0.05, feature_value=1480.0, rank=3),
            _Stub(feature_name="pressure", impact_weight=0.02, feature_value=6.4, rank=4),
        ],
        root_cause=_Stub(
            headline="Vibration dominated alert",
            narrative="Elevated vibration is consistent with bearing wear.",
            contributing_failure_modes=["fm-bearing-wear"],
        ),
        confidence_matrix=[_Stub(label="SHAP convergence", confidence=0.95)],
    )


@pytest.fixture
def graphrag_response() -> _Stub:
    return _Stub(
        answer="P-101A shows a likely bearing lubrication issue.",
        context_chunks=[],
        graph_nodes=[
            _Stub(id="asset:P-101A", label="P-101A", type="Asset", properties={}),
            _Stub(
                id="fm:bearing",
                label="Bearing Wear",
                type="FailureMode",
                properties={"status": "active"},
            ),
            _Stub(id="sop:SOP-MECH-042", label="SOP-MECH-042", type="SOP", properties={}),
        ],
        graph_edges=[
            _Stub(
                source="asset:P-101A",
                target="fm:bearing",
                relationship="HAS_FAILURE_MODE",
                weight=1.0,
            ),
            _Stub(
                source="fm:bearing",
                target="sop:SOP-MECH-042",
                relationship="MITIGATED_BY",
                weight=1.0,
            ),
        ],
        citations=[
            _Stub(
                citation_id="cit-1",
                claim_span="vibration at 5.2 mm/s",
                source_document="sop-p101a.pdf",
                source_type="SOP",
                source_node_id="sop:SOP-MECH-042",
                confidence_score=0.91,
            )
        ],
        overall_confidence=0.87,
        vector_hits=3,
    )


@pytest.fixture
def recommendation_response() -> _Stub:
    return _Stub(
        asset_id="P-101A",
        recommendations=[
            _Stub(
                action_id="act-1",
                action_type="INSPECT",
                description="Inspect and lubricate P-101A drive-end bearing.",
                priority="HIGH",
                severity_tier="SCHEDULED",
                risk_score_if_ignored=0.78,
                estimated_cost_avoidance_usd=42000,
                recommended_completion_by=NOW + timedelta(days=2),
                sop_linkage=_Stub(
                    sop_id="SOP-PUMP-BEARING",
                    title="Pump bearing inspection",
                    revision="v2.1",
                    effectiveness=0.82,
                ),
                rank=1,
            )
        ],
        decision_log=[],
        overall_risk_score=0.78,
    )


@pytest.fixture
def history_frames() -> list:
    out = []
    for i in range(24):
        out.append(
            _Stub(
                timestamp=NOW + timedelta(minutes=5 * i),
                readings=[
                    _Stub(metric="rpm", value=1480.0 + i),
                    _Stub(metric="vibration_rms", value=5.2 + 0.1 * i),
                    _Stub(metric="bearing_temp", value=82.0 + i * 0.3),
                    _Stub(metric="pressure", value=6.4),
                    _Stub(metric="flow_rate", value=240.0),
                    _Stub(metric="load_kw", value=312.0),
                ],
            )
        )
    return out


# ---------------------------------------------------------------------------
# 1. adapt_inference_to_prediction — Section 11 Prediction shape
# ---------------------------------------------------------------------------
class TestAdaptInferenceToPrediction:
    def test_returns_section_11_keys(self, inference_obj: _Stub) -> None:
        out = adapt_inference_to_prediction(inference_obj)
        assert set(out.keys()) == {
            "id",
            "assetId",
            "remainingUsefulLifeDays",
            "failureProbability",
            "inferredFaultMechanism",
        }
        assert out["id"] == "pred-p101a-001"
        assert out["assetId"] == "P-101A"
        assert out["remainingUsefulLifeDays"] == 5.2
        assert out["failureProbability"] == 0.64
        assert out["inferredFaultMechanism"] == "Bearing wear"

    def test_generates_stable_id_when_explanation_id_missing(self) -> None:
        inference = _Stub(
            asset_id="P-101A",
            explanation_id=None,
            inference_id=None,
            rul=_Stub(value_days=4.0),
            failure_probability=_Stub(probability=0.2, failure_mode_label="Routine"),
            anomaly_flags=[],
            anomalous_sensors=[],
        )
        out = adapt_inference_to_prediction(inference)
        assert out["id"].startswith("pred-")
        assert out["inferredFaultMechanism"] == "Routine"

    def test_falls_back_to_anomaly_label_when_no_failure_mode(self) -> None:
        inference = _Stub(
            asset_id="P-101A",
            explanation_id="pred-x",
            inference_id=None,
            rul=_Stub(value_days=4.0),
            failure_probability=_Stub(probability=0.2, failure_mode_label=None, failure_mode_id=None),
            anomaly_flags=[
                _Stub(metric="vibration_rms", anomaly_score=-0.1, is_anomalous=True, severity="LOW"),
            ],
            anomalous_sensors=[],
        )
        out = adapt_inference_to_prediction(inference)
        assert "vibration" in out["inferredFaultMechanism"].lower()


# ---------------------------------------------------------------------------
# 2. adapt_graphrag_payload — GraphRagPanel shape
# ---------------------------------------------------------------------------
class TestAdaptGraphRagPayload:
    def test_returns_panel_shape(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="Why is P-101A vibrating?")
        # Validate against the strict Pydantic model
        UIGraphRAGPayload.model_validate(out)
        assert out["answer"] == "P-101A shows a likely bearing lubrication issue."
        assert any("vibrating" in log for log in out["logs"])
        assert any("3 chunks" in log for log in out["logs"])
        assert any("Synthesizing" in log for log in out["logs"])

    def test_nodes_have_deterministic_layout(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="q")
        for node in out["nodes"]:
            assert "x" in node and "y" in node
            assert isinstance(node["x"], (int, float))
            assert isinstance(node["y"], (int, float))
        # Asset nodes are in the left column
        asset_nodes = [n for n in out["nodes"] if n["type"] == "asset"]
        for n in asset_nodes:
            assert n["x"] == 60.0

    def test_node_type_vocabulary_matches_panel(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="q")
        valid_types = {"asset", "component", "anomaly", "procedure", "record"}
        for node in out["nodes"]:
            assert node["type"] in valid_types

    def test_failure_mode_maps_to_anomaly_type(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="q")
        anomaly_nodes = [n for n in out["nodes"] if n["type"] == "anomaly"]
        assert any(n["id"] == "fm:bearing" for n in anomaly_nodes)

    def test_sop_maps_to_procedure_type(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="q")
        procedure_nodes = [n for n in out["nodes"] if n["type"] == "procedure"]
        assert any(n["id"] == "sop:SOP-MECH-042" for n in procedure_nodes)

    def test_highlighted_node_ids_are_strings(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="q")
        for nid in out["highlightedNodes"]:
            assert isinstance(nid, str)
        for eid in out["highlightedEdges"]:
            assert isinstance(eid, str)

    def test_handles_empty_graph(self) -> None:
        empty = _Stub(
            answer="",
            context_chunks=[],
            graph_nodes=[],
            graph_edges=[],
            citations=[],
            overall_confidence=0.0,
            vector_hits=0,
        )
        out = adapt_graphrag_payload(empty, query="q")
        assert out["nodes"] == []
        assert out["edges"] == []
        assert out["answer"] == ""
        # logs are still populated so the panel's loading strip animates
        assert len(out["logs"]) >= 1

    def test_logs_always_start_with_vector_search_line(self, graphrag_response: _Stub) -> None:
        out = adapt_graphrag_payload(graphrag_response, query="why?")
        assert out["logs"][0].startswith("Vector search initiated")


# ---------------------------------------------------------------------------
# 3. adapt_digital_twin_payload — DigitalTwinView shape
# ---------------------------------------------------------------------------
class TestAdaptDigitalTwinPayload:
    def test_returns_required_top_level_keys(
        self, history_frames: list, inference_obj: _Stub
    ) -> None:
        asset = UIAsset(
            id="P-101A",
            name="Pump 101A",
            type="PUMP",
            status=UIAssetStatus.OPERATIONAL,
            parentId=None,
        )
        out = adapt_digital_twin_payload(
            asset=asset, inference=inference_obj, history=history_frames
        )
        assert "asset" in out
        assert "telemetry" in out
        assert "history" in out
        assert "activeAnomaly" in out
        assert out["activeAnomaly"] == "bearing-wear"

    def test_telemetry_keys_match_panel_destructuring(
        self, history_frames: list, inference_obj: _Stub
    ) -> None:
        asset = UIAsset(
            id="P-101A", name="P-101A", type="PUMP", status=UIAssetStatus.OPERATIONAL
        )
        out = adapt_digital_twin_payload(
            asset=asset, inference=inference_obj, history=history_frames
        )
        tel = out["telemetry"]
        expected = {"speed", "vibration", "pressure", "temperature", "flowRate", "load", "riskScore", "status"}
        assert expected.issubset(set(tel.keys()))
        assert tel["status"] in {"ok", "warning", "critical", "offline"}
        assert 0.0 <= tel["riskScore"] <= 100.0

    def test_risk_score_is_failure_probability_times_100(
        self, history_frames: list, inference_obj: _Stub
    ) -> None:
        asset = UIAsset(
            id="P-101A", name="P-101A", type="PUMP", status=UIAssetStatus.OPERATIONAL
        )
        out = adapt_digital_twin_payload(
            asset=asset, inference=inference_obj, history=history_frames
        )
        assert out["telemetry"]["riskScore"] == 64.0

    def test_high_anomaly_severity_drives_critical_status(
        self, history_frames: list
    ) -> None:
        inference = _Stub(
            asset_id="P-101A",
            explanation_id="pred-x",
            rul=_Stub(value_days=5.0),
            failure_probability=_Stub(probability=0.95, failure_mode_id="fm-x", failure_mode_label="Trip"),
            anomaly_flags=[
                _Stub(
                    sensor_id="sns-1",
                    metric="vibration_rms",
                    anomaly_score=-0.5,
                    is_anomalous=True,
                    severity="CRITICAL",
                )
            ],
            anomalous_sensors=["sns-1"],
        )
        asset = UIAsset(
            id="P-101A", name="P-101A", type="PUMP", status=UIAssetStatus.OPERATIONAL
        )
        out = adapt_digital_twin_payload(
            asset=asset, inference=inference, history=history_frames
        )
        assert out["telemetry"]["status"] == "critical"
        assert out["activeAnomaly"] in {"bearing-wear", "electrical-trip"}

    def test_offline_asset_status_drives_offline_telemetry(self) -> None:
        asset = UIAsset(
            id="P-101A",
            name="P-101A",
            type="PUMP",
            status=UIAssetStatus.OFFLINE,
        )
        out = adapt_digital_twin_payload(asset=asset, history=[])
        assert out["telemetry"]["status"] == "offline"

    def test_history_has_one_frame_per_input(
        self, history_frames: list, inference_obj: _Stub
    ) -> None:
        asset = UIAsset(
            id="P-101A", name="P-101A", type="PUMP", status=UIAssetStatus.OPERATIONAL
        )
        out = adapt_digital_twin_payload(
            asset=asset, inference=inference_obj, history=history_frames
        )
        assert len(out["history"]) == len(history_frames)
        for frame in out["history"]:
            assert "timestamp" in frame
            assert "speed" in frame
            assert "vibration" in frame
            assert "pressure" in frame
            assert "temperature" in frame
            assert "flowRate" in frame
            assert "load" in frame
            assert "riskScore" in frame

    def test_dominant_anomaly_uses_failure_mode_label(self) -> None:
        inference = _Stub(
            asset_id="C-204",
            explanation_id="x",
            rul=_Stub(value_days=10.0),
            failure_probability=_Stub(
                probability=0.6,
                failure_mode_id="fm-surge",
                failure_mode_label="Compressor surge",
            ),
            anomaly_flags=[],
            anomalous_sensors=[],
        )
        asset = UIAsset(
            id="C-204", name="C-204", type="COMPRESSOR", status=UIAssetStatus.DEGRADED
        )
        out = adapt_digital_twin_payload(asset=asset, inference=inference, history=[])
        assert out["activeAnomaly"] == "compressor-surge"

    def test_handles_nan_in_history(self) -> None:
        bad_frame = _Stub(
            timestamp=NOW,
            readings=[
                _Stub(metric="rpm", value=float("nan")),
                _Stub(metric="vibration_rms", value=float("inf")),
            ],
        )
        asset = UIAsset(
            id="P-101A", name="P-101A", type="PUMP", status=UIAssetStatus.OPERATIONAL
        )
        out = adapt_digital_twin_payload(asset=asset, history=[bad_frame])
        # NaN/Inf must be coerced to 0 so the chart library doesn't crash
        assert not math.isnan(out["telemetry"]["speed"])
        assert not math.isinf(out["telemetry"]["speed"])


# ---------------------------------------------------------------------------
# 4. build_telemetry_chart_series — Recharts/Chart.js shape
# ---------------------------------------------------------------------------
class TestBuildTelemetryChartSeries:
    def test_returns_xy_points(self, history_frames: list) -> None:
        series = build_telemetry_chart_series(history_frames, metric_key="vibration_rms")
        assert len(series) == len(history_frames)
        for p in series:
            assert "x" in p
            assert "y" in p
            assert isinstance(p["x"], str)
            assert isinstance(p["y"], (int, float))


# ---------------------------------------------------------------------------
# 5. adapt_explainability_payload — ShapExplainability shape
# ---------------------------------------------------------------------------
class TestAdaptExplainabilityPayload:
    def test_features_sorted_by_abs_shap_value_desc(self, explanation_obj: _Stub) -> None:
        out = adapt_explainability_payload(
            explanation=explanation_obj, prediction_id="pred-p101a-001", asset_id="P-101A"
        )
        UIShapExplanation.model_validate(out)
        shap_values = [abs(f["shapValue"]) for f in out["features"]]
        assert shap_values == sorted(shap_values, reverse=True)
        # vibration_rms has the highest |impact_weight| (0.42)
        assert out["features"][0]["name"] == "vibration_rms"

    def test_required_keys_present(self, explanation_obj: _Stub) -> None:
        out = adapt_explainability_payload(
            explanation=explanation_obj, prediction_id="pred-p101a-001", asset_id="P-101A"
        )
        for key in (
            "predictionId",
            "assetId",
            "method",
            "scope",
            "baseValue",
            "predictionValue",
            "features",
            "confidenceMatrix",
            "rootCause",
        ):
            assert key in out

    def test_feature_shape_matches_panel(self, explanation_obj: _Stub) -> None:
        out = adapt_explainability_payload(
            explanation=explanation_obj, prediction_id="pred-p101a-001", asset_id="P-101A"
        )
        for feature in out["features"]:
            assert set(feature.keys()) == {"name", "value", "shapValue", "desc"}

    def test_units_appear_in_value_string(self, explanation_obj: _Stub) -> None:
        out = adapt_explainability_payload(
            explanation=explanation_obj, prediction_id="pred-p101a-001", asset_id="P-101A"
        )
        value_map = {f["name"]: f["value"] for f in out["features"]}
        assert "mm/s" in value_map["vibration_rms"]
        assert "°C" in value_map["bearing_temp"]
        assert "RPM" in value_map["rpm"]


# ---------------------------------------------------------------------------
# 6. adapt_recommendations_to_actions
# ---------------------------------------------------------------------------
class TestAdaptRecommendationsToActions:
    def test_action_card_keys(self, recommendation_response: _Stub) -> None:
        cards = adapt_recommendations_to_actions(recommendation_response)
        assert len(cards) == 1
        card = cards[0]
        expected = {
            "actionId",
            "actionType",
            "description",
            "priority",
            "severityTier",
            "riskScoreIfIgnored",
            "estimatedCostAvoidanceUsd",
            "recommendedCompletionBy",
            "sop",
            "rank",
        }
        assert expected.issubset(set(card.keys()))
        assert card["priority"] == UIActionPriority.HIGH.value
        assert card["severityTier"] == UISeverityTier.SCHEDULED.value

    def test_sop_linkage_flattened(self, recommendation_response: _Stub) -> None:
        cards = adapt_recommendations_to_actions(recommendation_response)
        assert cards[0]["sop"] is not None
        assert cards[0]["sop"]["sopId"] == "SOP-PUMP-BEARING"
        assert cards[0]["sop"]["title"] == "Pump bearing inspection"

    def test_empty_recommendations(self) -> None:
        empty = _Stub(recommendations=[], decision_log=[], overall_risk_score=0.0)
        assert adapt_recommendations_to_actions(empty) == []


# ---------------------------------------------------------------------------
# 7. UI envelope helpers
# ---------------------------------------------------------------------------
class TestUIEnvelope:
    def test_envelope_shape(self) -> None:
        env = to_ui_api_envelope(success=True, data={"foo": "bar"}, request_id="req-1")
        assert env["success"] is True
        assert env["data"] == {"foo": "bar"}
        assert env["requestId"] == "req-1"
        assert "generatedAt" in env
        assert env["error"] is None

    def test_envelope_coerces_string_error(self) -> None:
        env = to_ui_api_envelope(
            success=False,
            data=None,
            request_id="req-1",
            error="something went wrong",
        )
        assert env["error"]["code"] == "AI_SERVICE_ERROR"
        assert env["error"]["message"] == "something went wrong"
        assert env["error"]["details"] is None

    def test_api_error_to_ui_error(self) -> None:
        err = api_error_to_ui_error(
            error_code="AI_DEPENDENCY_UNAVAILABLE",
            message="backend down",
            details={"engine": "graphrag"},
        )
        assert err["code"] == "AI_DEPENDENCY_UNAVAILABLE"
        assert err["message"] == "backend down"
        assert err["details"] == {"engine": "graphrag"}


# ---------------------------------------------------------------------------
# 8. Asset / alert helpers
# ---------------------------------------------------------------------------
class TestAssetAlertHelpers:
    def test_adapt_asset(self) -> None:
        a = _Stub(id="P-101A", name="Pump 101A", type="PUMP", status="OPERATIONAL", parentId=None)
        out = adapt_asset(a)
        assert out["id"] == "P-101A"
        assert out["status"] == "OPERATIONAL"
        assert out["parentId"] is None

    def test_adapt_asset_falls_back_to_id_for_name(self) -> None:
        a = _Stub(id="P-101A", name=None, type="PUMP", status="OPERATIONAL")
        out = adapt_asset(a)
        assert out["name"] == "P-101A"

    def test_adapt_alert(self) -> None:
        a = _Stub(
            id="al-1",
            asset_id="P-101A",
            severity="CRITICAL",
            message="Bearing temperature exceeded threshold.",
            timestamp=NOW,
            acknowledged=False,
        )
        out = adapt_alert(a)
        assert out["assetId"] == "P-101A"
        assert out["severity"] == "CRITICAL"
        assert out["acknowledged"] is False
        assert "timestamp" in out
