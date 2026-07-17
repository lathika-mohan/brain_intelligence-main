"""
Phase 8 — AI Decision Engine test suite.

Covers (all offline — no live Neo4j required; the graph layer degrades to
its documented fallback paths when no driver is connected):

  1. Rule Engine — severity classification matrix edge cases (negative RUL,
     simultaneous multi-sensor failures, probability force-escalation,
     ontology floor rules), asset-criticality weighting, prioritization.
  2. Risk Scorer — RPN = P x S x D equation correctness, detectability
     inverse-proportionality, cost-of-inaction modelling.
  3. SOP Matcher — pure Cypher query builder, record-to-payload mapping,
     offline fallback catalogue completeness (steps/tools/hazards/PPE).
  4. Decision Service — end-to-end orchestration from a mock
     prediction/explanation packet to a fully-formed prescriptive decision
     object, including graceful degradation when Phase 6/7 fail.
  5. Contract conformance — the exact frontend/API JSON signature via the
     FastAPI TestClient, matching ``docs/api_contracts.md`` §4.

Run:  pytest tests/test_phase8_decision.py -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.decision.risk_scorer import (
    RiskScorer,
    detectability_from_anomaly_confidence,
    probability_to_scale,
    severity_from_ontology,
)
from app.decision.rule_engine import (
    CRITICALITY_WEIGHTS,
    PredictionSignal,
    RuleEngine,
    asset_criticality_weight,
    classify_severity,
    failure_mode_severity_boost,
)
from app.decision.sop_matcher import (
    SopMatcher,
    build_sop_lookup_query,
    records_to_sop_bundle,
)
from app.decision.decision_service import DecisionService
from app.models.decision import (
    MaintenanceActionType,
    PriorityLevel,
    RecommendationRequest,
    RecommendationResponse,
    SeverityTier,
)


# ===========================================================================
# 1. Rule Engine — severity classification
# ===========================================================================


class TestSeverityClassification:
    def test_negative_rul_is_always_imminent(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=-5.0, failure_probability=0.1)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.IMMINENT
        fired = {r.rule_name for r in result.triggered_rules if r.fired}
        assert "rul_elapsed_or_negative" in fired

    def test_zero_rul_is_imminent(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=0.0, failure_probability=0.0)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.IMMINENT

    def test_healthy_asset_is_monitor(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=90.0, failure_probability=0.02)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.MONITOR

    def test_rul_within_imminent_window(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=2.0, failure_probability=0.1)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.IMMINENT

    def test_rul_within_scheduled_window(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=10.0, failure_probability=0.1)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.SCHEDULED

    def test_high_failure_probability_forces_imminent_despite_long_rul(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=90.0, failure_probability=0.9)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.IMMINENT
        fired = {r.rule_name for r in result.triggered_rules if r.fired}
        assert "failure_probability_force_imminent" in fired

    def test_moderate_failure_probability_forces_scheduled(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=90.0, failure_probability=0.5)
        result = classify_severity(signal)
        assert result.tier == SeverityTier.SCHEDULED

    def test_simultaneous_multi_sensor_failure_escalates_from_monitor(self):
        signal = PredictionSignal(
            asset_id="asset-1",
            rul_days=90.0,
            failure_probability=0.05,
            anomalous_sensors=["sensor-a", "sensor-b"],
        )
        result = classify_severity(signal)
        assert result.tier == SeverityTier.SCHEDULED
        fired = {r.rule_name for r in result.triggered_rules if r.fired}
        assert "simultaneous_multi_sensor_failure" in fired

    def test_single_sensor_anomaly_does_not_trigger_multisensor_rule(self):
        signal = PredictionSignal(
            asset_id="asset-1",
            rul_days=90.0,
            failure_probability=0.02,
            anomalous_sensors=["sensor-a"],
        )
        result = classify_severity(signal)
        fired = {r.rule_name for r in result.triggered_rules if r.fired}
        assert "simultaneous_multi_sensor_failure" not in fired
        assert result.tier == SeverityTier.MONITOR

    def test_high_intensity_anomaly_escalates_monitor_to_scheduled(self):
        signal = PredictionSignal(
            asset_id="asset-1",
            rul_days=90.0,
            failure_probability=0.05,
            is_anomalous=True,
            anomaly_score=-0.4,  # intensity = min(0.4/0.5, 1.0) = 0.8 >= 0.6
        )
        result = classify_severity(signal)
        assert result.tier == SeverityTier.SCHEDULED

    def test_ontology_critical_failure_mode_is_hard_floor(self):
        signal = PredictionSignal(
            asset_id="asset-1",
            rul_days=90.0,
            failure_probability=0.01,
            failure_mode_severity_tier="CRITICAL",
        )
        result = classify_severity(signal)
        assert result.tier == SeverityTier.IMMINENT
        fired = {r.rule_name for r in result.triggered_rules if r.fired}
        assert "ontology_failure_mode_critical_floor" in fired

    def test_every_rule_is_recorded_regardless_of_outcome(self):
        signal = PredictionSignal(asset_id="asset-1", rul_days=90.0, failure_probability=0.02)
        result = classify_severity(signal)
        # All 8 rules must be present in the audit trail even when they don't fire.
        assert len(result.triggered_rules) == 8

    def test_escalation_score_is_bounded_and_monotonic_with_probability(self):
        low = classify_severity(PredictionSignal(asset_id="a", rul_days=50.0, failure_probability=0.05))
        high = classify_severity(PredictionSignal(asset_id="a", rul_days=50.0, failure_probability=0.6))
        assert 0.0 <= low.escalation_score <= 1.0
        assert 0.0 <= high.escalation_score <= 1.0
        assert high.escalation_score > low.escalation_score

    def test_anomaly_intensity_zero_when_not_anomalous(self):
        signal = PredictionSignal(asset_id="a", anomaly_score=-0.5, is_anomalous=False)
        assert signal.anomaly_intensity() == 0.0

    def test_anomaly_intensity_clamped_at_one(self):
        signal = PredictionSignal(asset_id="a", anomaly_score=-5.0, is_anomalous=True)
        assert signal.anomaly_intensity() == 1.0


class TestCriticalityWeighting:
    def test_known_tiers_map_to_expected_weights(self):
        assert asset_criticality_weight("A") == CRITICALITY_WEIGHTS["A"]
        assert asset_criticality_weight("B") == CRITICALITY_WEIGHTS["B"]
        assert asset_criticality_weight("C") == CRITICALITY_WEIGHTS["C"]

    def test_bottleneck_outweighs_backup(self):
        assert asset_criticality_weight("A") > asset_criticality_weight("C")

    def test_unknown_or_missing_tier_falls_back_to_default(self):
        from app.core.config import get_settings

        default = get_settings().decision_engine_default_criticality_weight
        assert asset_criticality_weight(None) == default
        assert asset_criticality_weight("unknown-tier") == default

    def test_case_insensitive_lookup(self):
        assert asset_criticality_weight("a") == CRITICALITY_WEIGHTS["A"]

    def test_failure_mode_severity_boost_ordering(self):
        assert failure_mode_severity_boost("CRITICAL") > failure_mode_severity_boost("DEGRADED")
        assert failure_mode_severity_boost("DEGRADED") > failure_mode_severity_boost("INCIPIENT")
        assert failure_mode_severity_boost(None) == 0.0


class TestPrioritization:
    def test_bottleneck_asset_outranks_backup_with_identical_failure_profile(self):
        engine = RuleEngine()
        signal_a = PredictionSignal(asset_id="pump-primary", rul_days=2.0, failure_probability=0.8)
        signal_b = PredictionSignal(asset_id="pump-backup", rul_days=2.0, failure_probability=0.8)
        cls_a = engine.classify(signal_a)
        cls_b = engine.classify(signal_b)
        weight_a = engine.criticality_weight("A")
        weight_b = engine.criticality_weight("C")
        ordered = engine.prioritize(
            [("pump-backup", cls_b, weight_b), ("pump-primary", cls_a, weight_a)]
        )
        assert ordered[0] == "pump-primary"

    def test_imminent_always_outranks_scheduled_regardless_of_weight(self):
        engine = RuleEngine()
        imminent = engine.classify(PredictionSignal(asset_id="x", rul_days=1.0, failure_probability=0.9))
        scheduled = engine.classify(PredictionSignal(asset_id="y", rul_days=10.0, failure_probability=0.5))
        ordered = engine.prioritize(
            [("y", scheduled, CRITICALITY_WEIGHTS["A"]), ("x", imminent, CRITICALITY_WEIGHTS["C"])]
        )
        assert ordered[0] == "x"


# ===========================================================================
# 2. Risk Scorer — RPN = P x S x D
# ===========================================================================


class TestRiskScorer:
    def test_probability_scale_boundaries(self):
        assert probability_to_scale(0.0) == pytest.approx(1.0)
        assert probability_to_scale(1.0) == pytest.approx(10.0)
        assert probability_to_scale(0.5) == pytest.approx(5.5)

    def test_probability_scale_clamps_out_of_range_inputs(self):
        assert probability_to_scale(-0.5) == pytest.approx(1.0)
        assert probability_to_scale(1.5) == pytest.approx(10.0)

    def test_severity_from_ontology_uses_tier_first(self):
        assert severity_from_ontology("CRITICAL", None) == 9.0
        assert severity_from_ontology("DEGRADED", None) == 6.0
        assert severity_from_ontology("INCIPIENT", None) == 3.0

    def test_severity_from_ontology_falls_back_to_rpn_hint(self):
        assert severity_from_ontology(None, 700.0) == pytest.approx(7.0)

    def test_severity_from_ontology_default_when_nothing_available(self):
        assert severity_from_ontology(None, None) == 5.0

    def test_detectability_is_inversely_proportional_to_confidence(self):
        low_conf = detectability_from_anomaly_confidence(0.1)
        high_conf = detectability_from_anomaly_confidence(0.9)
        assert low_conf > high_conf  # low detection confidence -> harder to detect -> higher score

    def test_detectability_boundaries(self):
        assert detectability_from_anomaly_confidence(1.0) == pytest.approx(1.0)
        assert detectability_from_anomaly_confidence(0.0) == pytest.approx(10.0)

    def test_rpn_equation_matches_p_times_s_times_d(self):
        scorer = RiskScorer()
        breakdown = scorer.score(
            probability_of_failure=0.5,
            severity_tier="CRITICAL",
            risk_priority_number_hint=None,
            anomaly_confidence=0.8,
            criticality_weight=1.0,
        )
        expected_p = probability_to_scale(0.5)
        expected_s = 9.0
        expected_d = detectability_from_anomaly_confidence(0.8)
        expected_rpn = expected_p * expected_s * expected_d
        assert breakdown.risk_priority_number == pytest.approx(expected_rpn, rel=1e-6)

    def test_higher_criticality_weight_increases_weighted_rpn(self):
        scorer = RiskScorer()
        low_weight = scorer.score(
            probability_of_failure=0.5,
            severity_tier="DEGRADED",
            risk_priority_number_hint=None,
            anomaly_confidence=0.5,
            criticality_weight=0.85,
        )
        high_weight = scorer.score(
            probability_of_failure=0.5,
            severity_tier="DEGRADED",
            risk_priority_number_hint=None,
            anomaly_confidence=0.5,
            criticality_weight=1.5,
        )
        assert high_weight.risk_priority_number > low_weight.risk_priority_number

    def test_normalized_risk_score_bounded(self):
        scorer = RiskScorer()
        breakdown = scorer.score(
            probability_of_failure=1.0,
            severity_tier="CRITICAL",
            risk_priority_number_hint=None,
            anomaly_confidence=1.0,
            criticality_weight=1.5,
        )
        assert 0.0 <= breakdown.normalized_risk_score <= 1.0

    def test_zero_probability_and_low_severity_yields_low_risk(self):
        scorer = RiskScorer()
        breakdown = scorer.score(
            probability_of_failure=0.0,
            severity_tier="INCIPIENT",
            risk_priority_number_hint=None,
            anomaly_confidence=0.0,
            criticality_weight=0.85,
        )
        assert breakdown.normalized_risk_score < 0.05

    def test_cost_of_inaction_avoidance_is_non_negative(self):
        scorer = RiskScorer()
        cost = scorer.estimate_cost(risk_score=0.7)
        assert cost.estimated_cost_avoidance_usd >= 0.0
        assert cost.unplanned_downtime_cost_usd >= cost.planned_maintenance_cost_usd

    def test_cost_scales_with_risk_score(self):
        scorer = RiskScorer()
        low_risk_cost = scorer.estimate_cost(risk_score=0.1)
        high_risk_cost = scorer.estimate_cost(risk_score=0.9)
        assert high_risk_cost.unplanned_downtime_cost_usd > low_risk_cost.unplanned_downtime_cost_usd


# ===========================================================================
# 3. SOP Matcher — query builder + fallback catalogue
# ===========================================================================


class TestSopMatcherQueryBuilder:
    def test_query_builder_is_pure_and_parametrized(self):
        cypher, params = build_sop_lookup_query("failuremode-bearing-overheat", max_sops=2)
        assert "MITIGATED_BY" in cypher
        assert "$failure_mode_id" in cypher
        assert params["failure_mode_id"] == "failuremode-bearing-overheat"
        assert params["limit"] == 50

    def test_records_to_bundle_groups_by_sop_and_orders_by_effectiveness(self):
        records = [
            {
                "sop": {"id": "sop-1", "title": "Low Effectiveness SOP", "revision": "A"},
                "mitigation": {"effectiveness": 0.4},
                "step": {"sequence_number": 1, "instruction": "Step one"},
                "tools": ["Wrench"],
                "hazards": ["Pinch point"],
                "ppe_lists": [["Gloves"]],
            },
            {
                "sop": {"id": "sop-2", "title": "High Effectiveness SOP", "revision": "B"},
                "mitigation": {"effectiveness": 0.9},
                "step": {"sequence_number": 1, "instruction": "Verify isolation"},
                "tools": [],
                "hazards": [],
                "ppe_lists": [],
            },
        ]
        linkages, steps = records_to_sop_bundle(records, max_sops=3)
        assert [l.sop_id for l in linkages] == ["sop-2", "sop-1"]
        assert steps[0].sop_id == "sop-2"

    def test_records_to_bundle_respects_max_sops_cap(self):
        records = [
            {
                "sop": {"id": f"sop-{i}", "title": f"SOP {i}"},
                "mitigation": {"effectiveness": 0.5 + i * 0.01},
                "step": None,
                "tools": [],
                "hazards": [],
                "ppe_lists": [],
            }
            for i in range(5)
        ]
        linkages, _ = records_to_sop_bundle(records, max_sops=2)
        assert len(linkages) == 2

    def test_empty_records_yields_empty_bundle(self):
        linkages, steps = records_to_sop_bundle([], max_sops=3)
        assert linkages == []
        assert steps == []


@pytest.mark.asyncio
class TestSopMatcherFallback:
    async def test_fallback_used_when_no_graph_available(self):
        matcher = SopMatcher()
        linkages, steps, used_graph = await matcher.find_sops_for_failure_mode(
            "failuremode-bearing-overheat"
        )
        assert used_graph is False
        assert len(linkages) == 1
        assert linkages[0].sop_id == "sop:SOP-114:REV-C"
        assert len(steps) >= 3
        # Safety-critical SOPs must include at least one hazard-linked step.
        assert any(step.hazards for step in steps)
        assert any(step.hold_point for step in steps)

    async def test_fallback_for_unknown_failure_mode_uses_general_catalogue(self):
        matcher = SopMatcher()
        linkages, steps, used_graph = await matcher.find_sops_for_failure_mode("failuremode-totally-unknown")
        assert used_graph is False
        assert linkages[0].sop_id == "sop:SOP-200:REV-A"

    async def test_fallback_for_none_failure_mode_id(self):
        matcher = SopMatcher()
        linkages, steps, used_graph = await matcher.find_sops_for_failure_mode(None)
        assert used_graph is False
        assert len(linkages) == 1


# ===========================================================================
# 4. Decision Service — end-to-end orchestration (offline / mocked)
# ===========================================================================


@pytest.mark.asyncio
class TestDecisionServiceIntegration:
    async def test_end_to_end_decision_for_healthy_asset(self):
        service = DecisionService()
        request = RecommendationRequest(asset_id="asset-101", risk_horizon_days=30, max_recommendations=3)
        response = await service.recommend(request)

        assert isinstance(response, RecommendationResponse)
        assert response.asset_id == "asset-101"
        assert len(response.recommendations) >= 1
        assert len(response.decision_log) == 1
        assert response.decision_log[0].asset_id == "asset-101"
        assert 0.0 <= response.overall_risk_score <= 1.0

    async def test_recommendations_are_capped_at_max_recommendations(self):
        service = DecisionService()
        request = RecommendationRequest(asset_id="asset-101", max_recommendations=1)
        response = await service.recommend(request)
        assert len(response.recommendations) <= 1

    async def test_decision_log_captures_triggered_rules_and_risk_breakdown(self):
        service = DecisionService()
        request = RecommendationRequest(asset_id="asset-202")
        response = await service.recommend(request)
        log = response.decision_log[0]
        assert len(log.triggered_rules) == 8
        assert log.risk_breakdown.risk_priority_number >= 0.0
        assert log.cost_estimate.estimated_cost_avoidance_usd >= 0.0
        assert "criticality_weight" in log.weights_applied

    async def test_recommendation_has_valid_action_type_and_priority(self):
        service = DecisionService()
        request = RecommendationRequest(asset_id="asset-303")
        response = await service.recommend(request)
        for rec in response.recommendations:
            assert isinstance(rec.action_type, MaintenanceActionType)
            assert isinstance(rec.priority, PriorityLevel)
            assert rec.recommended_completion_by is not None

    async def test_sop_steps_are_populated_and_reference_a_recommendation_sop(self):
        service = DecisionService()
        request = RecommendationRequest(asset_id="asset-404")
        response = await service.recommend(request)
        sop_ids_in_recs = {
            rec.sop_linkage.sop_id for rec in response.recommendations if rec.sop_linkage is not None
        }
        sop_ids_in_steps = {step.sop_id for step in response.sop_steps}
        # Every SOP referenced by a recommendation must have matching steps.
        assert sop_ids_in_recs.issubset(sop_ids_in_steps) or not sop_ids_in_recs


# ===========================================================================
# 5. API contract conformance
# ===========================================================================


class TestDecisionApi:
    @pytest.fixture()
    def client(self) -> TestClient:
        from app.main import app as fastapi_app

        return TestClient(fastapi_app)

    def test_recommend_endpoint_returns_wrapped_contract_payload(self, client: TestClient):
        res = client.post(
            "/api/v1/decision/recommend",
            json={"asset_id": "asset-101", "risk_horizon_days": 30, "max_recommendations": 3},
        )
        assert res.status_code == 200
        envelope = res.json()
        assert envelope["success"] is True
        assert envelope["error"] is None
        data = envelope["data"]
        assert data["asset_id"] == "asset-101"
        assert "recommendations" in data
        assert "sop_steps" in data
        assert "decision_log" in data
        assert "overall_risk_score" in data

    def test_recommend_response_matches_frozen_recommendation_field_set(self, client: TestClient):
        res = client.post("/api/v1/decision/recommend", json={"asset_id": "asset-101"})
        data = res.json()["data"]
        for rec in data["recommendations"]:
            assert {
                "action_id",
                "action_type",
                "description",
                "priority",
                "risk_score_if_ignored",
                "estimated_cost_avoidance_usd",
                "recommended_completion_by",
                "sop_linkage",
                "supporting_explanation_id",
                "severity_tier",
                "rank",
            }.issubset(set(rec.keys()))

    def test_recommend_defaults_are_applied(self, client: TestClient):
        res = client.post("/api/v1/decision/recommend", json={"asset_id": "asset-999"})
        assert res.status_code == 200

    def test_recommend_rejects_missing_asset_id(self, client: TestClient):
        res = client.post("/api/v1/decision/recommend", json={})
        assert res.status_code == 422

    def test_recommend_rejects_out_of_range_horizon(self, client: TestClient):
        res = client.post(
            "/api/v1/decision/recommend", json={"asset_id": "asset-101", "risk_horizon_days": 0}
        )
        assert res.status_code == 422

    def test_recommend_rejects_extra_fields(self, client: TestClient):
        res = client.post(
            "/api/v1/decision/recommend", json={"asset_id": "asset-101", "hacker_field": "x"}
        )
        assert res.status_code == 422

    def test_health_endpoint_reports_configuration(self, client: TestClient):
        res = client.get("/api/v1/decision/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ready"
        assert "criticality_weights" in body
        assert "severity_thresholds_days" in body
