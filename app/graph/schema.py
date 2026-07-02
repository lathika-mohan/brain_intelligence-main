"""
Neo4j graph schema constants (Phase 0 — structural blueprint only).

This module intentionally contains ZERO Cypher execution / pipeline
logic. It exists so:
  1. `client.py` can reference canonical label/relationship string
     constants instead of magic strings scattered across the codebase.
  2. `scripts/init_neo4j_constraints.py` can programmatically apply the
     constraints/indexes documented in `docs/neo4j_schema.md`.

The authoritative human-readable schema spec lives in
`docs/neo4j_schema.md` — keep both in sync.
"""
from enum import Enum


class NodeLabel(str, Enum):
    ASSET = "Asset"
    COMPONENT = "Component"
    SENSOR = "Sensor"
    FAILURE_MODE = "FailureMode"
    SOP = "SOP"


class RelationshipType(str, Enum):
    HAS_COMPONENT = "HAS_COMPONENT"       # (:Asset)-[:HAS_COMPONENT]->(:Component)
    HAS_SENSOR = "HAS_SENSOR"             # (:Component)-[:HAS_SENSOR]->(:Sensor)
    INDICATES_FAILURE = "INDICATES_FAILURE"  # (:Sensor)-[:INDICATES_FAILURE]->(:FailureMode)
    MITIGATED_BY = "MITIGATED_BY"         # (:FailureMode)-[:MITIGATED_BY]->(:SOP)
    PART_OF = "PART_OF"                   # (:Component)-[:PART_OF]->(:Asset) (inverse convenience)
    DEPENDS_ON = "DEPENDS_ON"             # (:Asset)-[:DEPENDS_ON]->(:Asset)


# Uniqueness constraints applied at bootstrap time (see scripts/init_neo4j_constraints.py)
UNIQUE_CONSTRAINTS: dict[NodeLabel, str] = {
    NodeLabel.ASSET: "id",
    NodeLabel.COMPONENT: "id",
    NodeLabel.SENSOR: "id",
    NodeLabel.FAILURE_MODE: "id",
    NodeLabel.SOP: "id",
}
