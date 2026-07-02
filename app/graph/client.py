"""
Neo4j connectivity wrapper (Phase 0 — thin driver lifecycle only).

No Cypher query logic / graph algorithms are implemented here. This
module's sole Phase 0 responsibility is: establish a verifiable
connection to Neo4j using settings from `app.core.config`, and expose a
session factory for later phases (GraphRAG traversal, PdM graph writes)
to build on.
"""
from __future__ import annotations

import logging
from typing import Optional

from neo4j import Driver, GraphDatabase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_driver: Optional[Driver] = None


def get_driver() -> Driver:
    """Lazily construct and cache the Neo4j driver singleton."""
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_lifetime=settings.neo4j_max_connection_lifetime,
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
            connection_timeout=settings.neo4j_connection_timeout,
        )
        logger.info("Neo4j driver initialized for %s", settings.neo4j_uri)
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


def verify_connectivity() -> bool:
    """Used by the /health endpoint. Returns False (not raises) on failure."""
    try:
        get_driver().verify_connectivity()
        return True
    except Exception as exc:  # noqa: BLE001 — health check must not raise
        logger.warning("Neo4j connectivity check failed: %s", exc)
        return False
