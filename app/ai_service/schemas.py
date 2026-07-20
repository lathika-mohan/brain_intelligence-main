"""Phase 9/10 — AI service request/response schemas.

This module defines the request/response models used by the Phase 10 AI router
and Phase 11 UI router. These are distinct from the Phase 1 common envelope
models in :mod:`app.ai_service.schemas`.

The models here include:
- Agent chat request/response models (AgentChatRequest, AgentChatResponse, etc.)
- AI router envelope models (AIHealthResponse, AgentAIEnvelope, etc.)
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Phase 1 Common Envelope (migrated from missing common.schemas)
# ---------------------------------------------------------------------------
T = TypeVar("T")


class UIAPIErrorPayload(BaseModel):
    """Strict error payload shape used by the Phase 1 response helper."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str = "AI_SERVICE_ERROR"
    message: str = "An unspecified error occurred."
    details: Optional[Any] = None


class UIAPIResponseEnvelope(BaseModel, Generic[T]):
    """Standard wire-level response envelope (Section 1.1)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    requestId: str = Field(..., alias="requestId")
    generatedAt: str = Field(..., alias="generatedAt")
    success: bool = True
    error: Optional[UIAPIErrorPayload] = None
    data: Optional[T] = None


def utc_now_iso() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Agent Chat Models (Phase 9/10)
# ---------------------------------------------------------------------------
class AgentRole(str, Enum):
    """Role of a chat message participant."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AgentChatMessage(BaseModel):
    """A single message in the agent chat conversation."""

    model_config = ConfigDict(extra="forbid")

    role: AgentRole
    content: str


class AgentStateName(str, Enum):
    """Semantic state names for the diagnostic agent workflow."""

    RECEIVED = "received"
    TRIAGED = "triaged"
    GRAPHRAG_RETRIEVED = "graphrag_retrieved"
    DECISION_EVALUATED = "decision_evaluated"
    FINAL = "final"
    ERROR = "error"


class AgentState(BaseModel):
    """A single state transition in the diagnostic agent workflow."""

    model_config = ConfigDict(extra="forbid")

    state: AgentStateName
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentChatRequest(BaseModel):
    """Request to run a diagnostic agent chat turn."""

    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = None
    asset_id: Optional[str] = None
    messages: List[AgentChatMessage]
    stream: bool = False
    include_graph_context: bool = True
    include_recommendations: bool = True


class AgentChatResponse(BaseModel):
    """Response from a diagnostic agent chat turn."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    asset_id: Optional[str] = None
    final_answer: str
    states: List[AgentState]


# ---------------------------------------------------------------------------
# AI Router Envelope Models (Phase 10)
# ---------------------------------------------------------------------------
class AIHealthResponse(BaseModel):
    """Health check response for the AI service."""

    model_config = ConfigDict(extra="forbid")

    module: Literal["ai-service"] = "ai-service"
    status: str
    version: str
    dependencies: Dict[str, Any]


class APIResponse(BaseModel):
    """Generic API response envelope."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    success: bool
    data: Optional[Any] = None
    request_id: str = Field(alias="requestId")
    error: Optional[Dict[str, Any]] = None


class GraphRagAIEnvelope(APIResponse):
    """GraphRAG query response envelope."""

    pass


class PredictiveAIEnvelope(APIResponse):
    """Predictive maintenance inference response envelope."""

    pass


class ExplainAIEnvelope(APIResponse):
    """Explainability (XAI) response envelope."""

    pass


class ExplainFetchResponse(BaseModel):
    """Explanation fetch response data."""

    model_config = ConfigDict(extra="forbid")

    prediction_id: str
    explanation: Any


class RecommendAIEnvelope(APIResponse):
    """Recommendation response envelope."""

    pass


class AgentAIEnvelope(APIResponse):
    """Agent chat response envelope."""

    pass