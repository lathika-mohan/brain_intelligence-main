"""
Predictive Maintenance contracts — Phase 0 (frozen) → Phase 6 (implemented).

These Pydantic models are the *exact* wire shapes documented in
``docs/api_contracts.md`` §2 (``POST /api/v1/predictive/infer``) which powers
``src/components/DigitalTwinView.tsx``:

    InferenceResponse
      ├── rul: RulEstimate                     (value + upper/lower confidence bounds)
      ├── failure_probability: FailureProbability  (normalised 0..1 + predicted window)
      └── anomaly_flags: List[AnomalyFlag]     (score, is_anomalous, offending sensor)

The tiny Phase 0 stubs (``PredictiveInferRequest`` / ``PredictiveInferResponse``)
are preserved verbatim so earlier-phase imports keep working.

No ML logic lives here — contract vocabulary only. The engines live in
``app/predictive/``.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now
from app.models.telemetry import TelemetryReading


# ---------------------------------------------------------------------------
# Phase 0 stubs — kept for backward compatibility (do not remove)
# ---------------------------------------------------------------------------

class PredictiveInferRequest(BaseModel):
    asset_id: str
    horizon_hours: int = 24


class PredictiveInferResponse(BaseModel):
    asset_id: str
    rul_hours: Optional[float] = None
    failure_probability: float = 0.0
    anomaly_score: float = 0.0
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Phase 6 — frozen inference contract (docs/api_contracts.md §2)
# ---------------------------------------------------------------------------

class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RulEstimate(BaseModel):
    """Remaining Useful Life prediction with confidence bounds."""

    model_config = ConfigDict(extra="forbid")

    value_days: float = Field(..., ge=0.0, description="Point RUL estimate in days.")
    lower_bound_days: float = Field(..., ge=0.0)
    upper_bound_days: float = Field(..., ge=0.0)
    confidence_level: float = Field(default=0.9, ge=0.0, le=1.0)
    model_name: str = "xgboost_rul_v1"
    model_version: str = "1.0.0"


class FailureWindow(BaseModel):
    """Predicted calendar window during which failure is most likely."""

    model_config = ConfigDict(extra="forbid")

    earliest: datetime
    latest: datetime
    most_likely: datetime


class FailureProbability(BaseModel):
    """Normalised likelihood of breakdown within the imminent window."""

    model_config = ConfigDict(extra="forbid")

    probability: float = Field(..., ge=0.0, le=1.0)
    predicted_window: FailureWindow
    failure_mode_id: Optional[str] = None
    failure_mode_label: Optional[str] = None
    model_name: str = "xgboost_failure_classifier_v1"
    model_version: str = "1.0.0"


class AnomalyFlag(BaseModel):
    """Per-sensor anomaly verdict from the Isolation Forest engine."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str
    metric: str
    anomaly_score: float = Field(
        ...,
        description=(
            "Isolation Forest decision-function score. Negative values are "
            "anomalous; the more negative, the stronger the outlier."
        ),
    )
    is_anomalous: bool = False
    severity: AnomalySeverity = AnomalySeverity.LOW
    detected_at: datetime = Field(default_factory=utc_now)


class InferenceRequest(BaseModel):
    """Request wrapping one or more frozen ``TelemetryReading`` frames.

    ``history`` should contain the most recent frames for the asset in
    chronological order — enough to cover the largest rolling window
    (24 h). Fewer frames are accepted; window features degrade gracefully.
    """

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(..., min_length=1)
    component_id: Optional[str] = None
    history: List[TelemetryReading] = Field(..., min_length=1)
    horizon_hours: int = Field(default=24, ge=1, le=24 * 90)


class InferenceResponse(BaseModel):
    """Frozen response contract consumed by ``DigitalTwinView.tsx``."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    component_id: Optional[str] = None
    rul: RulEstimate
    failure_probability: FailureProbability
    anomaly_flags: List[AnomalyFlag] = Field(default_factory=list)
    anomalous_sensors: List[str] = Field(
        default_factory=list,
        description="Convenience list of sensor_ids currently flagged anomalous.",
    )
    explanation_id: Optional[str] = Field(
        default=None, description="UUID linkable to POST /api/v1/xai/explain."
    )
    inference_latency_ms: float = 0.0
    generated_at: datetime = Field(default_factory=utc_now)
    fallback_used: bool = False


# ---------------------------------------------------------------------------
# Phase 6 — evaluation / registry artifacts
# ---------------------------------------------------------------------------

class RegressionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mae: float
    rmse: float
    r2: float
    n_samples: int


class AnomalyMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precision: float
    recall: float
    f1: float
    n_samples: int
    contamination: float


class FeatureImportanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_name: str
    importance: float
    rank: int = Field(..., ge=1)


class ModelEvaluationReport(BaseModel):
    """Serialised alongside model artifacts by ``train_predictive_models.py``."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    trained_at: datetime = Field(default_factory=utc_now)
    rul_model_name: str = "xgboost_rul_v1"
    rul_model_version: str = "1.0.0"
    anomaly_model_name: str = "isolation_forest_v1"
    anomaly_model_version: str = "1.0.0"
    rul_metrics: RegressionMetrics
    anomaly_metrics: AnomalyMetrics
    feature_importance: List[FeatureImportanceEntry] = Field(default_factory=list)
    feature_columns: List[str] = Field(default_factory=list)
    training_config: Dict[str, Any] = Field(default_factory=dict)
