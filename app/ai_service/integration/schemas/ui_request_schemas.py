"""Validated request contracts for the Phase 11 UI router.

The UI accepts both the established snake_case gateway fields and camelCase
browser fields, while route handlers consume one typed, normalized API.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

class _UIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

class UIGraphRAGQueryRequest(_UIRequest):
    query_text: Optional[str] = Field(default=None, validation_alias=AliasChoices("query_text", "queryText", "query"))
    asset_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("asset_id", "assetId"))
    top_k: int = Field(default=5, ge=1, le=50, validation_alias=AliasChoices("top_k", "topK"))
    def resolved_query_text(self) -> str: return (self.query_text or "").strip()
    def resolved_asset_id(self) -> Optional[str]: return self.asset_id

class UIRecommendationRequest(_UIRequest):
    asset_id: str = Field(validation_alias=AliasChoices("asset_id", "assetId"), min_length=1)
    component_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("component_id", "componentId"))
    risk_horizon_days: int = Field(default=14, ge=1, le=365, validation_alias=AliasChoices("risk_horizon_days", "riskHorizonDays"))
    max_recommendations: int = Field(default=5, ge=1, le=50, validation_alias=AliasChoices("max_recommendations", "maxRecommendations"))
    def resolved_asset_id(self) -> str: return self.asset_id
    def resolved_component_id(self) -> Optional[str]: return self.component_id
    def resolved_risk_horizon(self) -> int: return self.risk_horizon_days
    def resolved_max_rec(self) -> int: return self.max_recommendations

class UIChatMessage(_UIRequest):
    role: str
    content: str

class _AgentRequest(_UIRequest):
    session_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("session_id", "sessionId"))
    asset_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("asset_id", "assetId"))
    messages: List[UIChatMessage] = Field(default_factory=list)
    include_graph_context: bool = Field(default=True, validation_alias=AliasChoices("include_graph_context", "includeGraphContext"))
    include_recommendations: bool = Field(default=True, validation_alias=AliasChoices("include_recommendations", "includeRecommendations"))
    def resolved_session_id(self) -> Optional[str]: return self.session_id
    def resolved_asset_id(self) -> Optional[str]: return self.asset_id
    def resolved_include_graph(self) -> bool: return self.include_graph_context
    def resolved_include_recs(self) -> bool: return self.include_recommendations

class UIAgentChatRequest(_AgentRequest):
    pass
class UIAgentChatStreamRequest(_AgentRequest):
    pass
