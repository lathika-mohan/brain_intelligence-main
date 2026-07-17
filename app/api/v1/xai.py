"""
Explainable AI (XAI) API endpoints Router.
"""
from __future__ import annotations

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.xai import ExplanationRequest, ExplanationResponse
from app.predictive.xai_service import get_xai_service, XaiService
from app.predictive.telemetry_simulator import generate_episode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/xai", tags=["Explainable AI"])

@router.post(
    "/explain",
    response_model=ExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute SHAP & LIME local or global explanations for a specific asset",
)
async def generate_explanation(
    request: ExplanationRequest,
    service: XaiService = Depends(get_xai_service),
) -> ExplanationResponse:
    """Generate contract-compliant operational feature explanations and root cause synthesis."""
    try:
        # Simulate / retrieve the required telemetry history for feature engineering
        # (Usually 24 frames are ideal to compute all rolling statistical window offsets)
        episode = generate_episode(asset_id=request.asset_id)
        history = episode.frames[:24]
        
        response = await service.explain(request, history)
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter configuration: {str(val_err)}"
        )
    except Exception as exc:
        logger.exception("XAI endpoint evaluation failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"XAI calculation failed: {str(exc)}"
        )
