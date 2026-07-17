"""
Phase 8 — Quantitative Operational Risk Scoring.

Implements the standard industrial Risk Priority Number equation:

    RPN = P(Failure) x S(Severity) x D(Detectability)

on the classic 1-10 FMEA scale (so the maximum RPN is 1000, matching
``FailureMode.risk_priority_number`` in the Phase 1 ontology, which is
explicitly documented as "1 to 1000"), plus a criticality-weighted
normalisation into [0, 1] for ranking/sorting, and a basic cost-of-inaction
analytical model (planned maintenance vs. unplanned downtime).

Pure, deterministic, side-effect-free — no I/O. The caller
(:mod:`app.decision.decision_service`) is responsible for sourcing
``severity`` from the Graph database and ``criticality_weight`` from the
Phase 8 rule engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.models.decision import CostEstimate, RiskFactorBreakdown

#: FailureSeverityTier (ontology) -> FMEA severity score (1-10 scale).
#: CRITICAL maps to the top of the scale (safety/production stoppage);
#: INCIPIENT maps to a low nuisance-level severity.
SEVERITY_TIER_SCALE: dict[str, float] = {
    "CRITICAL": 9.0,
    "DEGRADED": 6.0,
    "INCIPIENT": 3.0,
}

_DEFAULT_SEVERITY_SCORE = 5.0  # Used when the graph has no severity_tier / RPN hint.


def probability_to_scale(probability: float) -> float:
    """Map a 0..1 failure probability onto the FMEA 1-10 occurrence scale."""
    probability = max(0.0, min(1.0, probability))
    return round(1.0 + probability * 9.0, 4)


def severity_from_ontology(
    severity_tier: str | None = None,
    risk_priority_number_hint: float | None = None,
) -> float:
    """Resolve the FMEA severity score (1-10) from graph ontology properties.

    Prefers an explicit ``FailureMode.severity_tier`` (CRITICAL/DEGRADED/
    INCIPIENT); if the graph instead only carries a legacy 1-1000
    ``risk_priority_number`` hint, that is rescaled down to a 1-10 pseudo
    severity as a best-effort fallback. Defaults to a neutral mid-scale
    value (5.0) when neither is available so an un-catalogued asset does
    not silently produce a zero risk score.
    """
    if severity_tier:
        scaled = SEVERITY_TIER_SCALE.get(severity_tier.upper())
        if scaled is not None:
            return scaled
    if risk_priority_number_hint is not None and risk_priority_number_hint > 0:
        return round(max(1.0, min(10.0, risk_priority_number_hint / 100.0)), 4)
    return _DEFAULT_SEVERITY_SCORE


def detectability_from_anomaly_confidence(anomaly_confidence: float) -> float:
    """Detectability (1-10) is *inversely* proportional to IF confidence.

    ``anomaly_confidence`` is expected in [0, 1] where 1.0 means the
    Isolation Forest is maximally confident the reading is anomalous
    (i.e. the fault is easy to *detect*). FMEA detectability convention is
    inverted vs. intuition: 1 = certain detection, 10 = undetectable. So a
    high anomaly confidence should produce a *low* detectability score.
    """
    confidence = max(0.0, min(1.0, anomaly_confidence))
    # confidence=1.0 -> detectability=1 (certain detection)
    # confidence=0.0 -> detectability=10 (essentially undetectable)
    return round(10.0 - confidence * 9.0, 4)


@dataclass
class RiskScorer:
    """Stateless RPN + cost-of-inaction calculator."""

    def score(
        self,
        *,
        probability_of_failure: float,
        severity_tier: str | None,
        risk_priority_number_hint: float | None,
        anomaly_confidence: float,
        criticality_weight: float,
    ) -> RiskFactorBreakdown:
        """Compute the full RPN = P x S x D breakdown for one asset/failure-mode.

        ``criticality_weight`` (from :mod:`app.decision.rule_engine`) is
        applied as a multiplicative modifier on top of the raw RPN so a
        primary bottleneck asset's risk score outranks an identical failure
        profile on a redundant backup unit, per the Phase 8 brief §1.
        """
        settings = get_settings()

        p_scaled = probability_to_scale(probability_of_failure)
        s_scaled = severity_from_ontology(severity_tier, risk_priority_number_hint)
        d_scaled = detectability_from_anomaly_confidence(anomaly_confidence)

        raw_rpn = p_scaled * s_scaled * d_scaled
        weighted_rpn = raw_rpn * max(criticality_weight, 0.0)

        ceiling = settings.decision_engine_rpn_ceiling * max(criticality_weight, 1.0)
        normalized = 0.0 if ceiling <= 0 else min(weighted_rpn / ceiling, 1.0)

        return RiskFactorBreakdown(
            probability_of_failure=round(max(0.0, min(1.0, probability_of_failure)), 4),
            probability_scaled=p_scaled,
            severity_scaled=s_scaled,
            detectability_scaled=d_scaled,
            criticality_weight=round(max(criticality_weight, 0.0), 4),
            risk_priority_number=round(weighted_rpn, 4),
            risk_priority_number_max=settings.decision_engine_rpn_ceiling,
            normalized_risk_score=round(normalized, 4),
        )

    def estimate_cost(
        self,
        *,
        risk_score: float,
        downtime_cost_per_hour_usd: float | None = None,
        estimated_repair_hours: float | None = None,
        planned_discount: float | None = None,
    ) -> CostEstimate:
        """Basic cost-of-inaction model: unplanned downtime vs. planned repair.

        ``unplanned_downtime_cost`` scales with both the base hourly downtime
        cost and the composite risk score (higher risk => more cascading
        secondary damage/expedite premiums assumed). ``planned_discount``
        represents the fraction saved by proactively scheduling the same
        repair (labour, parts logistics, no rush-order premium, no
        unplanned line stoppage).
        """
        settings = get_settings()
        downtime_rate = (
            downtime_cost_per_hour_usd
            if downtime_cost_per_hour_usd is not None
            else settings.decision_engine_default_downtime_cost_per_hour_usd
        )
        repair_hours = (
            estimated_repair_hours
            if estimated_repair_hours is not None
            else settings.decision_engine_default_repair_hours
        )
        discount = (
            planned_discount
            if planned_discount is not None
            else settings.decision_engine_planned_maintenance_discount
        )

        risk_score = max(0.0, min(1.0, risk_score))
        # Risk amplifies unplanned cost: at risk=0 the multiplier is 1.0x
        # (base repair cost only); at risk=1 it climbs to 3x (cascading
        # secondary failure / lost-production / expedite-freight premium).
        severity_multiplier = 1.0 + (risk_score * 2.0)

        unplanned_cost = downtime_rate * repair_hours * severity_multiplier
        planned_cost = downtime_rate * repair_hours * (1.0 - discount)
        planned_cost = max(planned_cost, 0.0)
        avoidance = max(unplanned_cost - planned_cost, 0.0)

        return CostEstimate(
            unplanned_downtime_cost_usd=round(unplanned_cost, 2),
            planned_maintenance_cost_usd=round(planned_cost, 2),
            estimated_cost_avoidance_usd=round(avoidance, 2),
            downtime_cost_per_hour_usd=round(downtime_rate, 2),
            estimated_repair_hours=round(repair_hours, 2),
        )
