"""
Phase 0 / Phase 5 — GraphRAG Engine contracts
Frozen API contracts + internal graph context models.

Phase 0 contracts (GraphRagQueryRequest, GraphRagQueryResponse, etc.) are
the frozen, public API surface.  The internal GraphNode / GraphEdge /
GraphContextMap models are used by the Phase 2 graph_services layer and
consumed internally by the Phase 5 fusion engine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import APIResponse


# ---------------------------------------------------------------------------
# Phase 0 — Public API contracts (frozen)
# ---------------------------------------------------------------------------

class GraphRagQueryRequest(BaseModel):
    """Frozen Phase 0 request contract for POST /api/v1/graphrag/query."""

    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(..., min_length=1, max_length=2048)
    top_k: int = Field(8, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None
    min_score: float = Field(0.55, ge=0.0, le=1.0)
    max_graph_hops: int = Field(2, ge=0, le=5)
    include_telemetry: bool = True
    asset_id: Optional[str] = None


class GraphRagContextChunk(BaseModel):
    """A single vector-retrieved context chunk with provenance."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    text: str
    score: float
    document_type: str
    source: Optional[str] = None


class GraphRagNode(BaseModel):
    """Graph node surfaced in the GraphRAG response payload."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphRagEdge(BaseModel):
    """Graph edge surfaced in the GraphRAG response payload."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relationship: str
    weight: float = 1.0


class Citation(BaseModel):
    """A single citation linking a claim span to a source."""

    model_config = ConfigDict(extra="forbid")

    citation_id: str
    claim_span: str = ""
    source_document: Optional[str] = None
    source_type: Optional[str] = None
    source_node_id: Optional[str] = None
    confidence_score: float = 0.0
    page_number: Optional[int] = None
    url: Optional[str] = None


class GraphRagQueryResponse(BaseModel):
    """Frozen Phase 0 response contract — returned inside APIResponse[data]."""

    model_config = ConfigDict(extra="forbid")

    answer: Optional[str] = None
    context_chunks: List[GraphRagContextChunk] = Field(default_factory=list)
    graph_nodes: List[GraphRagNode] = Field(default_factory=list)
    graph_edges: List[GraphRagEdge] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    overall_confidence: float = 0.0
    graph_nodes_expanded: int = 0
    vector_hits: int = 0
    latency_ms: float = 0.0
    query_embedding_model: str = ""
    generated_at: Optional[str] = None


class GraphRagQueryEnvelope(APIResponse[GraphRagQueryResponse]):
    """Convenience alias — APIResponse[GraphRagQueryResponse]."""

    pass


# ---------------------------------------------------------------------------
# Internal graph context models (used by Phase 2 graph_services & Phase 5 engine)
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """Internal graph node representation (Phase 2 graph traversal)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    display_name: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Internal graph edge representation (Phase 2 graph traversal)."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relationship: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphContextMap(BaseModel):
    """Sub-graph context map returned by the Phase 2 traversal layer."""

    model_config = ConfigDict(extra="forbid")

    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    root_node_ids: List[str] = Field(default_factory=list)
