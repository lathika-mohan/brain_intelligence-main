"""
Neo4j connection lifecycle manager — Phase 4 hardened optional.
Thread-safe async driver singleton with fallback stub when neo4j driver missing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from neo4j import AsyncDriver, AsyncGraphDatabase
    from neo4j.exceptions import AuthError, ServiceUnavailable
    HAS_NEO4J = True
except Exception as e:  # pragma: no cover
    AsyncDriver = Any  # type: ignore
    AsyncGraphDatabase = Any  # type: ignore
    AuthError = Exception
    ServiceUnavailable = Exception
    HAS_NEO4J = False
    logger.info("neo4j driver not available — graph client will operate in degraded stub: %s", e)

DEFAULT_CONNECTION_RETRIES = 5
DEFAULT_MAX_BACKOFF_SECONDS = 8.0

class Neo4jConnectionError(RuntimeError):
    pass

def _driver_config() -> dict:
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

class _StubDriver:
    async def verify_connectivity(self):
        return True
    async def close(self):
        pass
    def session(self):
        class _S:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def run(self, *a, **kw):
                class _R:
                    async def single(self):
                        return None
                return _R()
        return _S()

class GraphDriverManager:
    _driver: Optional[Any] = None
    _lock = asyncio.Lock()
    _retries = DEFAULT_CONNECTION_RETRIES

    @classmethod
    async def get_driver(cls) -> Any:
        async with cls._lock:
            if cls._driver is None:
                if not HAS_NEO4J:
                    logger.warning("Neo4j stub driver used — no real DB")
                    cls._driver = _StubDriver()
                else:
                    cls._driver = await cls._create_with_retry()
            return cls._driver

    @classmethod
    async def _create_with_retry(cls) -> Any:
        settings = get_settings()
        uri = settings.neo4j_uri
        auth = (settings.neo4j_user, settings.neo4j_password)
        last_exc: Optional[Exception] = None
        for attempt in range(1, cls._retries + 1):
            if not HAS_NEO4J:
                return _StubDriver()
            driver = AsyncGraphDatabase.driver(uri, auth=auth, **_driver_config())
            try:
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
                    attempt, cls._retries, uri, exc,
                )
                await driver.close()
                backoff = min(2 ** (attempt - 1), DEFAULT_MAX_BACKOFF_SECONDS)
                await asyncio.sleep(backoff)

        raise Neo4jConnectionError(
            f"Could not connect to Neo4j at {uri} after {cls._retries} attempt(s): {last_exc}"
        )

    @classmethod
    async def healthcheck(cls) -> dict:
        connected = False
        version = None
        edition = None
        try:
            driver = await cls.get_driver()
            if HAS_NEO4J:
                async with driver.session() as session:
                    result = await session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS v")
                    record = await result.single()
                    if record is not None:
                        version = record["v"]
                    connected = True
            else:
                connected = False
        except Exception as exc:
            logger.debug("Neo4j healthcheck degraded: %s", exc)
        return {
            "neo4j": "up" if connected else "down",
            "version": version,
            "edition": edition,
            "driver": "stub" if not HAS_NEO4J else "real",
        }

    @classmethod
    async def edition(cls) -> Optional[str]:
        try:
            driver = await cls.get_driver()
            if not HAS_NEO4J:
                return None
            async with driver.session() as session:
                result = await session.run(
                    "CALL dbms.components() YIELD edition RETURN toLower(edition) AS edition"
                )
                record = await result.single()
                return record["edition"] if record is not None else None
        except Exception:
            return None

    @classmethod
    async def close(cls) -> None:
        async with cls._lock:
            driver = cls._driver
            cls._driver = None
            if driver is not None:
                try:
                    await driver.close()
                except Exception:
                    pass
                logger.info("Neo4j driver closed.")

    @classmethod
    def is_connected(cls) -> bool:
        return cls._driver is not None

async def get_async_driver() -> Any:
    return await GraphDriverManager.get_driver()

async def get_driver() -> Any:
    return await GraphDriverManager.get_driver()
