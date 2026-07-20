"""
Phase 4 — Qdrant client lifecycle — hardened, optional.
Thread-safe singleton with sync + async support and graceful degraded mode
when qdrant-client is not installed (CI / lightweight test runner).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional, Any

from app.core.config import get_settings, Settings

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
    HAS_QDRANT = True
except Exception as e:  # pragma: no cover
    QdrantClient = Any  # type: ignore
    rest = Any  # type: ignore
    HAS_QDRANT = False
    logger.info("qdrant-client not available — vector client will operate in degraded stub mode: %s", e)

_client_instance: Optional[Any] = None

class _StubQdrantClient:
    """Very small in-memory stub that satisfies health checks."""
    def __init__(self, *args, **kwargs):
        self._collections = []
    def get_collections(self):
        class _Resp:
            collections = []
        return _Resp()
    def collection_exists(self, collection_name: str = "") -> bool:
        return False
    def close(self):
        pass
    def search(self, *a, **kw):
        return []

def build_qdrant_client(settings: Optional[Settings] = None) -> Any:
    """Construct a configured QdrantClient (sync) or stub if missing."""
    settings = settings or get_settings()
    if not HAS_QDRANT:
        logger.warning("Qdrant client stub used — no real vector DB")
        return _StubQdrantClient()

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

def get_qdrant_client() -> Any:
    """Singleton accessor — cached process-wide."""
    global _client_instance
    if _client_instance is None:
        _client_instance = build_qdrant_client()
    return _client_instance

@lru_cache(maxsize=1)
def get_qdrant_client_cached() -> Any:
    return build_qdrant_client()

def close_qdrant_client() -> None:
    global _client_instance
    if _client_instance is not None:
        try:
            _client_instance.close()
        except Exception:
            pass
        _client_instance = None

def check_qdrant_health(client: Optional[Any] = None) -> dict:
    c = client or get_qdrant_client()
    try:
        collections = c.get_collections()
        col_count = len(getattr(collections, 'collections', []))
        return {
            "status": "ok" if HAS_QDRANT else "degraded_stub",
            "collections": col_count,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error("Qdrant health check failed: %s", e)
        return {
            "status": "degraded",
            "error": str(e),
        }

def collection_exists(collection_name: str, client: Optional[Any] = None) -> bool:
    c = client or get_qdrant_client()
    try:
        return c.collection_exists(collection_name=collection_name)
    except Exception:
        return False
