"""
Explainable AI (XAI) router — powers `ShapExplainability.tsx`.

Phase 0 scope: frozen contract behind a runnable stub endpoint. Real
SHAP/LIME computation is implemented in a later phase.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter

from app.models.common import APIResponse
from app.models.xai import (
    ConfidenceMatrixEntry,
    ExplanationRequest,
    ExplanationResponse,
    FeatureImpact,
    RootCauseSummary,
)

router = APIRouter(prefix="/xai", tags=["explainability"])


@router.post("/explain", response_model=APIResponse[ExplanationResponse])
def explain(payload: ExplanationRequest) -> APIResponse[ExplanationResponse]:
    """Contract-frozen stub — see module docstring."""
    local_importance = [
        FeatureImpact(feature_name="bearing_temp_c", impact_weight=0.34, feature_value=78.2, rank=1),
        FeatureImpact(feature_name="vibration_rms_mm_s", impact_weight=0.21, feature_value=4.1, rank=2),
        FeatureImpact(feature_name="motor_current_a", impact_weight=-0.08, feature_value=12.4, rank=3),
    ]
    root_cause = RootCauseSummary(
        headline="Elevated bearing temperature is the dominant failure driver.",
        narrative=(
            "[STUB] SHAP attribution indicates bearing_temp_c contributes the largest positive impact "
            "toward the failure classifier's output, consistent with early-stage bearing degradation."
        ),
        contributing_failure_modes=["failuremode-stub-1"],
    )
    response = ExplanationResponse(
        explanation_id=payload.explanation_id or str(uuid4()),
        asset_id=payload.asset_id,
        method=payload.method,
        scope=payload.scope,
        base_value=0.15,
        predicted_value=0.23,
        global_feature_importance=None,
        local_feature_importance=local_importance,
        root_cause=root_cause,
        confidence_matrix=[
            ConfidenceMatrixEntry(label="Bearing Overheat", confidence=0.82),
            ConfidenceMatrixEntry(label="Misalignment", confidence=0.11),
            ConfidenceMatrixEntry(label="Cavitation", confidence=0.07),
        ],
        model_name=payload.target_model_name,
    )
    return APIResponse[ExplanationResponse](data=response)
