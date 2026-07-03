"""Decision Engine contracts"""
from pydantic import BaseModel
from typing import List, Optional

class DecisionRecommendRequest(BaseModel):
    asset_id: str
    risk_horizon_days: int = 30
    max_recommendations: int = 5

class DecisionRecommendation(BaseModel):
    action: str
    rationale: str
    confidence: float
    priority: int

class DecisionRecommendResponse(BaseModel):
    asset_id: str
    recommendations: List[DecisionRecommendation]
