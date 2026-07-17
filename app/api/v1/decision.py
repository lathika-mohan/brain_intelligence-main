"""
Phase 8 — AI Decision Engine API Router.

Exposes the frozen Phase 0 contract endpoint
``POST /api/v1/decision/recommend`` (``docs/api_contracts.md`` §4) that
powers the (future) prescriptive-action panel on the frontend.

The router:
  • Accepts ``RecommendationRequest`` (frozen contract)
  • Calls ``DecisionService.recommend()`` for the full rule/risk/SOP pipeline
  • Wraps the response in ``APIResponse[RecommendationResponse]``
  • Exposes health + rule-catalogue diagnostics endpoints

No frontend modification is required or performed — the payload conforms
exactly to the contract documented in ``docs/api_contracts.md`` §4.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.decision.decision_service import DecisionService, get_decision_service
from app.decision.risk_scorer import SEVERITY_TIER_SCALE
from app.decision.rule_engine import CRITICALITY_WEIGHTS
from app.models.common import APIResponse
from app.models.decision import RecommendationRequest, RecommendationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision", tags=["decision"])


# ---------------------------------------------------------------------------
# POST /api/v1/decision/recommend — main prescriptive endpoint
# ---------------------------------------------------------------------------


@router.post("/recommend", response_model=APIResponse[RecommendationResponse])
async def decision_recommend(body: RecommendationRequest) -> APIResponse[RecommendationResponse]:
    """Generate prioritized, risk-managed, SOP-backed prescriptive actions.

    Orchestrates Phase 6 predictions + Phase 7 explanations through the
    Phase 8 rule engine / risk scorer / SOP matcher and returns the frozen
    ``RecommendationResponse`` contract, additively enriched with
    ``sop_steps`` and an auditable ``decision_log``.
    """
    request_id = str(uuid.uuid4())
    try:
        service: DecisionService = get_decision_service()
        result = await service.recommend(body)
        return APIResponse(success=True, data=result, error=None, request_id=request_id)
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.exception("Decision recommendation failed")
        raise HTTPException(status_code=500, detail=f"Decision recommendation failed: {e}")


# ---------------------------------------------------------------------------
# GET /api/v1/decision/health — engine status
# ---------------------------------------------------------------------------


@router.get("/health")
async def decision_health() -> Dict[str, Any]:
    """Report the rule/weight configuration currently active."""
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "status": "ready",
        "severity_thresholds_days": {
            "imminent_rul_days": settings.decision_engine_imminent_rul_days,
            "scheduled_rul_days": settings.decision_engine_scheduled_rul_days,
        },
        "failure_probability_thresholds": {
            "imminent": settings.decision_engine_imminent_probability,
            "scheduled": settings.decision_engine_scheduled_probability,
        },
        "criticality_weights": CRITICALITY_WEIGHTS,
        "severity_tier_fmea_scale": SEVERITY_TIER_SCALE,
        "rpn_ceiling": settings.decision_engine_rpn_ceiling,
    }
