"""Phase 10 Pydantic v2 API schemas for the isolated AI service router.

The models below form the public `/api/v1/ai/*` integration boundary. They
compose the frozen Phase 0 domain contracts already implemented in
``app.models.*`` and add endpoint-specific OpenAPI examples for Member 1/4.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import APIResponse, utc_now
from app.models.decision import RecommendationRequest, RecommendationResponse
from app.models.graphrag import GraphRagQueryRequest, GraphRagQueryResponse
from app.models.predictive import InferenceRequest, InferenceResponse
from app.models.xai import ExplanationResponse


class AIHealthResponse(BaseModel):
    """Lightweight module readiness contract."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "degraded"] = Field(..., examples=["ready"])
    module: str = Field(default="ai-service", examples=["ai-service"])
    version: str = Field(..., examples=["0.10.0"])
    dependencies: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=utc_now)


class ExplainFetchResponse(BaseModel):
    """Response wrapper for GET /ai/explain/{prediction_id}."""

    model_config = ConfigDict(extra="forbid")

    prediction_id: str = Field(..., examples=["pred-p101a-20260707T071500Z"])
    explanation: ExplanationResponse


class AgentRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentChatMessage(BaseModel):
    """One multi-turn diagnostic chat message."""

    model_config = ConfigDict(extra="forbid")

    role: AgentRole = Field(..., examples=["user"])
    content: str = Field(..., min_length=1, max_length=4096, examples=["Why is pump P-101A vibrating?"])
    timestamp: Optional[datetime] = Field(default=None, examples=["2026-07-07T07:15:00Z"])


class AgentChatRequest(BaseModel):
    """Request for the Phase 9 LangGraph diagnostic agent endpoint."""

    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = Field(default=None, examples=["sess-maint-001"])
    asset_id: Optional[str] = Field(default=None, examples=["P-101A"])
    messages: List[AgentChatMessage] = Field(
        ...,
        min_length=1,
        examples=[[{"role": "user", "content": "Diagnose elevated bearing temperature on P-101A."}]],
    )
    stream: bool = Field(default=False, description="When true, returns newline-delimited structured agent states.")
    include_graph_context: bool = Field(default=True)
    include_recommendations: bool = Field(default=True)


class AgentStateName(str, Enum):
    RECEIVED = "received"
    TRIAGED = "triaged"
    GRAPHRAG_RETRIEVED = "graphrag_retrieved"
    DECISION_EVALUATED = "decision_evaluated"
    FINAL = "final"


class AgentState(BaseModel):
    """One emitted LangGraph-style state transition."""

    model_config = ConfigDict(extra="forbid")

    state: AgentStateName = Field(..., examples=["graphrag_retrieved"])
    message: str = Field(..., examples=["Retrieved graph and vector context for the active anomaly."])
    payload: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=utc_now)


class AgentChatResponse(BaseModel):
    """Non-streaming structured agent response."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., examples=["sess-maint-001"])
    asset_id: Optional[str] = Field(default=None, examples=["P-101A"])
    final_answer: str = Field(..., examples=["P-101A shows a likely bearing lubrication issue..."])
    states: List[AgentState] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


GraphRagAIEnvelope = APIResponse[GraphRagQueryResponse]
PredictiveAIEnvelope = APIResponse[InferenceResponse]
ExplainAIEnvelope = APIResponse[ExplainFetchResponse]
RecommendAIEnvelope = APIResponse[RecommendationResponse]
AgentAIEnvelope = APIResponse[AgentChatResponse]
