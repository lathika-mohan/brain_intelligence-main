"""
Prescriptive Decision Engine contracts.

Fuses Predictive Maintenance outputs (`predictive.py`) with GraphRAG
knowledge retrieval (`graphrag.py`) to produce prioritized, actionable
maintenance recommendations, each linked to a governing SOP.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ActionType(str, Enum):
    INSPECT = "INSPECT"
    LUBRICATE = "LUBRICATE"
    REPLACE_COMPONENT = "REPLACE_COMPONENT"
    RECALIBRATE = "RECALIBRATE"
    SCHEDULE_SHUTDOWN = "SCHEDULE_SHUTDOWN"
    MONITOR = "MONITOR"
    ESCALATE_TO_ENGINEER = "ESCALATE_TO_ENGINEER"


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    component_id: Optional[str] = None
    inference_id: Optional[str] = Field(
        default=None, description="Correlates to a prior InferenceResponse.explanation_id / asset context."
    )
    risk_horizon_days: int = Field(default=30, ge=1, le=365)
    max_recommendations: int = Field(default=5, ge=1, le=20)


class SOPLinkage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sop_id: str = Field(..., description="Neo4j :SOP.id.")
    title: str
    document_url: Optional[str] = None
    revision: Optional[str] = None


class PrescriptiveAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    action_type: ActionType
    description: str
    priority: RecommendationPriority
    risk_score_if_ignored: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated risk (0-1) of adverse outcome if this action is skipped."
    )
    estimated_cost_avoidance_usd: Optional[float] = Field(default=None, ge=0.0)
    recommended_completion_by: Optional[datetime] = None
    sop_linkage: Optional[SOPLinkage] = None
    supporting_explanation_id: Optional[str] = Field(
        default=None, description="Correlates to an ExplanationResponse.explanation_id."
    )


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    component_id: Optional[str] = None
    recommendations: List[PrescriptiveAction] = Field(default_factory=list)
    overall_risk_score: float = Field(..., ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=utc_now)
