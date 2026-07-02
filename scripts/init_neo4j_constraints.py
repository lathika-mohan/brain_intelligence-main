#!/usr/bin/env python3
"""
Bootstrap Neo4j uniqueness constraints and indexes per docs/neo4j_schema.md.

Usage:
    python scripts/init_neo4j_constraints.py
"""
from __future__ import annotations

import logging
import sys

sys.path.insert(0, ".")

from app.graph.client import get_driver  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONSTRAINTS = [
    "CREATE CONSTRAINT asset_id_unique IF NOT EXISTS FOR (a:Asset) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT component_id_unique IF NOT EXISTS FOR (c:Component) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT sensor_id_unique IF NOT EXISTS FOR (s:Sensor) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT failuremode_id_unique IF NOT EXISTS FOR (f:FailureMode) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT sop_id_unique IF NOT EXISTS FOR (s:SOP) REQUIRE s.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX asset_status_idx IF NOT EXISTS FOR (a:Asset) ON (a.status)",
    "CREATE INDEX asset_type_idx IF NOT EXISTS FOR (a:Asset) ON (a.type)",
]


def main() -> None:
    driver = get_driver()
    with driver.session() as session:
        for stmt in CONSTRAINTS + INDEXES:
            logger.info("Applying: %s", stmt)
            session.run(stmt)
    logger.info("Neo4j schema bootstrap complete.")


if __name__ == "__main__":
    main()
