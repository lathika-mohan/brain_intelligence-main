"""
Decision Engine contracts — Phase 0 (frozen stub) → Phase 8 (implemented).

Section 4 of ``docs/api_contracts.md`` freezes the wire shape for
``POST /api/v1/decision/recommend``:

    RecommendationRequest
      └── asset_id, component_id, risk_horizon_days, max_recommendations

    RecommendationResponse
      ├── asset_id, component_id
      ├── recommendations: List[Recommendation]
      │     └── action_id, action_type, description, priority,
      │         risk_score_if_ignored, estimated_cost_avoidance_usd,
      │         recommended_completion_by, sop_linkage,
      │         supporting_explanation_id
      ├── overall_risk_score
      └── generated_at

Phase 8 additionally surfaces two auditable extras consumed by the
prescriptive-action UI panel and by compliance tooling — ``sop_steps``
(the structured procedure breakdown backing each recommendation's
``sop_linkage``) and ``decision_log`` (the rule/weight audit trail that
justifies the ranking). Both are *additive* fields with safe defaults so
existing consumers built against the frozen §4 shape keep working
unmodified — this mirrors how Phase 6/7 layered richer contracts on top
of their Phase 0 stubs (see ``app/models/predictive.py`` / ``xai.py``).

The tiny Phase 0 stub (``DecisionRecommendRequest`` / ``DecisionRecommendResponse``
/ ``DecisionRecommendation``) is preserved verbatim so earlier-phase imports
keep working.

No business logic lives here — the rule engine, risk scorer, SOP matcher and
orchestrator live in ``app/decision/``.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now

# ---------------------------------------------------------------------------
# Phase 0 stubs — kept for backward compatibility (do not remove)
# ---------------------------------------------------------------------------


class DecisionRecommendRequest(BaseModel):
    asset_id: str
    risk_horizon_days: int = 30
    max_recommendations: int = 5


class DecisionRecommendation(BaseModel):
    action: str
    rationale: str
    confidence: float
    priority: int


class DecisionRecommendResponse(BaseModel):
    asset_id: str
    recommendations: List[DecisionRecommendation]


# ---------------------------------------------------------------------------
# Phase 8 — frozen recommend contract (docs/api_contracts.md §4)
# ---------------------------------------------------------------------------


class PriorityLevel(str, Enum):
    """Wire-level priority band surfaced on every ``Recommendation``.

    Kept as the industrial-standard LOW/MEDIUM/HIGH/CRITICAL vocabulary
    (matching ``RiskLevel`` in ``app/models/ontology.py``) so the frozen
    §4 example (``"priority": "HIGH"``) is satisfied verbatim.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SeverityTier(str, Enum):
    """Decision-engine action tier (§1 of the Phase 8 brief).

    Mirrors ``FailureSeverityTier`` (CRITICAL/DEGRADED/INCIPIENT) from the
    Phase 1 ontology, renamed to the operational vocabulary the plant floor
    reacts to.
    """

    IMMINENT = "IMMINENT"      # Critical — immediate action required
    SCHEDULED = "SCHEDULED"    # Degraded — plan maintenance within horizon
    MONITOR = "MONITOR"        # Incipient — watch, no action yet


class MaintenanceActionType(str, Enum):
    """Canonical prescriptive action vocabulary (subset of ``MaintenanceTask``
    types referenced in ``docs/industrial_knowledge_ontology.md`` §2.4)."""

    LUBRICATE = "LUBRICATE"
    REPLACE = "REPLACE"
    INSPECT = "INSPECT"
    ISOLATE = "ISOLATE"
    CALIBRATE = "CALIBRATE"
    ALIGN = "ALIGN"
    BALANCE = "BALANCE"
    MONITOR = "MONITOR"
    SHUTDOWN = "SHUTDOWN"
    SCHEDULE_INSPECTION = "SCHEDULE_INSPECTION"


class RecommendationRequest(BaseModel):
    """Frozen §4 request contract."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(..., min_length=1)
    component_id: Optional[str] = None
    risk_horizon_days: int = Field(default=30, ge=1, le=365)
    max_recommendations: int = Field(default=5, ge=1, le=20)


class SOPLinkage(BaseModel):
    """Pointer from a recommendation back to its governing SOP."""

    model_config = ConfigDict(extra="forbid")

    sop_id: str
    title: str
    document_url: Optional[str] = None
    revision: Optional[str] = None
    effectiveness: float = Field(default=0.75, ge=0.0, le=1.0)


class Recommendation(BaseModel):
    """One prescriptive, risk-ranked action — the frozen §4 shape."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    action_type: MaintenanceActionType
    description: str
    priority: PriorityLevel
    risk_score_if_ignored: float = Field(..., ge=0.0, le=1.0)
    estimated_cost_avoidance_usd: float = Field(..., ge=0.0)
    recommended_completion_by: datetime
    sop_linkage: Optional[SOPLinkage] = None
    supporting_explanation_id: Optional[str] = None

    # --- Phase 8 additive fields (non-breaking; safe defaults) ---
    severity_tier: SeverityTier = SeverityTier.MONITOR
    rank: int = Field(default=1, ge=1)


class SOPStepDetail(BaseModel):
    """Structured procedure breakdown backing a recommendation's SOP linkage."""

    model_config = ConfigDict(extra="forbid")

    sop_id: str
    sop_title: str
    sequence_number: int = Field(..., ge=1)
    instruction: str
    expected_outcome: Optional[str] = None
    step_type: str = "EXECUTION"
    hold_point: bool = False
    tooling_required: List[str] = Field(default_factory=list)
    hazards: List[str] = Field(default_factory=list)
    required_ppe: List[str] = Field(default_factory=list)


class TriggeredRule(BaseModel):
    """One fired rule inside the multi-criteria severity evaluator."""

    model_config = ConfigDict(extra="forbid")

    rule_name: str
    condition: str
    fired: bool
    resulting_tier: Optional[SeverityTier] = None


class RiskFactorBreakdown(BaseModel):
    """Explicit RPN = P x S x D decomposition for audit/justification."""

    model_config = ConfigDict(extra="forbid")

    probability_of_failure: float = Field(..., ge=0.0, le=1.0)
    probability_scaled: float = Field(..., ge=0.0, le=10.0)
    severity_scaled: float = Field(..., ge=0.0, le=10.0)
    detectability_scaled: float = Field(..., ge=0.0, le=10.0)
    criticality_weight: float = Field(..., gt=0.0)
    risk_priority_number: float = Field(..., ge=0.0)
    risk_priority_number_max: float = 1000.0
    normalized_risk_score: float = Field(..., ge=0.0, le=1.0)
    formula: str = "RPN = P(scaled 0-10) x S(scaled 0-10) x D(scaled 0-10) x CriticalityWeight"


class CostEstimate(BaseModel):
    """Basic cost-of-inaction vs. planned-intervention analytical model."""

    model_config = ConfigDict(extra="forbid")

    unplanned_downtime_cost_usd: float = Field(..., ge=0.0)
    planned_maintenance_cost_usd: float = Field(..., ge=0.0)
    estimated_cost_avoidance_usd: float = Field(..., ge=0.0)
    downtime_cost_per_hour_usd: float = Field(..., ge=0.0)
    estimated_repair_hours: float = Field(..., ge=0.0)


class DecisionLogEntry(BaseModel):
    """Auditable snapshot of one recommendation's derivation.

    Captures the inputs, weights, and rules triggered so a maintenance
    planner (or a compliance auditor) can reconstruct exactly *why* the
    engine ranked this action the way it did.
    """

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    asset_id: str
    component_id: Optional[str] = None
    failure_mode_id: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    triggered_rules: List[TriggeredRule] = Field(default_factory=list)
    risk_breakdown: RiskFactorBreakdown
    cost_estimate: CostEstimate
    weights_applied: Dict[str, float] = Field(default_factory=dict)
    rationale: str
    generated_at: datetime = Field(default_factory=utc_now)


class RecommendationResponse(BaseModel):
    """Frozen §4 response contract, additively enriched for Phase 8."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    component_id: Optional[str] = None
    recommendations: List[Recommendation] = Field(default_factory=list)

    # Phase 8 additive fields (non-breaking; default to empty/zero so a
    # strict §4-only consumer still validates successfully).
    sop_steps: List[SOPStepDetail] = Field(default_factory=list)
    decision_log: List[DecisionLogEntry] = Field(default_factory=list)

    overall_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=utc_now)
