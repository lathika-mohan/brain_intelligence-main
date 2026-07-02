"""
Explainable AI (XAI) contracts — powers `src/components/ShapExplainability.tsx`.

Carries both global (model-level) and local (single-prediction) SHAP/LIME
feature-importance values, a root-cause narrative, and a confidence
scoring matrix.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now


class ExplanationMethod(str, Enum):
    SHAP = "SHAP"
    LIME = "LIME"


class ExplanationScope(str, Enum):
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"


class ExplanationRequest(BaseModel):
    """Request an explanation for a prior inference, or ad hoc feature set."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str
    explanation_id: Optional[str] = Field(
        default=None, description="If set, re-fetches a cached explanation tied to a prior InferenceResponse."
    )
    method: ExplanationMethod = ExplanationMethod.SHAP
    scope: ExplanationScope = ExplanationScope.LOCAL
    feature_vector: Optional[Dict[str, float]] = Field(
        default=None, description="Required for ad hoc (non-cached) local explanations."
    )
    target_model_name: str = Field(default="xgboost_failure_classifier_v1")


class FeatureImpact(BaseModel):
    """A single feature's contribution to the model output."""

    model_config = ConfigDict(extra="forbid")

    feature_name: str
    impact_weight: float = Field(..., description="Signed contribution; sign indicates direction of impact.")
    feature_value: Optional[float] = Field(default=None, description="Observed value that produced this impact.")
    rank: int = Field(..., ge=1, description="1 = most influential feature.")


class RootCauseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(..., description="One-line root cause statement.")
    narrative: str = Field(..., description="Full natural-language root-cause explanation.")
    contributing_failure_modes: List[str] = Field(
        default_factory=list, description="Neo4j :FailureMode.id values implicated."
    )


class ConfidenceMatrixEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="e.g. a failure mode or class name.")
    confidence: float = Field(..., ge=0.0, le=1.0)


class ExplanationResponse(BaseModel):
    """Response rendered by `ShapExplainability.tsx`."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    explanation_id: str
    asset_id: str
    method: ExplanationMethod
    scope: ExplanationScope
    base_value: float = Field(..., description="Model expected value / baseline before feature contributions.")
    predicted_value: float = Field(..., description="Final model output for this instance (or global mean).")
    global_feature_importance: Optional[List[FeatureImpact]] = Field(
        default=None, description="Populated when scope=GLOBAL (or always included as model-level context)."
    )
    local_feature_importance: Optional[List[FeatureImpact]] = Field(
        default=None, description="Populated when scope=LOCAL."
    )
    root_cause: RootCauseSummary
    confidence_matrix: List[ConfidenceMatrixEntry] = Field(default_factory=list)
    model_name: str
    model_version: str = Field(default="1.0.0")
    generated_at: datetime = Field(default_factory=utc_now)
