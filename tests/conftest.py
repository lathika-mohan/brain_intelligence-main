"""
Shared pytest fixtures for Phase 2 graph-layer tests.

Integration tests require a reachable Neo4j 5.x instance. By default they
target ``bolt://127.0.0.1:7687`` (the in-repo ``docker-compose`` service /
the local dev server). Override with environment variables:

    NEO4J_TEST_URI=bolt://localhost:7687
    NEO4J_TEST_USER=neo4j
    NEO4J_TEST_PASSWORD=neo4jtest123
    NEO4J_TEST_DATABASE=neo4j

If no Neo4j is reachable, the ``neo4j_driver`` fixture **skips** cleanly so the
offline unit suite still passes in constrained CI environments. To run the
real integration suite, start the database first (e.g. ``docker compose up -d neo4j``).
"""
from __future__ import annotations

import os

import pytest

NEO4J_TEST_URI = os.getenv("NEO4J_TEST_URI", "bolt://127.0.0.1:7687")
NEO4J_TEST_USER = os.getenv("NEO4J_TEST_USER", "neo4j")
NEO4J_TEST_PASSWORD = os.getenv("NEO4J_TEST_PASSWORD", "neo4jtest123")
NEO4J_TEST_DATABASE = os.getenv("NEO4J_TEST_DATABASE", "neo4j")


def _connect_driver():
    from neo4j import AsyncGraphDatabase

    return AsyncGraphDatabase.driver(
        NEO4J_TEST_URI,
        auth=(NEO4J_TEST_USER, NEO4J_TEST_PASSWORD),
        max_connection_lifetime=60,
        max_connection_pool_size=10,
        connection_timeout=10,
        connection_acquisition_timeout=10,
    )


async def _verify(driver) -> None:
    import asyncio

    from neo4j.exceptions import AuthError, ServiceUnavailable

    try:
        await asyncio.wait_for(driver.verify_connectivity(), timeout=10)
    except (ServiceUnavailable, AuthError, asyncio.TimeoutError) as exc:  # pragma: no cover
        await driver.close()
        raise ConnectionError(f"Neo4j not reachable at {NEO4J_TEST_URI}: {exc}") from exc


async def _clean(driver) -> None:
    # Best-effort full-graph cleanup so each integration test starts isolated.
    try:
        async with driver.session(database=NEO4J_TEST_DATABASE) as session:
            await (await session.run("MATCH (n) DETACH DELETE n")).consume()
    except Exception:  # noqa: BLE001 - cleanup is best-effort
        pass


@pytest.fixture
async def neo4j_driver():
    """Async Neo4j driver fixture; skips the test when no database is reachable."""
    try:
        driver = _connect_driver()
        await _verify(driver)
    except (ConnectionError, Exception) as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j integration database not available at {NEO4J_TEST_URI} ({exc}).")

    # Isolation: start from an empty graph for every test that requests the DB.
    await _clean(driver)

    yield driver

    await _clean(driver)
    await driver.close()
