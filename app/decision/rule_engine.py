"""
Phase 8 — Multi-Criteria Rule & Priority Engine.

Pure, deterministic, side-effect-free classification logic:

  1. :class:`PredictionSignal` — the normalised bundle of Phase 6 (RUL,
     anomaly, failure probability) + Phase 7 (root-cause sensors) outputs
     that every rule evaluates against.
  2. :func:`classify_severity` — the dynamic severity classification matrix
     (IMMINENT / SCHEDULED / MONITOR) driven by RUL + failure probability +
     anomaly intensity thresholds (``Settings.decision_engine_*``).
  3. :func:`asset_criticality_weight` — cross-references the Phase 2 Neo4j
     ``Asset.criticality`` property (falling back to a safe default when the
     graph is unreachable) so an identical failure profile on a primary
     bottleneck asset outranks the same profile on a redundant backup unit.

Every function here is a pure function over plain data (no I/O), so the
whole module is unit-testable without a database, an ML model, or a running
FastAPI app — only :func:`asset_criticality_weight`'s *caller*
(:mod:`app.decision.decision_service`) touches Neo4j.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.models.decision import SeverityTier, TriggeredRule

# ---------------------------------------------------------------------------
# Criticality vocabulary (mirrors app.models.ontology.CriticalityTier)
# ---------------------------------------------------------------------------

#: Numeric weight applied per Neo4j ``Asset.criticality`` tier. Tier "A"
#: (safety/production bottleneck) dominates an identical failure profile on
#: a "C" tier (redundant/backup) asset — this is the asset-criticality
#: prioritization index required by the Phase 8 brief §1.
CRITICALITY_WEIGHTS: Dict[str, float] = {
    "A": 1.5,   # Primary / bottleneck / safety-critical
    "B": 1.15,  # Important but has partial redundancy
    "C": 0.85,  # Redundant / backup unit
}

#: FailureSeverityTier (Phase 1 ontology) -> extra escalation nudge applied
#: on top of the RUL/probability thresholds when the graph exposes the
#: FailureMode.severity_tier property.
FAILURE_MODE_SEVERITY_BOOST: Dict[str, float] = {
    "CRITICAL": 0.20,
    "DEGRADED": 0.08,
    "INCIPIENT": 0.0,
}


@dataclass
class PredictionSignal:
    """Normalised ingestion of Phase 6 + Phase 7 outputs for one asset.

    This is the single seam the rule engine, risk scorer, and SOP matcher
    all read from — it decouples the Decision Engine from the exact shape
    of ``InferenceResponse`` / ``ExplanationResponse`` so unit tests can
    construct edge cases directly without spinning up the ML pipeline.
    """

    asset_id: str
    component_id: Optional[str] = None

    # --- Phase 6 (Predictive Maintenance) ---
    rul_days: float = 30.0
    failure_probability: float = 0.0
    is_anomalous: bool = False
    anomaly_score: float = 0.0  # Isolation Forest decision_function; negative = anomalous
    failure_mode_id: Optional[str] = None
    failure_mode_label: Optional[str] = None
    anomalous_sensors: List[str] = field(default_factory=list)

    # --- Phase 7 (XAI) ---
    top_root_cause_sensors: List[str] = field(default_factory=list)
    root_cause_headline: Optional[str] = None
    explanation_confidence: float = 0.9
    explanation_id: Optional[str] = None

    # --- Ontology enrichment (populated by the caller from Neo4j) ---
    asset_criticality_tier: str = "B"
    failure_mode_severity_tier: Optional[str] = None

    def anomaly_intensity(self) -> float:
        """Map the raw Isolation Forest score into a 0..1 intensity band.

        More negative decision-function scores are stronger outliers; this
        clamps/normalises so rule thresholds stay readable (e.g. "intensity
        > 0.6" rather than "score < -0.18").
        """
        if not self.is_anomalous:
            return 0.0
        # Empirically IF scores rarely exceed -0.5 in magnitude for this
        # feature space (see app/predictive/prediction_service.py::_severity).
        return float(min(abs(self.anomaly_score) / 0.5, 1.0))


@dataclass
class SeverityClassification:
    """Result of the dynamic severity classification matrix."""

    tier: SeverityTier
    triggered_rules: List[TriggeredRule]
    escalation_score: float  # 0..1 composite used for tie-breaking/sorting


def classify_severity(signal: PredictionSignal) -> SeverityClassification:
    """Deterministic multi-criteria severity classifier.

    Rules are evaluated in priority order and the *first* matching rule
    that would escalate the tier wins (IMMINENT > SCHEDULED > MONITOR),
    but every rule is still recorded in ``triggered_rules`` for the audit
    trail regardless of whether it changed the outcome.

    Classification axes (Phase 8 brief §1):
      * Remaining Useful Life (RUL) duration.
      * Failure probability (can force-escalate even with borderline RUL).
      * Anomaly intensity (Isolation Forest confidence).
      * Negative / already-elapsed RUL is treated as an immediate failure.
    """
    settings = get_settings()
    rules: List[TriggeredRule] = []
    tier = SeverityTier.MONITOR

    # --- Rule 1: RUL already elapsed or negative -> always IMMINENT. ---
    rul_elapsed = signal.rul_days <= 0.0
    rules.append(
        TriggeredRule(
            rule_name="rul_elapsed_or_negative",
            condition="rul_days <= 0.0",
            fired=rul_elapsed,
            resulting_tier=SeverityTier.IMMINENT if rul_elapsed else None,
        )
    )
    if rul_elapsed:
        tier = SeverityTier.IMMINENT

    # --- Rule 2: RUL within the imminent window. ---
    rul_imminent = 0.0 < signal.rul_days <= settings.decision_engine_imminent_rul_days
    rules.append(
        TriggeredRule(
            rule_name="rul_within_imminent_window",
            condition=f"0 < rul_days <= {settings.decision_engine_imminent_rul_days}",
            fired=rul_imminent,
            resulting_tier=SeverityTier.IMMINENT if rul_imminent else None,
        )
    )
    if rul_imminent:
        tier = SeverityTier.IMMINENT

    # --- Rule 3: RUL within the scheduled-maintenance window. ---
    rul_scheduled = (
        settings.decision_engine_imminent_rul_days
        < signal.rul_days
        <= settings.decision_engine_scheduled_rul_days
    )
    rules.append(
        TriggeredRule(
            rule_name="rul_within_scheduled_window",
            condition=(
                f"{settings.decision_engine_imminent_rul_days} < rul_days <= "
                f"{settings.decision_engine_scheduled_rul_days}"
            ),
            fired=rul_scheduled,
            resulting_tier=SeverityTier.SCHEDULED if rul_scheduled else None,
        )
    )
    if rul_scheduled and tier == SeverityTier.MONITOR:
        tier = SeverityTier.SCHEDULED

    # --- Rule 4: Failure probability force-escalation (independent of RUL). ---
    prob_imminent = signal.failure_probability >= settings.decision_engine_imminent_probability
    rules.append(
        TriggeredRule(
            rule_name="failure_probability_force_imminent",
            condition=f"failure_probability >= {settings.decision_engine_imminent_probability}",
            fired=prob_imminent,
            resulting_tier=SeverityTier.IMMINENT if prob_imminent else None,
        )
    )
    if prob_imminent:
        tier = SeverityTier.IMMINENT

    prob_scheduled = (
        settings.decision_engine_scheduled_probability
        <= signal.failure_probability
        < settings.decision_engine_imminent_probability
    )
    rules.append(
        TriggeredRule(
            rule_name="failure_probability_force_scheduled",
            condition=(
                f"{settings.decision_engine_scheduled_probability} <= failure_probability < "
                f"{settings.decision_engine_imminent_probability}"
            ),
            fired=prob_scheduled,
            resulting_tier=SeverityTier.SCHEDULED if prob_scheduled else None,
        )
    )
    if prob_scheduled and tier == SeverityTier.MONITOR:
        tier = SeverityTier.SCHEDULED

    # --- Rule 5: High-intensity anomaly nudges MONITOR -> SCHEDULED. ---
    intensity = signal.anomaly_intensity()
    anomaly_escalates = signal.is_anomalous and intensity >= 0.6
    rules.append(
        TriggeredRule(
            rule_name="high_intensity_anomaly_escalation",
            condition="is_anomalous AND anomaly_intensity >= 0.6",
            fired=anomaly_escalates,
            resulting_tier=SeverityTier.SCHEDULED if anomaly_escalates else None,
        )
    )
    if anomaly_escalates and tier == SeverityTier.MONITOR:
        tier = SeverityTier.SCHEDULED

    # --- Rule 6: Multi-sensor simultaneous anomaly -> force at least SCHEDULED. ---
    multi_sensor = len({*signal.anomalous_sensors, *signal.top_root_cause_sensors}) >= 2
    rules.append(
        TriggeredRule(
            rule_name="simultaneous_multi_sensor_failure",
            condition="count(distinct implicated sensors) >= 2",
            fired=multi_sensor,
            resulting_tier=SeverityTier.SCHEDULED if multi_sensor else None,
        )
    )
    if multi_sensor and tier == SeverityTier.MONITOR:
        tier = SeverityTier.SCHEDULED

    # --- Rule 7: Ontology-declared CRITICAL failure mode is a hard floor. ---
    fm_critical = (signal.failure_mode_severity_tier or "").upper() == "CRITICAL"
    rules.append(
        TriggeredRule(
            rule_name="ontology_failure_mode_critical_floor",
            condition="FailureMode.severity_tier == 'CRITICAL'",
            fired=fm_critical,
            resulting_tier=SeverityTier.IMMINENT if fm_critical else None,
        )
    )
    if fm_critical:
        tier = SeverityTier.IMMINENT

    # Composite escalation score for sorting/tie-breaking across assets
    # (used later by the SOP matcher / decision service to rank multiple
    # simultaneous alerts, independent of the discrete tier bucket).
    rul_component = 1.0 - min(max(signal.rul_days, 0.0) / max(settings.decision_engine_scheduled_rul_days, 1e-6), 1.0)
    escalation_score = float(
        min(
            max(
                0.5 * rul_component
                + 0.35 * signal.failure_probability
                + 0.15 * intensity,
                0.0,
            ),
            1.0,
        )
    )

    return SeverityClassification(tier=tier, triggered_rules=rules, escalation_score=escalation_score)


def asset_criticality_weight(criticality_tier: Optional[str]) -> float:
    """Map a Neo4j ``Asset.criticality`` tier ("A"/"B"/"C") to a numeric weight.

    Falls back to ``Settings.decision_engine_default_criticality_weight``
    when the tier is missing/unrecognised (e.g. asset not catalogued yet,
    or the graph lookup failed/timed-out).
    """
    settings = get_settings()
    if not criticality_tier:
        return settings.decision_engine_default_criticality_weight
    return CRITICALITY_WEIGHTS.get(
        criticality_tier.upper(), settings.decision_engine_default_criticality_weight
    )


def failure_mode_severity_boost(severity_tier: Optional[str]) -> float:
    """Extra escalation weight contributed by the ontology's failure-mode tier."""
    if not severity_tier:
        return 0.0
    return FAILURE_MODE_SEVERITY_BOOST.get(severity_tier.upper(), 0.0)


class RuleEngine:
    """Stateless facade bundling the pure classification functions above.

    Kept as a thin class (rather than bare module functions) so the
    orchestrator (:mod:`app.decision.decision_service`) can depend on an
    injectable object — useful for tests that want to monkeypatch specific
    rule behaviour without touching module globals.
    """

    def classify(self, signal: PredictionSignal) -> SeverityClassification:
        return classify_severity(signal)

    def criticality_weight(self, criticality_tier: Optional[str]) -> float:
        return asset_criticality_weight(criticality_tier)

    def severity_boost(self, severity_tier: Optional[str]) -> float:
        return failure_mode_severity_boost(severity_tier)

    def prioritize(
        self, classifications: List[tuple[str, SeverityClassification, float]]
    ) -> List[str]:
        """Rank a batch of (asset_id, classification, criticality_weight) tuples.

        Sort key: severity tier (IMMINENT first) -> criticality-weighted
        escalation score (descending). Returns asset_ids in priority order —
        this is the "identical failure profile on a bottleneck pump
        overrides a redundant backup unit" behaviour from the Phase 8 brief.
        """
        tier_rank = {SeverityTier.IMMINENT: 0, SeverityTier.SCHEDULED: 1, SeverityTier.MONITOR: 2}
        ordered = sorted(
            classifications,
            key=lambda item: (
                tier_rank[item[1].tier],
                -(item[1].escalation_score * item[2]),
            ),
        )
        return [asset_id for asset_id, _, _ in ordered]
