"""
Phase 6 — Predictive Maintenance API Router.

Exposes the Phase 0 contract endpoint ``POST /api/v1/predictive/infer``
that powers ``src/components/DigitalTwinView.tsx``.

The router:
  • Accepts ``InferenceRequest`` (frozen contract — wraps TelemetryReading frames)
  • Calls ``PredictionService.infer()`` for the async dual-model pipeline
  • Wraps the response in ``APIResponse[InferenceResponse]``
  • Maps contract violations to HTTP 422 and missing artifacts to HTTP 503
  • Exposes health + evaluation-report diagnostics endpoints

No frontend modification is required — the payload conforms exactly to the
contract documented in ``docs/api_contracts.md`` §2.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.models.common import APIResponse
from app.models.predictive import InferenceRequest, InferenceResponse
from app.predictive.feature_engineering import TelemetryContractError
from app.predictive.model_registry import get_model_registry
from app.predictive.prediction_service import (
    PredictionServiceUnavailable,
    get_prediction_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictive", tags=["predictive"])


# ---------------------------------------------------------------------------
# POST /api/v1/predictive/infer — main inference endpoint
# ---------------------------------------------------------------------------

@router.post("/infer", response_model=APIResponse[InferenceResponse])
async def predictive_infer(body: InferenceRequest) -> APIResponse[InferenceResponse]:
    """Run real-time RUL + anomaly inference over live telemetry frames."""
    request_id = str(uuid.uuid4())
    try:
        service = get_prediction_service()
        result = await service.infer(body)
        return APIResponse(success=True, data=result, error=None, request_id=request_id)
    except TelemetryContractError as tce:
        logger.warning("Telemetry contract violation: %s", tce)
        raise HTTPException(status_code=422, detail=str(tce))
    except PredictionServiceUnavailable as psu:
        logger.error("Prediction service unavailable: %s", psu)
        raise HTTPException(status_code=503, detail=str(psu))
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.exception("Predictive inference failed")
        raise HTTPException(status_code=500, detail=f"Predictive inference failed: {e}")


# ---------------------------------------------------------------------------
# GET /api/v1/predictive/health — engine + artifact status
# ---------------------------------------------------------------------------

@router.get("/health")
async def predictive_health() -> Dict[str, Any]:
    registry = get_model_registry()
    available = registry.artifacts_available()
    report = registry.load_report() if available else None
    return {
        "status": "ready" if available else "degraded_fallback",
        "artifacts_available": available,
        "registry_path": str(registry.path),
        "rul_model": registry.rul_model_path.name,
        "anomaly_model": registry.anomaly_model_path.name,
        "last_trained_at": report.trained_at.isoformat() if report else None,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/predictive/evaluation — latest evaluation report
# ---------------------------------------------------------------------------

@router.get("/evaluation")
async def predictive_evaluation() -> Dict[str, Any]:
    registry = get_model_registry()
    report = registry.load_report()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No evaluation report found. Train models first: "
                "`python -m app.predictive.train_predictive_models`."
            ),
        )
    return report.model_dump(mode="json")
