"""
Phase 4 — Qdrant Vector Schema
Canonical collection & payload definitions for Industry 5.0 GraphRAG
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

# ---------------------------------------------------------------------------
# Collection catalog — mirrors Phase 0 qdrant_schema.md
# ---------------------------------------------------------------------------

class QdrantCollection(str, Enum):
    """Canonical Qdrant collection identifiers"""
    SOP_DOCS = "sop_documents"
    TECHNICAL_MANUALS = "technical_manuals"
    INCIDENT_REPORTS = "incident_reports"
    # unified operational knowledge collection (Phase 4 primary)
    OPERATIONAL_KNOWLEDGE = "operational_knowledge_v4"

# Default production collection
DEFAULT_COLLECTION = QdrantCollection.OPERATIONAL_KNOWLEDGE

# ---------------------------------------------------------------------------
# Embedding model catalog
# ---------------------------------------------------------------------------

class EmbeddingModelId(str, Enum):
    """Supported SentenceTransformer models with dimensions"""
    ALL_MINILM_L6_V2 = "sentence-transformers/all-MiniLM-L6-v2"  # 384d
    ALL_MPNET_BASE_V2 = "sentence-transformers/all-mpnet-base-v2"  # 768d - Phase 4 default
    BGE_LARGE_EN_V15 = "BAAI/bge-large-en-v1.5"  # 1024d

# Model → vector dimensions
EMBEDDING_DIMENSIONS: dict[str, int] = {
    EmbeddingModelId.ALL_MINILM_L6_V2.value: 384,
    EmbeddingModelId.ALL_MPNET_BASE_V2.value: 768,
    EmbeddingModelId.BGE_LARGE_EN_V15.value: 1024,
}

# Phase 4 production model
DEFAULT_EMBEDDING_MODEL = EmbeddingModelId.ALL_MPNET_BASE_V2.value
DEFAULT_VECTOR_DIM = EMBEDDING_DIMENSIONS[DEFAULT_EMBEDDING_MODEL]

# ---------------------------------------------------------------------------
# Distance metrics
# ---------------------------------------------------------------------------

QDRANT_DISTANCE_COSINE = "Cosine"
QDRANT_DISTANCE_DOT = "Dot"
QDRANT_DISTANCE_EUCLID = "Euclid"

DEFAULT_DISTANCE = QDRANT_DISTANCE_COSINE

# ---------------------------------------------------------------------------
# Payload schema — strict Phase 3 ChunkMetadata mapping
# ---------------------------------------------------------------------------

# Payload field names (must match ChunkMetadata + Phase 1 ontology)
PAYLOAD_FIELDS = {
    "chunk_id": "keyword",           # unique chunk primary key
    "document_id": "keyword",
    "document_type": "keyword",      # Manual, SOP, Log, SPEC_SHEET, INCIDENT_REPORT
    "asset_type": "keyword",         # PUMP, MOTOR, TURBINE, etc.
    "section_title": "text",         # searchable text
    "source_filename": "keyword",
    "chunk_index": "integer",
    "token_count": "integer",
    "char_count": "integer",
    "page_start": "integer",
    "page_end": "integer",
    "embedding_model": "keyword",
    "embedding_timestamp": "datetime",
    "hash": "keyword",
    "text": "text",                  # original chunk content — full-text preserved
}

# High-cardinality categorical fields requiring payload indexes
PAYLOAD_INDEXED_FIELDS = [
    "chunk_id",
    "document_id",
    "document_type",
    "asset_type",
    "source_filename",
]

# ---------------------------------------------------------------------------
# Search tuning
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 8
DEFAULT_SCORE_THRESHOLD = 0.70  # cosine similarity — reject low-confidence
MAX_TOP_K = 50

# HNSW tuning — production defaults
HNSW_CONFIG = {
    "m": 16,
    "ef_construct": 200,
}

# Optimizer
OPTIMIZERS_CONFIG = {
    "default_segment_number": 2,
    "memmap_threshold": 20000,
}

# ---------------------------------------------------------------------------
# Document type taxonomy — Phase 1 aligned
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    MANUAL = "MANUAL"
    SOP = "SOP"
    SPEC_SHEET = "SPEC_SHEET"
    MAINTENANCE_LOG = "MAINTENANCE_LOG"
    INCIDENT_REPORT = "INCIDENT_REPORT"

# Asset type passthrough — re-export for payload validation
# See app.models.common.AssetType
