"""
Qdrant vector collection schema constants (Phase 0 — structural blueprint only).

Authoritative human-readable spec: `docs/qdrant_schema.md`. Keep in sync.
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings


class QdrantCollectionName(str, Enum):
    SOP_DOCUMENTS = "sop_documents"
    TECHNICAL_MANUALS = "technical_manuals"
    INCIDENT_REPORTS = "incident_reports"


class VectorPayloadSchema(BaseModel):
    """
    Canonical payload attached to every point across all three collections.
    Mirrors `VectorContextChunk` in `app.models.graphrag` minus the vector
    itself (Qdrant stores the embedding separately from the payload).
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    text: str
    source_document: str
    source_type: str  # "SOP" | "MANUAL" | "INCIDENT_REPORT" | "MAINTENANCE_LOG"
    asset_types: list[str] = []
    asset_ids: list[str] = []
    page_number: int | None = None
    revision: str | None = None
    ingested_at: str  # ISO-8601 timestamp string


def collection_config() -> dict:
    """
    Returns the {name: (size, distance)} config for all collections,
    derived from Settings so environment overrides propagate at bootstrap
    time (see scripts/init_qdrant_collections.py).
    """
    settings = get_settings()
    return {
        settings.qdrant_collection_sop_docs: {
            "size": settings.qdrant_vector_size,
            "distance": settings.qdrant_distance_metric,
        },
        settings.qdrant_collection_manuals: {
            "size": settings.qdrant_vector_size,
            "distance": settings.qdrant_distance_metric,
        },
        settings.qdrant_collection_incidents: {
            "size": settings.qdrant_vector_size,
            "distance": settings.qdrant_distance_metric,
        },
    }
