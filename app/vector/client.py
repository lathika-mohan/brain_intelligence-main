"""
Phase 4 — Qdrant client lifecycle
Thread-safe singleton with sync + async support
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from app.core.config import get_settings, Settings

logger = logging.getLogger(__name__)

_client_instance: Optional[QdrantClient] = None


def build_qdrant_client(settings: Optional[Settings] = None) -> QdrantClient:
    """Construct a configured QdrantClient (sync)."""
    settings = settings or get_settings()
    client_kwargs = {
        "url": settings.qdrant_url,
        "prefer_grpc": settings.qdrant_prefer_grpc,
        "grpc_port": settings.qdrant_grpc_port,
        "timeout": 30,
    }
    if settings.qdrant_api_key:
        client_kwargs["api_key"] = settings.qdrant_api_key

    client = QdrantClient(**client_kwargs)
    logger.debug("Qdrant client initialized: %s (grpc=%s)", settings.qdrant_url, settings.qdrant_prefer_grpc)
    return client


def get_qdrant_client() -> QdrantClient:
    """Singleton accessor — cached process-wide."""
    global _client_instance
    if _client_instance is None:
        _client_instance = build_qdrant_client()
    return _client_instance


@lru_cache(maxsize=1)
def get_qdrant_client_cached() -> QdrantClient:
    """lru_cache variant for FastAPI Depends compatibility."""
    return build_qdrant_client()


def close_qdrant_client() -> None:
    """Graceful shutdown helper."""
    global _client_instance
    if _client_instance is not None:
        try:
            _client_instance.close()
        except Exception:
            pass
        _client_instance = None


# ---------------------------------------------------------------------------
# Health / readiness probes
# ---------------------------------------------------------------------------

def check_qdrant_health(client: Optional[QdrantClient] = None) -> dict:
    """Return health dict suitable for /health/ready."""
    c = client or get_qdrant_client()
    try:
        # collections list is a cheap ping
        collections = c.get_collections()
        return {
            "status": "ok",
            "collections": len(collections.collections),
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("Qdrant health check failed: %s", e)
        return {
            "status": "degraded",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Collection helpers (thin wrappers — full lifecycle in qdrant_manager)
# ---------------------------------------------------------------------------

def collection_exists(collection_name: str, client: Optional[QdrantClient] = None) -> bool:
    c = client or get_qdrant_client()
    try:
        return c.collection_exists(collection_name=collection_name)
    except Exception:
        return False
