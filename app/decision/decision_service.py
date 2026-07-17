"""
Phase 8 — AI Decision Engine orchestrator.

Wires together:

  * Phase 6 :class:`~app.predictive.prediction_service.PredictionService`
    (RUL, failure probability, anomaly flags)
  * Phase 7 :class:`~app.predictive.xai_service.XaiService`
    (top root-cause sensors, root-cause narrative)
  * Phase 2 Neo4j graph (asset criticality, failure-mode severity, SOPs)
  * :mod:`app.decision.rule_engine` (severity classification + prioritization)
  * :mod:`app.decision.risk_scorer` (RPN = P x S x D + cost-of-inaction)
  * :mod:`app.decision.sop_matcher` (graph-driven SOP retrieval)

into the frozen ``RecommendationResponse`` contract (``app/models/decision.py``,
``docs/api_contracts.md`` §4) consumed by ``POST /api/v1/decision/recommend``.

The orchestrator degrades gracefully at every external boundary (Neo4j down,
model artifacts missing, XAI computation failing) — it never raises for a
downstream dependency outage, it just falls back to conservative defaults
and records the degradation in the ``decision_log`` so operators can see
*why* a recommendation might be less confident than usual.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.decision.risk_scorer import RiskScorer
from app.decision.rule_engine import PredictionSignal, RuleEngine, SeverityClassification
from app.decision.sop_matcher import SopMatcher
from app.models.common import utc_now
from app.models.decision import (
    CostEstimate,
    DecisionLogEntry,
    MaintenanceActionType,
    PriorityLevel,
    Recommendation,
    RecommendationRequest,
    RecommendationResponse,
    RiskFactorBreakdown,
    SeverityTier,
    SOPStepDetail,
    TriggeredRule,
)
from app.models.predictive import InferenceRequest, InferenceResponse
from app.models.telemetry import TelemetryReading
from app.models.xai import ExplanationRequest, ExplanationResponse
from app.predictive.prediction_service import PredictionServiceUnavailable, get_prediction_service
from app.predictive.telemetry_simulator import generate_episode
from app.predictive.xai_service import get_xai_service

logger = logging.getLogger(__name__)

#: Severity tier -> outward-facing priority band.
_TIER_TO_PRIORITY: Dict[SeverityTier, PriorityLevel] = {
    SeverityTier.IMMINENT: PriorityLevel.CRITICAL,
    SeverityTier.SCHEDULED: PriorityLevel.HIGH,
    SeverityTier.MONITOR: PriorityLevel.MEDIUM,
}

#: Severity tier -> default recommended-completion offset (days).
_TIER_TO_COMPLETION_DAYS: Dict[SeverityTier, float] = {
    SeverityTier.IMMINENT: 1.0,
    SeverityTier.SCHEDULED: 7.0,
    SeverityTier.MONITOR: 30.0,
}

#: Severity tier -> primary prescriptive action archetype (used when the
#: matched SOP does not resolve a more specific action type).
_TIER_TO_ACTION: Dict[SeverityTier, MaintenanceActionType] = {
    SeverityTier.IMMINENT: MaintenanceActionType.ISOLATE,
    SeverityTier.SCHEDULED: MaintenanceActionType.REPLACE,
    SeverityTier.MONITOR: MaintenanceActionType.MONITOR,
}


class DecisionService:
    """Async orchestrator for ``POST /api/v1/decision/recommend``."""

    def __init__(
        self,
        *,
        rule_engine: Optional[RuleEngine] = None,
        risk_scorer: Optional[RiskScorer] = None,
        sop_matcher: Optional[SopMatcher] = None,
    ) -> None:
        self._settings_provider = get_settings
        self.rule_engine = rule_engine or RuleEngine()
        self.risk_scorer = risk_scorer or RiskScorer()
        self.sop_matcher = sop_matcher or SopMatcher()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """Run the full prescriptive pipeline for one asset."""
        settings = self._settings_provider()

        signal, degraded_reasons = await self._build_prediction_signal(request)
        signal.asset_criticality_tier = await self._lookup_asset_criticality(request.asset_id)
        (
            signal.failure_mode_severity_tier,
            failure_mode_rpn_hint,
        ) = await self._lookup_failure_mode_ontology(signal.failure_mode_id)

        classification = self.rule_engine.classify(signal)
        criticality_weight = self.rule_engine.criticality_weight(signal.asset_criticality_tier)

        risk_breakdown = self.risk_scorer.score(
            probability_of_failure=signal.failure_probability,
            severity_tier=signal.failure_mode_severity_tier,
            risk_priority_number_hint=failure_mode_rpn_hint,
            anomaly_confidence=signal.anomaly_intensity(),
            criticality_weight=criticality_weight,
        )
        cost_estimate = self.risk_scorer.estimate_cost(risk_score=risk_breakdown.normalized_risk_score)

        sop_linkages, sop_steps, used_graph = await self.sop_matcher.find_sops_for_failure_mode(
            signal.failure_mode_id
        )

        recommendations = self._build_recommendations(
            request=request,
            signal=signal,
            classification=classification,
            risk_breakdown=risk_breakdown,
            cost_estimate=cost_estimate,
            sop_linkages=sop_linkages,
        )

        decision_log = [
            self._build_decision_log_entry(
                request=request,
                signal=signal,
                classification=classification,
                risk_breakdown=risk_breakdown,
                cost_estimate=cost_estimate,
                criticality_weight=criticality_weight,
                used_graph_sops=used_graph,
                degraded_reasons=degraded_reasons,
            )
        ]

        overall_risk = max(
            (r.risk_score_if_ignored for r in recommendations), default=risk_breakdown.normalized_risk_score
        )

        return RecommendationResponse(
            asset_id=request.asset_id,
            component_id=request.component_id or signal.component_id,
            recommendations=recommendations,
            sop_steps=sop_steps,
            decision_log=decision_log,
            overall_risk_score=round(overall_risk, 4),
        )

    # ------------------------------------------------------------------ #
    # Signal assembly — Phase 6 + Phase 7 ingestion
    # ------------------------------------------------------------------ #
    async def _build_prediction_signal(
        self, request: RecommendationRequest
    ) -> Tuple[PredictionSignal, List[str]]:
        """Pull live Phase 6/7 outputs, degrading gracefully on failure."""
        degraded: List[str] = []
        history: List[TelemetryReading] = generate_episode(asset_id=request.asset_id).frames[:24]

        inference: Optional[InferenceResponse] = None
        try:
            prediction_service = get_prediction_service()
            inference = await prediction_service.infer(
                InferenceRequest(
                    asset_id=request.asset_id,
                    component_id=request.component_id,
                    history=history,
                    horizon_hours=max(request.risk_horizon_days * 24, 24),
                )
            )
        except PredictionServiceUnavailable as exc:
            degraded.append(f"prediction_service_unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 - never fail the decision pipeline
            logger.warning("Prediction service call failed for %s: %s", request.asset_id, exc)
            degraded.append(f"prediction_service_error: {exc}")

        explanation: Optional[ExplanationResponse] = None
        try:
            xai_service = get_xai_service()
            explanation = await xai_service.explain(
                ExplanationRequest(asset_id=request.asset_id), history
            )
        except Exception as exc:  # noqa: BLE001 - never fail the decision pipeline
            logger.warning("XAI explanation call failed for %s: %s", request.asset_id, exc)
            degraded.append(f"xai_service_error: {exc}")

        signal = PredictionSignal(asset_id=request.asset_id, component_id=request.component_id)

        if inference is not None:
            signal.component_id = signal.component_id or inference.component_id
            signal.rul_days = inference.rul.value_days
            signal.failure_probability = inference.failure_probability.probability
            signal.failure_mode_id = inference.failure_probability.failure_mode_id
            signal.failure_mode_label = inference.failure_probability.failure_mode_label
            signal.anomalous_sensors = list(inference.anomalous_sensors)
            anomalous_flags = [f for f in inference.anomaly_flags if f.is_anomalous]
            signal.is_anomalous = bool(anomalous_flags)
            if anomalous_flags:
                signal.anomaly_score = min(f.anomaly_score for f in anomalous_flags)
            elif inference.anomaly_flags:
                signal.anomaly_score = inference.anomaly_flags[0].anomaly_score
        else:
            degraded.append("using_conservative_default_prediction_signal")
            # Conservative defaults: assume borderline-but-not-critical so the
            # engine still returns a MONITOR-tier recommendation rather than
            # silently omitting the asset from the prescriptive pipeline.
            settings = self._settings_provider()
            signal.rul_days = settings.decision_engine_scheduled_rul_days * 1.5
            signal.failure_probability = 0.2

        if explanation is not None:
            top_features = sorted(explanation.local_feature_importance, key=lambda f: f.rank)
            signal.top_root_cause_sensors = [f.feature_name for f in top_features[:5]]
            signal.root_cause_headline = explanation.root_cause.headline
            signal.explanation_confidence = (
                explanation.confidence_matrix[0].confidence if explanation.confidence_matrix else 0.9
            )
            signal.explanation_id = explanation.explanation_id
            if not signal.failure_mode_id and explanation.root_cause.contributing_failure_modes:
                signal.failure_mode_id = explanation.root_cause.contributing_failure_modes[0]

        return signal, degraded

    # ------------------------------------------------------------------ #
    # Graph enrichment (Phase 2 Neo4j)
    # ------------------------------------------------------------------ #
    async def _get_graph_service(self):
        try:
            from app.graph.client import GraphDriverManager

            if not (hasattr(GraphDriverManager, "_driver") and GraphDriverManager._driver is not None):
                return None
            from app.graph.graph_services import GraphAPIService

            return await GraphAPIService.connect()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Decision service graph fast bypass: %s", exc)
            return None

    async def _lookup_asset_criticality(self, asset_id: str) -> str:
        """Resolve ``Asset.criticality`` ("A"/"B"/"C") from Neo4j, if reachable."""
        settings = self._settings_provider()
        default_tier = "B"
        graph_service = await self._get_graph_service()
        if graph_service is None:
            return default_tier
        try:
            node = await graph_service.crud.get_entity("Asset", asset_id)
            if node and node.get("criticality"):
                return str(node["criticality"]).upper()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Asset criticality lookup failed for %s: %s", asset_id, exc)
        return default_tier

    async def _lookup_failure_mode_ontology(
        self, failure_mode_id: Optional[str]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Resolve ``FailureMode.severity_tier`` + legacy RPN hint from Neo4j."""
        if not failure_mode_id:
            return None, None
        graph_service = await self._get_graph_service()
        if graph_service is None:
            return None, None
        try:
            node = await graph_service.crud.get_entity("FailureMode", failure_mode_id)
            if not node:
                return None, None
            severity_tier = node.get("severity_tier")
            rpn_hint = node.get("risk_priority_number")
            return (
                str(severity_tier) if severity_tier else None,
                float(rpn_hint) if rpn_hint is not None else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("FailureMode ontology lookup failed for %s: %s", failure_mode_id, exc)
            return None, None

    # ------------------------------------------------------------------ #
    # Payload assembly
    # ------------------------------------------------------------------ #
    def _build_recommendations(
        self,
        *,
        request: RecommendationRequest,
        signal: PredictionSignal,
        classification: SeverityClassification,
        risk_breakdown: RiskFactorBreakdown,
        cost_estimate: CostEstimate,
        sop_linkages,
    ) -> List[Recommendation]:
        priority = _TIER_TO_PRIORITY[classification.tier]
        completion_offset_days = _TIER_TO_COMPLETION_DAYS[classification.tier]
        completion_by = utc_now() + timedelta(days=completion_offset_days)
        base_action = _TIER_TO_ACTION[classification.tier]

        max_n = min(request.max_recommendations, max(len(sop_linkages), 1))
        recommendations: List[Recommendation] = []

        if not sop_linkages:
            recommendations.append(
                Recommendation(
                    action_id=str(uuid.uuid4()),
                    action_type=base_action,
                    description=self._describe_action(signal, classification, sop_title=None),
                    priority=priority,
                    risk_score_if_ignored=risk_breakdown.normalized_risk_score,
                    estimated_cost_avoidance_usd=cost_estimate.estimated_cost_avoidance_usd,
                    recommended_completion_by=completion_by,
                    sop_linkage=None,
                    supporting_explanation_id=signal.explanation_id,
                    severity_tier=classification.tier,
                    rank=1,
                )
            )
            return recommendations

        # Sort SOP options by effectiveness (economic/operational efficiency)
        # descending, per the Phase 8 brief §3, before allocating rank order.
        ordered_sops = sorted(sop_linkages, key=lambda l: l.effectiveness, reverse=True)[:max_n]
        for idx, sop in enumerate(ordered_sops, start=1):
            # Risk score decays slightly for lower-ranked alternative SOPs
            # (they are still valid mitigations, just less proven/effective).
            decay = 1.0 - (0.05 * (idx - 1))
            risk_for_rank = round(max(risk_breakdown.normalized_risk_score * decay, 0.0), 4)
            cost_for_rank = round(max(cost_estimate.estimated_cost_avoidance_usd * decay, 0.0), 2)
            recommendations.append(
                Recommendation(
                    action_id=str(uuid.uuid4()),
                    action_type=base_action,
                    description=self._describe_action(signal, classification, sop_title=sop.title),
                    priority=priority,
                    risk_score_if_ignored=risk_for_rank,
                    estimated_cost_avoidance_usd=cost_for_rank,
                    recommended_completion_by=completion_by,
                    sop_linkage=sop,
                    supporting_explanation_id=signal.explanation_id,
                    severity_tier=classification.tier,
                    rank=idx,
                )
            )
        return recommendations

    @staticmethod
    def _describe_action(
        signal: PredictionSignal, classification: SeverityClassification, sop_title: Optional[str]
    ) -> str:
        sensors = ", ".join(signal.top_root_cause_sensors[:2] or signal.anomalous_sensors[:2]) or "monitored channels"
        tier_phrase = {
            SeverityTier.IMMINENT: "Immediate action required",
            SeverityTier.SCHEDULED: "Schedule maintenance",
            SeverityTier.MONITOR: "Continue monitoring",
        }[classification.tier]
        sop_phrase = f" per {sop_title}" if sop_title else ""
        return (
            f"{tier_phrase} on asset '{signal.asset_id}' — root cause implicates {sensors} "
            f"(RUL {signal.rul_days:.1f}d, P(failure)={signal.failure_probability:.2f}){sop_phrase}."
        )

    def _build_decision_log_entry(
        self,
        *,
        request: RecommendationRequest,
        signal: PredictionSignal,
        classification: SeverityClassification,
        risk_breakdown: RiskFactorBreakdown,
        cost_estimate: CostEstimate,
        criticality_weight: float,
        used_graph_sops: bool,
        degraded_reasons: List[str],
    ) -> DecisionLogEntry:
        rationale = (
            f"Classified as {classification.tier.value} "
            f"(escalation_score={classification.escalation_score:.3f}) from RUL="
            f"{signal.rul_days:.2f}d, P(failure)={signal.failure_probability:.3f}, "
            f"anomaly_intensity={signal.anomaly_intensity():.3f}, "
            f"asset_criticality_tier={signal.asset_criticality_tier} "
            f"(weight={criticality_weight:.2f}). Risk Priority Number="
            f"{risk_breakdown.risk_priority_number:.1f}/"
            f"{risk_breakdown.risk_priority_number_max:.0f} "
            f"(normalized={risk_breakdown.normalized_risk_score:.3f})."
        )
        if degraded_reasons:
            rationale += " Degraded inputs: " + "; ".join(degraded_reasons) + "."
        if not used_graph_sops:
            rationale += " SOP guidance sourced from offline fallback catalogue (graph unreachable or unmatched)."

        return DecisionLogEntry(
            decision_id=str(uuid.uuid4()),
            asset_id=request.asset_id,
            component_id=request.component_id or signal.component_id,
            failure_mode_id=signal.failure_mode_id,
            inputs={
                "rul_days": signal.rul_days,
                "failure_probability": signal.failure_probability,
                "is_anomalous": signal.is_anomalous,
                "anomaly_score": signal.anomaly_score,
                "anomaly_intensity": signal.anomaly_intensity(),
                "anomalous_sensors": signal.anomalous_sensors,
                "top_root_cause_sensors": signal.top_root_cause_sensors,
                "asset_criticality_tier": signal.asset_criticality_tier,
                "failure_mode_severity_tier": signal.failure_mode_severity_tier,
                "risk_horizon_days": request.risk_horizon_days,
                "used_graph_sops": used_graph_sops,
                "degraded_reasons": degraded_reasons,
            },
            triggered_rules=classification.triggered_rules,
            risk_breakdown=risk_breakdown,
            cost_estimate=cost_estimate,
            weights_applied={
                "criticality_weight": criticality_weight,
                "escalation_score": classification.escalation_score,
                "explanation_confidence": signal.explanation_confidence,
            },
            rationale=rationale,
        )


# ---------------------------------------------------------------------------
# Singleton accessor (mirrors get_prediction_service / get_xai_service)
# ---------------------------------------------------------------------------
_service_lock = threading.Lock()
_service: Optional[DecisionService] = None


def get_decision_service() -> DecisionService:
    global _service
    with _service_lock:
        if _service is None:
            _service = DecisionService()
        return _service
