"""
Predictive Maintenance contracts — powers `src/components/DigitalTwinView.tsx`.

Inference requests wrap real-time `TelemetryReading` payloads (see
`telemetry.py`); responses carry RUL, failure probability, and Isolation
Forest anomaly flags rendered on the Digital Twin.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now
from app.models.telemetry import TelemetryReading


class InferenceRequest(BaseModel):
    """Real-time inference request built from ingestion-layer telemetry."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    asset_id: str
    component_id: Optional[str] = None
    telemetry_window: List[TelemetryReading] = Field(
        ..., min_length=1, description="Ordered telemetry frames feeding the model (most recent last)."
    )
    model_overrides: Optional[Dict[str, str]] = Field(
        default=None, description="Optional model name overrides, e.g. {'rul_model': 'xgboost_rul_v2'}."
    )
    include_explanation_hint: bool = Field(
        default=True, description="If true, response includes an `explanation_id` linkable to /xai."
    )


class RULEstimate(BaseModel):
    """Remaining Useful Life estimate with a confidence interval."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    value_days: float = Field(..., ge=0.0, description="Point estimate of RUL in days.")
    lower_bound_days: float = Field(..., ge=0.0)
    upper_bound_days: float = Field(..., ge=0.0)
    confidence_level: float = Field(default=0.9, ge=0.0, le=1.0, description="CI coverage, e.g. 0.9 = 90%.")
    model_name: str
    model_version: str = Field(default="1.0.0")


class FailureWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    earliest: datetime
    latest: datetime
    most_likely: datetime


class FailureProbability(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    probability: float = Field(..., ge=0.0, le=1.0)
    predicted_window: FailureWindow
    failure_mode_id: Optional[str] = Field(
        default=None, description="Phase 1 ontology :FailureMode.id, if a specific mode dominates."
    )
    failure_mode_label: Optional[str] = None
    model_name: str
    model_version: str = Field(default="1.0.0")


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


class AnomalyFlag(BaseModel):
    """Isolation-Forest-derived anomaly flag for a specific sensor/metric."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str
    metric: str
    anomaly_score: float = Field(
        ..., description="Raw Isolation Forest decision-function score (lower = more anomalous)."
    )
    is_anomalous: bool
    severity: AnomalySeverity
    detected_at: datetime = Field(default_factory=utc_now)


class InferenceResponse(BaseModel):
    """Response rendered by `DigitalTwinView.tsx`."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    component_id: Optional[str] = None
    rul: RULEstimate
    failure_probability: FailureProbability
    anomaly_flags: List[AnomalyFlag] = Field(default_factory=list)
    explanation_id: Optional[str] = Field(
        default=None, description="Correlates to an XAI ExplanationResponse via GET /xai/{explanation_id}."
    )
    inference_latency_ms: float = Field(..., ge=0.0)
    generated_at: datetime = Field(default_factory=utc_now)
    fallback_used: bool = Field(
        default=False, description="True if a degraded fallback strategy (see PDM_INFERENCE_FALLBACK_MODE) fired."
    )
