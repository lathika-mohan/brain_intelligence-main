"""
Phase 9 — strict state and wire contracts for the multi-agent orchestrator.

The orchestrator keeps a single Pydantic-backed state object that can be passed
through LangGraph nodes, serialized for audit traces, and projected back into
Phase 0/6/7/8 response contracts for Member 4/API consumers.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import utc_now
from app.models.decision import RecommendationResponse
from app.models.graphrag import GraphRagContextChunk, GraphRagEdge, GraphRagNode, GraphRagQueryResponse
from app.models.predictive import InferenceResponse
from app.models.telemetry import TelemetryReading
from app.models.xai import ExplanationResponse


class AgentName(str, Enum):
    SUPERVISOR = "supervisor"
    KNOWLEDGE = "knowledge_agent"
    RETRIEVAL = "retrieval_agent"
    PREDICTION = "prediction_agent"
    EXPLANATION = "explanation_agent"
    DECISION = "decision_agent"
    FINALIZER = "finalizer"
    END = "end"


class AgentError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    error_type: str
    message: str
    retry_count: int = 0
    recoverable: bool = True
    occurred_at: datetime = Field(default_factory=utc_now)


class TokenMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    total_estimated_tokens: int = 0
    max_context_tokens: int = 12000
    compression_events: int = 0


class AgentTraceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: str
    transition_index: int
    status: str = "ok"
    note: Optional[str] = None
    entered_at: datetime = Field(default_factory=utc_now)


class OrchestratorRequest(BaseModel):
    """Backend-only Phase 9 unified execution request."""

    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(..., min_length=1, max_length=4096)
    asset_id: Optional[str] = None
    component_id: Optional[str] = None
    top_k: int = Field(default=8, ge=1, le=50)
    risk_horizon_days: int = Field(default=30, ge=1, le=365)
    max_recommendations: int = Field(default=5, ge=1, le=20)
    telemetry_history: List[TelemetryReading] = Field(default_factory=list)
    max_transitions: int = Field(default=15, ge=3, le=50)
    include_debug_trace: bool = True


class AgentState(BaseModel):
    """Global state shared by all Phase 9 specialized agents."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    request_id: str
    query_text: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)

    # Routing / memory
    active_asset_id: Optional[str] = None
    component_id: Optional[str] = None
    active_agent: AgentName = AgentName.SUPERVISOR
    route_plan: List[AgentName] = Field(default_factory=list)
    visited_nodes: List[str] = Field(default_factory=list)
    trace: List[AgentTraceStep] = Field(default_factory=list)
    transition_count: int = 0
    max_transitions: int = 15
    terminal: bool = False

    # Operator/request parameters
    top_k: int = 8
    risk_horizon_days: int = 30
    max_recommendations: int = 5
    telemetry_history: List[TelemetryReading] = Field(default_factory=list)

    # Agent outputs
    context_chunks: List[GraphRagContextChunk] = Field(default_factory=list)
    graph_nodes: List[GraphRagNode] = Field(default_factory=list)
    graph_edges: List[GraphRagEdge] = Field(default_factory=list)
    prediction: Optional[InferenceResponse] = None
    explanation: Optional[ExplanationResponse] = None
    decision: Optional[RecommendationResponse] = None
    graphrag: Optional[GraphRagQueryResponse] = None

    # Guardrails / diagnostics
    anomaly_flags: List[Dict[str, Any]] = Field(default_factory=list)
    current_anomaly: bool = False
    model_predictions: Dict[str, Any] = Field(default_factory=dict)
    intermediate_payloads: Dict[str, Any] = Field(default_factory=dict)
    token_metrics: TokenMetrics = Field(default_factory=TokenMetrics)
    errors: List[AgentError] = Field(default_factory=list)
    retries: Dict[str, int] = Field(default_factory=dict)

    # Final answer
    answer: Optional[str] = None
    confidence: float = 0.0
    generated_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_request(cls, request: OrchestratorRequest, request_id: str) -> "AgentState":
        return cls(
            request_id=request_id,
            query_text=request.query_text,
            messages=[{"role": "user", "content": request.query_text}],
            active_asset_id=request.asset_id,
            component_id=request.component_id,
            top_k=request.top_k,
            risk_horizon_days=request.risk_horizon_days,
            max_recommendations=request.max_recommendations,
            telemetry_history=request.telemetry_history,
            max_transitions=request.max_transitions,
        )

    def append_trace(self, node: str, status: str = "ok", note: Optional[str] = None) -> None:
        self.transition_count += 1
        self.visited_nodes.append(node)
        self.trace.append(
            AgentTraceStep(
                node=node,
                transition_index=self.transition_count,
                status=status,
                note=note,
            )
        )

    def estimate_tokens(self) -> None:
        payload = self.model_dump(mode="json", exclude={"telemetry_history"})
        approx = max(len(str(payload)) // 4, 1)
        self.token_metrics.estimated_input_tokens = approx
        self.token_metrics.estimated_output_tokens = max(len(self.answer or "") // 4, 0)
        self.token_metrics.total_estimated_tokens = (
            self.token_metrics.estimated_input_tokens + self.token_metrics.estimated_output_tokens
        )

    def compress(self) -> None:
        """Prune large transient state while preserving final contracts and trace."""
        before = self.token_metrics.total_estimated_tokens
        self.messages = self.messages[-10:]
        self.context_chunks = self.context_chunks[:8]
        self.graph_nodes = self.graph_nodes[:50]
        self.graph_edges = self.graph_edges[:75]
        self.telemetry_history = self.telemetry_history[-24:]
        self.intermediate_payloads = {
            key: value for key, value in list(self.intermediate_payloads.items())[-8:]
        }
        self.estimate_tokens()
        if self.token_metrics.total_estimated_tokens < before or before == 0:
            self.token_metrics.compression_events += 1


class OrchestratorResponse(BaseModel):
    """Unified response produced by the Phase 9 finalizer."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    answer: str
    active_asset_id: Optional[str] = None
    component_id: Optional[str] = None
    confidence: float = 0.0
    route_taken: List[str] = Field(default_factory=list)
    trace: List[AgentTraceStep] = Field(default_factory=list)
    errors: List[AgentError] = Field(default_factory=list)
    token_metrics: TokenMetrics = Field(default_factory=TokenMetrics)

    # Phase-contract projections
    graphrag: Optional[GraphRagQueryResponse] = None
    prediction: Optional[InferenceResponse] = None
    explanation: Optional[ExplanationResponse] = None
    decision: Optional[RecommendationResponse] = None

    generated_at: datetime = Field(default_factory=utc_now)
