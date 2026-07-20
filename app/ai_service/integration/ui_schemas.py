"""Pydantic v2 wire schemas — strict mirror of Section 11 + component types.

These models are the **single source of truth** for the JSON shape Member 4
binds against. Every endpoint exposed by
:mod:`app.ai_service.integration.ui_router` validates its response through
one of these models so any drift triggers a 500 immediately during tests
instead of silently shipping a malformed payload to the browser.

Field-by-field source-of-truth:

* ``UIAsset / UIAlert / UIPrediction / UIChat / UIKnowledge / UIAPIResponse``
  mirror ``src/types/index.ts`` (Section 11) byte-for-byte, including the
  ``APIResponse.error: { code, message, details? }`` shape which is *richer*
  than the backend's frozen :class:`app.models.common.APIResponse` (which
  uses ``error: Optional[str]``). The Phase 11 adapter
  :func:`app.ai_service.integration.adapters.frontend_adapters.to_ui_api_envelope`
  performs that normalisation.
* ``UIGraphNode / UIGraphEdge`` mirror the inline ``GraphNode`` /
  ``GraphEdge`` interfaces declared in ``src/components/GraphRagPanel.tsx``.
  Notably this includes the ``x``/``y`` coordinates used by the panel's
  hand-rolled SVG renderer — the adapter projects a deterministic
  force-directed layout when those coordinates are missing.
* ``UITelemetry / UIHistoryFrame / UIDigitalTwinPayload`` mirror the runtime
  shape consumed by ``src/components/DigitalTwinView.tsx``. The panel reads
  ``telemetry.{speed, vibration, pressure, temperature, flowRate, load,
  riskScore, status}`` and walks ``history`` for the mini SVG charts.
* ``UIShapFeature / UIShapExplanation`` mirror ``SHAPFeature`` and the
  consumption pattern in ``src/components/ShapExplainability.tsx``. The
  features arrive **already sorted by abs(shapValue) desc** so the panel
  can render directly with no client-side sort.
* ``UIRecommendationAction`` is a flattened view of the Phase 8
  ``Recommendation`` model tailored for an action-card UI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Generic envelope — mirrors Section 11 ``APIResponse<T>``
# ---------------------------------------------------------------------------
T = TypeVar("T")


class UIAPIResponse(BaseModel, Generic[T]):
    """Section 11 ``APIResponse<T>`` mirror (rich error shape)."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: T
    error: Optional["UIAPIError"] = None
    request_id: Optional[str] = Field(default=None, alias="requestId")
    generated_at: Optional[datetime] = Field(default=None, alias="generatedAt")


class UIAPIError(BaseModel):
    """Section 11 ``APIResponse.error`` object shape."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Optional[Any] = None


# ---------------------------------------------------------------------------
# Section 11 strict types
# ---------------------------------------------------------------------------
class UIRole(str, Enum):
    """Mirrors ``Role`` in ``src/types/index.ts``."""

    SUPER_ADMIN = "SUPER_ADMIN"
    PLANT_MANAGER = "PLANT_MANAGER"
    CONTROL_ROOM_OPERATOR = "CONTROL_ROOM_OPERATOR"
    MAINTENANCE_ENGINEER = "MAINTENANCE_ENGINEER"


class UIAssetStatus(str, Enum):
    """Mirrors ``Asset.status`` in ``src/types/index.ts``."""

    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"


class UIAsset(BaseModel):
    """Section 11 ``Asset`` mirror."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    name: str
    type: str
    status: UIAssetStatus
    parentId: Optional[str] = None


class UIAlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class UIAlert(BaseModel):
    """Section 11 ``Alert`` mirror."""

    model_config = ConfigDict(extra="forbid")

    id: str
    assetId: str
    severity: UIAlertSeverity
    message: str
    timestamp: str
    acknowledged: bool


class UIPrediction(BaseModel):
    """Section 11 ``Prediction`` mirror — exactly what ``prediction.service.ts`` expects."""

    model_config = ConfigDict(extra="forbid")

    id: str
    assetId: str
    remainingUsefulLifeDays: float
    failureProbability: float = Field(ge=0.0, le=1.0)
    inferredFaultMechanism: str


class UISender(str, Enum):
    OPERATOR = "OPERATOR"
    AI_ENGINE = "AI_ENGINE"


class UIChat(BaseModel):
    """Section 11 ``Chat`` mirror — exactly what ``chat.service.ts`` expects."""

    model_config = ConfigDict(extra="forbid")

    messageId: str
    sender: UISender
    payload: str
    timestamp: str


class UIKnowledge(BaseModel):
    """Section 11 ``Knowledge`` mirror."""

    model_config = ConfigDict(extra="forbid")

    nodeId: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    edges: List[Dict[str, str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Component-level contracts (DigitalTwinView.tsx, GraphRagPanel.tsx, ShapExplainability.tsx)
# ---------------------------------------------------------------------------
class UITelemetryStatus(str, Enum):
    """DigitalTwinView's ``telemetry.status`` vocabulary.

    Matches the four CSS classes referenced in
    ``src/components/DigitalTwinView.tsx``:
    ``"ok" | "warning" | "critical" | "offline"``.
    """

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"


class UITelemetry(BaseModel):
    """DigitalTwinView's ``currentAsset.telemetry`` shape."""

    model_config = ConfigDict(extra="forbid")

    speed: float = Field(default=0.0, description="RPM, used by the Rotational Speed card.")
    vibration: float = Field(default=0.0, description="mm/s RMS, used by the Housing Vibration card.")
    pressure: float = Field(default=0.0, description="bar, used by the Discharge Pressure card.")
    temperature: float = Field(default=0.0, description="°C, used by the Casing Temperature card.")
    flowRate: float = Field(default=0.0, description="L/m, used by pumps/compressors.")
    load: float = Field(default=0.0, description="kW electrical load.")
    riskScore: float = Field(default=0.0, ge=0.0, le=100.0, description="AI Risk Index 0..100.")
    status: UITelemetryStatus = UITelemetryStatus.OK


class UIHistoryFrame(BaseModel):
    """One frame inside DigitalTwinView's ``currentAsset.history`` array.

    The component iterates ``history`` with
    ``reading[dataKey]`` for any of the telemetry metric keys, so we
    keep the shape as a flat dict with the same key vocabulary as
    :class:`UITelemetry` plus a timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    timestamp: str
    speed: float = 0.0
    vibration: float = 0.0
    pressure: float = 0.0
    temperature: float = 0.0
    flowRate: float = 0.0
    load: float = 0.0
    riskScore: float = Field(default=0.0, ge=0.0, le=100.0)
    status: UITelemetryStatus = UITelemetryStatus.OK


class UIHistoryPoint(BaseModel):
    """Recharts/Chart.js data point: ``{x, y}`` for a single metric series."""

    model_config = ConfigDict(extra="forbid")

    x: str
    y: float


class UIDigitalTwinPayload(BaseModel):
    """Top-level shape consumed by ``DigitalTwinView.tsx``.

    The component reads:

    * ``currentAsset.telemetry``       — live numeric state
    * ``currentAsset.history``         — chronological frames for mini charts
    * ``currentAsset.id``              — for branch-specific SVG schematics
    * ``currentAsset.status``          — top status pill
    * ``riskScore``                    — **Phase 2**: top-level AI Risk Index
      (0..100 float), always populated; mirrors the telemetry card when the
      predictive engine ran, and safely defaults to ``0.0`` otherwise.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset: UIAsset
    telemetry: UITelemetry
    history: List[UIHistoryFrame] = Field(default_factory=list)
    riskScore: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description=(
            "Phase 2 — top-level AI Risk Index (0..100). Never null; "
            "computed from the inference failure probability when available "
            "and safely defaulted otherwise."
        ),
    )
    activeAnomaly: Optional[str] = Field(
        default=None,
        description=(
            "Token identifying the dominant anomaly surfaced to the panel "
            "(e.g. 'bearing-wear', 'compressor-surge', 'electrical-trip', "
            "'leakage'). DigitalTwinView branches on this string."
        ),
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="generatedAt",
    )


# ---------------------------------------------------------------------------
# GraphRagPanel.tsx contract
# ---------------------------------------------------------------------------
class UIGraphNodeType(str, Enum):
    ASSET = "asset"
    COMPONENT = "component"
    ANOMALY = "anomaly"
    PROCEDURE = "procedure"
    RECORD = "record"


class UIGraphNode(BaseModel):
    """GraphRagPanel's ``GraphNode`` shape.

    The component renders ``x``/``y`` directly inside an SVG viewport, so
    coordinates are mandatory. The adapter projects a deterministic
    layered layout whenever the underlying graph traversal returns
    nodes without positions.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    type: UIGraphNodeType
    x: float
    y: float
    details: str = ""


class UIGraphEdge(BaseModel):
    """GraphRagPanel's ``GraphEdge`` shape."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: str
    highlighted: bool = False


class UIGraphRAGPayload(BaseModel):
    """Full response the GraphRagPanel binds to in one fetch."""

    model_config = ConfigDict(extra="forbid")

    answer: str = ""
    logs: List[str] = Field(
        default_factory=list,
        description="Chronological list of retrieval/rerank/synthesis log lines.",
    )
    nodes: List[UIGraphNode] = Field(default_factory=list)
    edges: List[UIGraphEdge] = Field(default_factory=list)
    highlightedNodes: List[str] = Field(default_factory=list)
    highlightedEdges: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    vectorHits: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    badge: Optional[str] = None
    warningLevel: Optional[str] = None
    color: Optional[Any] = None
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# ShapExplainability.tsx contract
# ---------------------------------------------------------------------------
class UIWaterfallStep(BaseModel):
    """One stepwise feature contribution inside the SHAP waterfall chart.

    Phase 2 — the waterfall is an explicit typed structure (not a loose
    dict) so any drift in the stepwise-contribution shape fails fast in CI.
    """

    model_config = ConfigDict(extra="forbid")

    feature: str
    value: str = ""
    delta: float
    start: float
    end: float
    cumulative: float
    direction: str = Field(default="positive", description="'positive' | 'negative'")


class UIWaterfall(BaseModel):
    """Phase 2 — explicit waterfall payload (base value + ordered steps)."""

    model_config = ConfigDict(extra="forbid")

    baseValue: float
    finalValue: float
    bars: List[UIWaterfallStep] = Field(default_factory=list)


class UIForceContribution(BaseModel):
    """One pushing force (feature mapping) inside the force plot."""

    model_config = ConfigDict(extra="forbid")

    feature: str
    value: str = ""
    weight: float = Field(ge=0.0, description="|shapValue| — arrow length.")
    direction: str = Field(default="positive", description="'positive' | 'negative'")


class UIForcePlot(BaseModel):
    """Phase 2 — explicit force-plot payload.

    ``baseValue`` anchors the plot, ``predictionValue`` is the final model
    output, and the ``positive`` / ``negative`` stacks hold the feature
    mappings pushing the prediction up or down.
    """

    model_config = ConfigDict(extra="forbid")

    baseValue: float
    predictionValue: float
    positive: List[UIForceContribution] = Field(default_factory=list)
    negative: List[UIForceContribution] = Field(default_factory=list)


class UIShapFeature(BaseModel):
    """ShapExplainability's ``SHAPFeature`` shape.

    The panel calls ``baseList.sort((a, b) => Math.abs(b.shapValue) - Math.abs(a.shapValue))``
    but the adapter returns features **already sorted by that key** so the
    client can render directly with no client-side sort.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str
    shapValue: float
    desc: str


class UIShapExplanation(BaseModel):
    """Full SHAP/LIME payload for ``ShapExplainability.tsx``."""

    model_config = ConfigDict(extra="forbid")

    predictionId: str
    assetId: str
    method: str = "SHAP"  # SHAP | LIME | INTEGRATED_GRADIENTS | PERMUTATION
    scope: str = "LOCAL"  # LOCAL | GLOBAL
    baseValue: float = Field(description="Model expected-value baseline (SHAP E[f(x)]).")
    predictionValue: float = Field(description="Model output for this instance.")
    features: List[UIShapFeature] = Field(
        default_factory=list,
        description="Pre-sorted desc by |shapValue| — the panel renders them top-to-bottom.",
    )
    confidenceMatrix: List[Dict[str, Any]] = Field(default_factory=list)
    rootCause: Dict[str, Any] = Field(
        default_factory=dict,
        description="Headline + narrative + contributing failure modes (as dict for flexibility).",
    )
    waterfall: Optional[UIWaterfall] = Field(
        default=None,
        description="Phase 2 — explicit stepwise feature-contribution waterfall.",
    )
    forcePlot: Optional[UIForcePlot] = Field(
        default=None,
        description="Phase 2 — explicit force plot (baseValue, pushing forces, feature mappings).",
    )
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Recommendation action-card shape (prescriptive-action UI panel)
# ---------------------------------------------------------------------------
class UIActionPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UISeverityTier(str, Enum):
    IMMINENT = "IMMINENT"
    SCHEDULED = "SCHEDULED"
    MONITOR = "MONITOR"


class UISopLinkage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sopId: str
    title: str
    revision: Optional[str] = None
    effectiveness: float = 0.75


class UIRecommendationAction(BaseModel):
    """Single action card on the prescriptive-action panel. Phase 2 Recovery: allows Phase 3 compat fields."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    actionId: str
    actionType: str
    description: str
    priority: UIActionPriority
    severityTier: UISeverityTier = UISeverityTier.MONITOR
    riskScoreIfIgnored: float = Field(ge=0.0, le=1.0)
    estimatedCostAvoidanceUsd: float = Field(ge=0.0)
    recommendedCompletionBy: str
    sop: Optional[UISopLinkage] = None
    rank: int = Field(default=1, ge=1)

    # Phase 3 compatibility fields — allowed to preserve backward compat
    actionCardId: Optional[str] = None
    title: Optional[str] = None
    costAvoidance: Optional[float] = None
    riskScore: Optional[float] = None
    completionDate: Optional[str] = None


# Resolve forward references for the generic envelope
UIAPIResponse.model_rebuild()
