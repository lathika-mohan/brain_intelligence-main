"""
Phase 4 — Embedding & Semantic Search Vector Module

Member 3 (AI & Knowledge Engineer)
Industry 5.0 Enterprise Team — IOB AI Intelligence Platform

Provides:
- embedding_engine: SentenceTransformer orchestration
- qdrant_manager: collection lifecycle & payload indexing
- search_service: high-performance semantic retrieval
- pipeline: idempotent vector ingestion
"""

__version__ = "4.0.0"
__phase__ = "Phase 4 — Embedding & Semantic Search"

from .embedding_engine import EmbeddingEngine, get_embedding_engine
from .qdrant_manager import QdrantCollectionManager
from .search_service import VectorSearchService, get_search_service
from .models import (
    VectorSearchResult,
    VectorSearchResponse,
    SearchFilters,
    ChunkPayload,
)

__all__ = [
    "EmbeddingEngine",
    "get_embedding_engine",
    "QdrantCollectionManager",
    "VectorSearchService",
    "get_search_service",
    "VectorSearchResult",
    "VectorSearchResponse",
    "SearchFilters",
    "ChunkPayload",
]
