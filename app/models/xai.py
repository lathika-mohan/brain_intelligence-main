"""
Explainable AI (XAI) contracts — powers `src/components/ShapExplainability.tsx`.

Frozen Phase 0 request/response shapes for SHAP/LIME feature-attribution
explanations. This is shared contract vocabulary only; no computation logic
lives here (the actual SHAP/LIME engine lands in a later phase).

Reconstructed in Phase 2 to restore the package import graph after the
initial repository snapshot shipped without it.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now


class ExplanationMethod(str, Enum):
    SHAP = "SHAP"
    LIME = "LIME"
    INTEGRATED_GRADIENTS = "INTEGRATED_GRADIENTS"
    PERMUTATION = "PERMUTATION"


class ExplanationScope(str, Enum):
    LOCAL = "LOCAL"
    GLOBAL = "GLOBAL"


class FeatureImpact(BaseModel):
    """One attributed feature and its directional contribution."""

    model_config = ConfigDict(extra="forbid")

    feature_name: str
    impact_weight: float = Field(..., description="Signed attribution weight for this feature.")
    feature_value: float = Field(..., description="Observed value of the feature at inference time.")
    rank: int = Field(..., ge=1, description="Rank by absolute impact (1 = most influential).")


class ConfidenceMatrixEntry(BaseModel):
    """A single (failure-mode/diagnosis, confidence) pair."""

    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class RootCauseSummary(BaseModel):
    """Natural-language ranked root-cause narrative."""

    model_config = ConfigDict(extra="forbid")

    headline: str
    narrative: str
    contributing_failure_modes: List[str] = Field(default_factory=list)


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    explanation_id: Optional[str] = Field(default=None, description="Client-supplied id for idempotency.")
    method: ExplanationMethod = ExplanationMethod.SHAP
    scope: ExplanationScope = ExplanationScope.LOCAL
    target_model_name: Optional[str] = Field(default=None, description="Which classifier to explain.")


class ExplanationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    explanation_id: str
    asset_id: str
    method: ExplanationMethod
    scope: ExplanationScope
    base_value: float = Field(..., description="Model expected-value baseline (e.g. SHAP E[f(x)]).")
    predicted_value: float = Field(..., description="Model output for this instance.")
    global_feature_importance: Optional[List[FeatureImpact]] = None
    local_feature_importance: List[FeatureImpact] = Field(default_factory=list)
    root_cause: RootCauseSummary
    confidence_matrix: List[ConfidenceMatrixEntry] = Field(default_factory=list)
    model_name: Optional[str] = None
    model_version: str = "1.0.0"
    generated_at: datetime = Field(default_factory=utc_now)
