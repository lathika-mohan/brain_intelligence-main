"""
Neo4j connection lifecycle manager (Phase 2 — Database Initialization).

Implements a single, thread-safe, async driver singleton backed by the
official ``neo4j`` 5.x async driver. Responsibilities:

* Lazily construct the driver from the Phase 0 :class:`~app.core.config.Settings`
  environment contract (``NEO4J_URI`` / ``NEO4J_USER`` / ``NEO4J_PASSWORD`` ...).
* Connection-pool sizing, lifetime, and acquisition-timeout configuration.
* Startup connectivity verification with bounded exponential-backoff retry.
* A clean ``async`` close path so test fixtures and process shutdown can
  release the pool deterministically.

The async driver is preferred over the sync driver because the Phase 2
repository/service layer is explicitly asynchronous (per the Phase 2 spec).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Default retry budget. The Phase 0 contract exposes the connection *timeout*
# but not a retry count, so we keep a sensible default here and treat it as a
# tunable constant rather than a hidden magic number.
DEFAULT_CONNECTION_RETRIES = 5
DEFAULT_MAX_BACKOFF_SECONDS = 8.0


class Neo4jConnectionError(RuntimeError):
    """Raised when the driver cannot be established after exhausting retries."""


def _driver_config() -> dict:
    """Translate :class:`Settings` into neo4j async-driver configuration."""
    settings = get_settings()
    return {
        "max_connection_lifetime": settings.neo4j_max_connection_lifetime,
        "max_connection_pool_size": settings.neo4j_max_connection_pool_size,
        "connection_timeout": settings.neo4j_connection_timeout,
        "max_transaction_retry_time": 5.0,
        "keep_alive": True,
        "connection_acquisition_timeout": float(settings.neo4j_connection_timeout),
        "user_agent": "iob-ai-platform/phase2",
    }


class GraphDriverManager:
    """Thread-safe async Neo4j driver lifecycle manager (singleton)."""

    _driver: Optional[AsyncDriver] = None
    _lock = asyncio.Lock()
    _retries = DEFAULT_CONNECTION_RETRIES

    # ------------------------------------------------------------------ #
    # Construction / retrieval
    # ------------------------------------------------------------------ #
    @classmethod
    async def get_driver(cls) -> AsyncDriver:
        """Return the singleton async driver, creating it on first use."""
        async with cls._lock:
            if cls._driver is None:
                cls._driver = await cls._create_with_retry()
            return cls._driver

    @classmethod
    async def _create_with_retry(cls) -> AsyncDriver:
        settings = get_settings()
        uri = settings.neo4j_uri
        auth = (settings.neo4j_user, settings.neo4j_password)
        last_exc: Optional[Exception] = None

        for attempt in range(1, cls._retries + 1):
            driver = AsyncGraphDatabase.driver(uri, auth=auth, **_driver_config())
            try:
                # verify_connectivity has no timeout kwarg; bound it externally.
                await asyncio.wait_for(
                    driver.verify_connectivity(),
                    timeout=settings.neo4j_connection_timeout,
                )
                logger.info("Neo4j driver established against %s", uri)
                return driver
            except (ServiceUnavailable, AuthError, asyncio.TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "Neo4j connectivity attempt %d/%d to %s failed: %s",
                    attempt,
                    cls._retries,
                    uri,
                    exc,
                )
                await driver.close()
                backoff = min(2 ** (attempt - 1), DEFAULT_MAX_BACKOFF_SECONDS)
                await asyncio.sleep(backoff)

        raise Neo4jConnectionError(
            f"Could not connect to Neo4j at {uri} after {cls._retries} attempt(s): {last_exc}"
        )

    # ------------------------------------------------------------------ #
    # Health / introspection
    # ------------------------------------------------------------------ #
    @classmethod
    async def healthcheck(cls) -> dict:
        """Return a small connectivity/liveness report."""
        connected = False
        edition = version = None
        try:
            driver = await cls.get_driver()
            async with driver.session() as session:
                result = await session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS v")
                record = await result.single()
                if record is not None:
                    version = record["v"]
                connected = True
        except Exception as exc:  # noqa: BLE001 - surface as degraded, not fatal
            logger.debug("Neo4j healthcheck degraded: %s", exc)
        return {
            "neo4j": "up" if connected else "down",
            "version": version,
            "edition": edition,
        }

    @classmethod
    async def edition(cls) -> Optional[str]:
        """Return the server edition ('enterprise' | 'community' | None).

        Neo4j 5.x exposes this via ``dbms.components()`` with an ``edition``
        column. Property-existence constraints (``IS NOT NULL``) and node-key
        constraints are only honoured on Enterprise Edition; this helper lets
        the migration runner apply those selectively.
        """
        try:
            driver = await cls.get_driver()
            async with driver.session() as session:
                result = await session.run(
                    "CALL dbms.components() YIELD edition RETURN toLower(edition) AS edition"
                )
                record = await result.single()
                return record["edition"] if record is not None else None
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------ #
    # Teardown
    # ------------------------------------------------------------------ #
    @classmethod
    async def close(cls) -> None:
        """Close the underlying driver pool, if open."""
        async with cls._lock:
            driver = cls._driver
            cls._driver = None
            if driver is not None:
                await driver.close()
                logger.info("Neo4j driver closed.")

    @classmethod
    def is_connected(cls) -> bool:
        return cls._driver is not None


# Public, import-friendly aliases. ``get_async_driver`` is the canonical name
# for the async repository; ``get_driver`` is retained so legacy imports
# (e.g. migration scripts) resolve to the same singleton.
async def get_async_driver() -> AsyncDriver:
    return await GraphDriverManager.get_driver()


async def get_driver() -> AsyncDriver:
    return await GraphDriverManager.get_driver()
