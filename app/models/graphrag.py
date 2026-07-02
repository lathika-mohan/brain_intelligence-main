"""
GraphRAG Engine contracts — powers `src/components/GraphRagPanel.tsx`.

Fuses Qdrant vector-search context with a Neo4j knowledge sub-graph and a
synthesized natural-language answer, with citations traceable back to
source SOPs/manuals. This is the single richest contract in Phase 0 — the
frontend's `GraphRagPanel` renders every field below.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import AssetType, TimeRange, utc_now


class GraphTraversalDepth(int, Enum):
    SHALLOW = 1
    STANDARD = 2
    DEEP = 3


class GraphRagQueryRequest(BaseModel):
    """Search request issued by `GraphRagPanel.tsx` (or the Decision Engine internally)."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000, description="Natural-language operator query.")
    asset_ids: Optional[List[str]] = Field(
        default=None, description="Restrict search to these asset IDs; None = plant-wide."
    )
    asset_types: Optional[List[AssetType]] = Field(default=None)
    time_bounds: Optional[TimeRange] = Field(
        default=None, description="Restrict retrieved incidents/SOP revisions to this window."
    )
    traversal_depth: GraphTraversalDepth = Field(
        default=GraphTraversalDepth.STANDARD, description="Max graph hops from seed nodes."
    )
    top_k_vector: int = Field(default=8, ge=1, le=50, description="Vector chunks to retrieve pre-fusion.")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    include_graph_context: bool = Field(default=True)
    include_citations: bool = Field(default=True)


class VectorContextChunk(BaseModel):
    """One retrieved chunk from the Qdrant semantic layer."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    text: str = Field(..., description="Retrieved passage text.")
    source_document: str = Field(..., description="Originating SOP/manual filename or doc ID.")
    source_type: str = Field(
        default="SOP", description="'SOP' | 'MANUAL' | 'INCIDENT_REPORT' | 'MAINTENANCE_LOG'."
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity / rerank score.")
    page_number: Optional[int] = None


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str = Field(..., description="Neo4j node label, e.g. 'Asset', 'FailureMode', 'SOP'.")
    display_name: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relationship: str = Field(..., description="Relationship type, e.g. 'HAS_SENSOR', 'INDICATES_FAILURE'.")
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphContextMap(BaseModel):
    """Extracted knowledge sub-graph for the frontend's graph renderer."""

    model_config = ConfigDict(extra="forbid")

    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    root_node_ids: List[str] = Field(
        default_factory=list, description="Seed node(s) the traversal expanded from."
    )


class Citation(BaseModel):
    """Maps a specific claim in the synthesized answer back to a source."""

    model_config = ConfigDict(extra="forbid")

    citation_id: str
    claim_span: str = Field(..., description="The substring of the answer this citation supports.")
    source_document: str
    source_type: str = Field(default="SOP")
    source_node_id: Optional[str] = Field(
        default=None, description="Neo4j :SOP node ID if resolvable, for graph deep-link."
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class GraphRagQueryResponse(BaseModel):
    """Fusion payload rendered by `GraphRagPanel.tsx`."""

    model_config = ConfigDict(extra="forbid")

    query: str
    answer: str = Field(..., description="Synthesized natural-language answer.")
    vector_context: List[VectorContextChunk] = Field(default_factory=list)
    graph_context: Optional[GraphContextMap] = None
    citations: List[Citation] = Field(default_factory=list)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float = Field(..., ge=0.0)
    generated_at: datetime = Field(default_factory=utc_now)
