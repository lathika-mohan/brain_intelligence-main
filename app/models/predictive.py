"""Predictive Maintenance contracts — Phase 0 stub"""
from pydantic import BaseModel, Field
from typing import Optional, List

class PredictiveInferRequest(BaseModel):
    asset_id: str
    horizon_hours: int = 24

class PredictiveInferResponse(BaseModel):
    asset_id: str
    rul_hours: Optional[float] = None
    failure_probability: float = 0.0
    anomaly_score: float = 0.0
    confidence: float = 0.0
