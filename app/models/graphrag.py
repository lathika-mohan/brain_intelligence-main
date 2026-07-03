"""
Phase 0 — GraphRAG Engine contracts
Restored in Phase 3 / Phase 4 for integration verification
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from .common import APIResponse

class GraphRagQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_text: str = Field(..., min_length=1, max_length=2048)
    top_k: int = Field(8, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None
    min_score: float = Field(0.55, ge=0.0, le=1.0)
    max_graph_hops: int = Field(2, ge=0, le=5)
    include_telemetry: bool = True
    asset_id: Optional[str] = None

class GraphRagContextChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    text: str
    score: float
    document_type: str
    source: Optional[str] = None

class GraphRagNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class GraphRagEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    relationship: str
    weight: float = 1.0

class GraphRagQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Optional[str] = None
    context_chunks: List[GraphRagContextChunk] = Field(default_factory=list)
    graph_nodes: List[GraphRagNode] = Field(default_factory=list)
    graph_edges: List[GraphRagEdge] = Field(default_factory=list)
    graph_nodes_expanded: int = 0
    vector_hits: int = 0
    latency_ms: float = 0.0
    query_embedding_model: str = ""

class GraphRagQueryEnvelope(APIResponse[GraphRagQueryResponse]):
    pass
