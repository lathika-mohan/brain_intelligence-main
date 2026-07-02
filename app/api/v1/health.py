"""Health & readiness endpoints — used by Member 1's gateway for liveness probes."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.graph.client import verify_connectivity as neo4j_ok
from app.vector.client import verify_connectivity as qdrant_ok

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe — always 200 if the process is up."""
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.get("/health/ready")
def readiness() -> dict:
    """
    Readiness probe — checks downstream dependencies.
    Returns 200 with per-dependency booleans regardless of their state so
    orchestrators can inspect *which* dependency is down instead of just
    getting a blanket 503.
    """
    neo4j_status = neo4j_ok()
    qdrant_status = qdrant_ok()
    return {
        "status": "ready" if (neo4j_status and qdrant_status) else "degraded",
        "dependencies": {
            "neo4j": "up" if neo4j_status else "down",
            "qdrant": "up" if qdrant_status else "down",
        },
    }
