"""
Prescriptive Decision Engine router.

Phase 0 scope: frozen contract behind a runnable stub endpoint. Real
fusion of predictive + GraphRAG outputs into prioritized actions is
implemented in a later phase (likely via a LangGraph agent — see
`app/agents/`).
"""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter

from app.models.common import APIResponse, utc_now
from app.models.decision import (
    ActionType,
    PrescriptiveAction,
    RecommendationPriority,
    RecommendationRequest,
    RecommendationResponse,
    SOPLinkage,
)

router = APIRouter(prefix="/decision", tags=["decision-engine"])


@router.post("/recommend", response_model=APIResponse[RecommendationResponse])
def recommend(payload: RecommendationRequest) -> APIResponse[RecommendationResponse]:
    """Contract-frozen stub — see module docstring."""
    action = PrescriptiveAction(
        action_id=str(uuid4()),
        action_type=ActionType.LUBRICATE,
        description="[STUB] Reduce bearing lubrication interval to 14 days per SOP-114.",
        priority=RecommendationPriority.HIGH,
        risk_score_if_ignored=0.68,
        estimated_cost_avoidance_usd=15000.0,
        recommended_completion_by=utc_now() + timedelta(days=7),
        sop_linkage=SOPLinkage(
            sop_id="sop-stub-1",
            title="SOP-114: Bearing Lubrication & Maintenance",
            document_url="https://docs.iob.enterprise.internal/sop/114",
            revision="Rev. C",
        ),
        supporting_explanation_id=None,
    )
    response = RecommendationResponse(
        asset_id=payload.asset_id,
        component_id=payload.component_id,
        recommendations=[action][: payload.max_recommendations],
        overall_risk_score=0.68,
    )
    return APIResponse[RecommendationResponse](data=response)
