"""
Pydantic models for Phase 5A gateway - compatible with both orchestrator and frontend.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponseData(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600

class FlexibleInferRequest(BaseModel):
    """Accepts both orchestrator style {asset_id, features{}} and AI service style {asset_id, history[]}"""
    asset_id: str = Field(..., min_length=1)
    features: Optional[Dict[str, float]] = None
    vibration: Optional[float] = None
    temperature: Optional[float] = None
    history: Optional[List[Dict[str, Any]]] = None
    component_id: Optional[str] = None
    horizon_hours: int = 24

    model_config = {"extra": "allow"}

class GraphRagQueryFlexible(BaseModel):
    """Accepts message, query_text, query"""
    message: Optional[str] = None
    query_text: Optional[str] = None
    query: Optional[str] = None
    top_k: int = 8
    min_score: float = 0.55
    max_graph_hops: int = 2
    asset_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    include_telemetry: bool = True

    model_config = {"extra": "allow"}

    def get_query(self) -> str:
        return self.message or self.query_text or self.query or "Show operational baseline"

class AlarmInjectRequest(BaseModel):
    asset_id: str
    metric: str
    value: float

    model_config = {"extra": "allow"}
