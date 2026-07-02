"""
Qdrant connectivity wrapper (Phase 0 — thin client lifecycle only).

No embedding / retrieval logic lives here yet — that belongs to the
GraphRAG pipeline in a later phase. This module's Phase-0 job is: expose
a cached `QdrantClient` singleton and a health-check helper.
"""
from __future__ import annotations

import logging
from typing import Optional

from qdrant_client import QdrantClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            prefer_grpc=settings.qdrant_prefer_grpc,
        )
        logger.info("Qdrant client initialized for %s", settings.qdrant_url)
    return _client


def verify_connectivity() -> bool:
    """Used by the /health endpoint. Returns False (not raises) on failure."""
    try:
        get_client().get_collections()
        return True
    except Exception as exc:  # noqa: BLE001 — health check must not raise
        logger.warning("Qdrant connectivity check failed: %s", exc)
        return False
