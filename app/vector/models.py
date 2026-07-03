"""
Phase 4 — Vector search Pydantic models
Aligns with Phase 0 GraphRAG contracts (app/models/graphrag.py)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Payload — Qdrant point payload (mirrors ChunkMetadata)
# ---------------------------------------------------------------------------

class ChunkPayload(BaseModel):
    """Strict payload schema attached to every Qdrant vector point."""
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    chunk_id: str = Field(..., description="Primary key — matches Neo4j :TextChunk.chunk_id")
    document_id: str
    document_type: str = Field(..., description="MANUAL | SOP | SPEC_SHEET | MAINTENANCE_LOG | INCIDENT_REPORT")
    asset_type: Optional[str] = Field(None, description="PUMP | MOTOR | TURBINE | …")
    section_title: Optional[str] = None
    source_filename: Optional[str] = None
    chunk_index: int = 0
    token_count: Optional[int] = None
    char_count: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    text: str = Field(..., min_length=1, description="Original chunk content")
    embedding_model: Optional[str] = None
    embedding_timestamp: Optional[datetime] = None
    hash: Optional[str] = None

    @field_validator("document_type")
    @classmethod
    def normalize_doc_type(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# Search filters
# ---------------------------------------------------------------------------

class SearchFilters(BaseModel):
    """Metadata filtering for hybrid semantic + structured search."""
    model_config = ConfigDict(extra="forbid")

    document_type: Optional[List[str] | str] = None
    asset_type: Optional[List[str] | str] = None
    document_id: Optional[List[str] | str] = None
    source_filename: Optional[List[str] | str] = None
    section_title: Optional[str] = None
    chunk_ids: Optional[List[str]] = None
    # token / char range guards
    min_token_count: Optional[int] = None
    max_token_count: Optional[int] = None

    def is_empty(self) -> bool:
        return not any([
            self.document_type,
            self.asset_type,
            self.document_id,
            self.source_filename,
            self.section_title,
            self.chunk_ids,
            self.min_token_count,
            self.max_token_count,
        ])


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------

class VectorSearchResult(BaseModel):
    """Single dense retrieval hit."""
    model_config = ConfigDict(extra="forbid")

    id: str | int  # Qdrant point id
    score: float = Field(..., description="Cosine similarity 0-1")
    chunk_id: str
    document_id: str
    document_type: str
    asset_type: Optional[str] = None
    section_title: Optional[str] = None
    text: str
    token_count: Optional[int] = None
    chunk_index: Optional[int] = None
    source_filename: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        # Qdrant cosine returns 0..1 — clamp defensively
        return max(0.0, min(1.0, float(v)))


class VectorSearchResponse(BaseModel):
    """Envelope returned by VectorSearchService.semantic_search"""
    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int
    returned: int
    score_threshold: float
    latency_ms: float
    results: List[VectorSearchResult]
    filters_applied: Optional[SearchFilters] = None
    collection: str
    embedding_model: str
    total_candidates_scanned: Optional[int] = None


# ---------------------------------------------------------------------------
# Upsert / ingestion DTOs
# ---------------------------------------------------------------------------

class EmbeddingUpsertItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point_id: str | int
    vector: List[float]
    payload: ChunkPayload


class EmbeddingBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_requested: int
    embedded: int
    skipped_existing: int
    upserted: int
    failed: int
    latency_ms: float
    collection: str
    vector_dim: int
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GraphRAG compatibility layer
# Phase 0 contract re-export — ensures search_service maps perfectly
# ---------------------------------------------------------------------------

class GraphRagQueryRequest(BaseModel):
    """Phase 0 frozen GraphRAG query contract"""
    model_config = ConfigDict(extra="forbid")
    query_text: str = Field(..., min_length=1, max_length=2048)
    top_k: int = Field(8, ge=1, le=50)
    filters: Optional[SearchFilters] = None
    min_score: float = Field(0.70, ge=0.0, le=1.0)
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


class GraphRagQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Optional[str] = None
    context_chunks: List[GraphRagContextChunk] = Field(default_factory=list)
    graph_nodes_expanded: int = 0
    vector_hits: int = 0
    latency_ms: float = 0.0
    query_embedding_model: str = ""
