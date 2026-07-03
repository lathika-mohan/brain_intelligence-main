"""
Phase 2 Programmatic Graph Repository Layer (Neo4j).

Provides:

* **Pure Cypher query builders** (``build_*`` functions) so the generated
  statements are unit-testable without a database and are guaranteed to use
  idempotent ``MERGE`` (never blind ``CREATE``) for node/edge upserts.
* **Property serialization** that flattens Pydantic ``model_dump(mode="json")``
  payloads into Neo4j-friendly scalar properties while JSON-encoding nested
  structures (operating envelopes, citation anchors, baselines) so the graph
  stays queryable.
* An **async :class:`Neo4jGraphRepository`** built on the official ``neo4j``
  5.x async driver, offering idempotent node upserts, deletion with structural
  decoupling (``DETACH DELETE``), isolated transactional relationship linkage
  (incl. endpoint-existence guards), and raw reads.

No Cypher strings are executed here at import time; execution only happens
through the public async methods against a driver obtained from
:mod:`app.graph.client`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class GraphRepositoryError(RuntimeError):
    """Base class for repository errors."""


class GraphEntityNotFound(GraphRepositoryError):
    """Raised when an expected node/edge does not exist."""


class GraphLinkError(GraphRepositoryError):
    """Raised when a relationship cannot be drawn between existing nodes."""


# --------------------------------------------------------------------------- #
# Property serialization
# --------------------------------------------------------------------------- #
def _jsonify(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str, sort_keys=False)


def to_graph_props(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten a JSON-safe dict into Neo4j property storage.

    Rules:
    * Scalars (str/int/float/bool) are stored directly.
    * Homogeneous lists of scalars are stored directly (index/query friendly).
    * Nested lists/dicts (envelopes, baseline constraints, citation anchors)
      are JSON-encoded into a single string property so the node stays flat.
    * ``None`` values are dropped (Neo4j has no null-property semantics).
    """
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
        elif isinstance(value, list):
            if value and all(isinstance(x, (str, int, float, bool)) for x in value):
                out[key] = value
            else:
                out[key] = _jsonify(value)
        elif isinstance(value, dict):
            out[key] = _jsonify(value)
        else:
            out[key] = _jsonify(value)
    return out


def model_to_graph_props(model: BaseModel) -> dict[str, Any]:
    """Serialize a Pydantic model into Neo4j-friendly properties."""
    return to_graph_props(model.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Pure Cypher builders (unit-testable, MERGE-based / idempotent)
# --------------------------------------------------------------------------- #
def build_upsert_node_query(label: str, node_id: str, properties: dict[str, Any]):
    # Always carry `id` into the property bag so ON CREATE SET n = $props does
    # not clobber the merge key (the pattern matches on id, but $props may not).
    merged = dict(properties)
    merged["id"] = node_id
    cypher = (
        f"MERGE (n:`{label}` {{id:$id}}) "
        "ON CREATE SET n = $props, n.created_at = datetime() "
        "ON MATCH SET n += $props, n.updated_at = datetime() "
        "RETURN n {.*} AS node"
    )
    params: dict[str, Any] = {"id": node_id, "props": merged}
    return cypher, params


def build_update_node_query(label: str, node_id: str, properties: dict[str, Any]):
    cypher = (
        f"MATCH (n:`{label}` {{id:$id}}) "
        "SET n += $props, n.updated_at = datetime() "
        "RETURN n {.*} AS node"
    )
    return cypher, {"id": node_id, "props": properties}


def build_get_node_query(label: str, node_id: str):
    cypher = f"MATCH (n:`{label}` {{id:$id}}) RETURN n {{.*}} AS node LIMIT 1"
    return cypher, {"id": node_id}


def build_delete_node_query(label: str, node_id: str):
    cypher = f"MATCH (n:`{label}` {{id:$id}}) DETACH DELETE n RETURN count(n) AS deleted"
    return cypher, {"id": node_id}


def build_endpoint_presence_query(source_label: str, source_id: str, target_label: str, target_id: str):
    cypher = (
        f"MATCH (a:`{source_label}` {{id:$source_id}}) "
        f"MATCH (b:`{target_label}` {{id:$target_id}}) "
        "RETURN a IS NOT NULL AS source_present, b IS NOT NULL AS target_present"
    )
    return cypher, {"source_id": source_id, "target_id": target_id}


def build_link_query(
    source_label: str,
    source_id: str,
    relationship: str,
    target_label: str,
    target_id: str,
    properties: Optional[dict[str, Any]] = None,
):
    cypher = (
        f"MATCH (a:`{source_label}` {{id:$source_id}}) "
        f"MATCH (b:`{target_label}` {{id:$target_id}}) "
        f"MERGE (a)-[r:`{relationship}`]->(b) "
        "ON CREATE SET r = $props, r.created_at = datetime() "
        "ON MATCH SET r += $props, r.updated_at = datetime() "
        "RETURN startNode(r).id AS source_id, endNode(r).id AS target_id, "
        "type(r) AS type, properties(r) AS properties"
    )
    params: dict[str, Any] = {
        "source_id": source_id,
        "target_id": target_id,
        "props": properties or {},
    }
    return cypher, params


def build_endpoint_check_query(label: str, node_id: str):
    return f"MATCH (n:`{label}` {{id:$id}}) RETURN count(n) AS c", {"id": node_id}


# --------------------------------------------------------------------------- #
# Async repository
# --------------------------------------------------------------------------- #
class Neo4jGraphRepository:
    """Async, idempotent graph repository over the neo4j 5.x async driver."""

    def __init__(self, driver, *, database: Optional[str] = None) -> None:
        self._driver = driver
        self._database = database

    # ----------------------------- low-level ----------------------------- #
    async def _read(self, cypher: str, params: Optional[dict] = None) -> list[dict]:
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def _write(self, cypher: str, params: Optional[dict] = None) -> list[dict]:
        # Writes use the default (WRITE) access mode; session.run handles it.
        return await self._read(cypher, params)

    # ------------------------------ nodes -------------------------------- #
    async def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> dict:
        cypher, params = build_upsert_node_query(label, node_id, properties)
        records = await self._write(cypher, params)
        return records[0]["node"] if records else {}

    async def update_node(self, label: str, node_id: str, properties: dict[str, Any]) -> Optional[dict]:
        cypher, params = build_update_node_query(label, node_id, properties)
        records = await self._write(cypher, params)
        return records[0]["node"] if records else None

    async def get_node(self, label: str, node_id: str) -> Optional[dict]:
        cypher, params = build_get_node_query(label, node_id)
        records = await self._read(cypher, params)
        return records[0]["node"] if records else None

    async def node_exists(self, label: str, node_id: str) -> bool:
        cypher, params = build_endpoint_check_query(label, node_id)
        records = await self._read(cypher, params)
        return bool(records and records[0]["c"] > 0)

    async def delete_node(self, label: str, node_id: str) -> int:
        """Delete a node and DETACH its relationships (structural decoupling).

        Deleting a Component this way removes the owning Asset's ``COMPRISED_OF``
        edge, so the asset is never left pointing at an orphaned child.
        """
        cypher, params = build_delete_node_query(label, node_id)
        records = await self._write(cypher, params)
        return int(records[0]["deleted"]) if records else 0

    # --------------------------- relationships --------------------------- #
    async def link_nodes(
        self,
        source_label: str,
        source_id: str,
        relationship: str,
        target_label: str,
        target_id: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Draw a directed, idempotent edge between two existing nodes."""
        present = await self._read(
            *build_endpoint_presence_query(source_label, source_id, target_label, target_id)
        )
        row = present[0] if present else {}
        if not row.get("source_present"):
            raise GraphLinkError(f"Source :{source_label} '{source_id}' not found.")
        if not row.get("target_present"):
            raise GraphLinkError(f"Target :{target_label} '{target_id}' not found.")

        cypher, params = build_link_query(
            source_label, source_id, relationship, target_label, target_id, properties
        )
        records = await self._write(cypher, params)
        if not records:
            raise GraphLinkError(
                f"Could not link :{source_label} '{source_id}' -[:{relationship}]-> "
                f":{target_label} '{target_id}'."
            )
        return records[0]

    # ------------------- typed structural linkage helpers ----------------- #
    # These map directly onto the Phase 1 RELATIONSHIP_CATALOG edge directions:
    #   (Asset)-[:COMPRISED_OF]->(Component)
    #   (Component)-[:MONITORED_BY]->(Sensor)
    async def link_component_to_asset(
        self, component_id: str, asset_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        # Edge direction is Asset -> Component even though the args read (component, asset).
        return await self.link_nodes(
            "Asset", asset_id, "COMPRISED_OF", "Component", component_id, properties
        )

    async def link_sensor_to_component(
        self, sensor_id: str, component_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        # Edge direction is Component -> Sensor even though the args read (sensor, component).
        return await self.link_nodes(
            "Component", component_id, "MONITORED_BY", "Sensor", sensor_id, properties
        )

    async def link_asset_to_location(
        self, asset_id: str, location_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        return await self.link_nodes(
            "Asset", asset_id, "LOCATED_IN", "Location", location_id, properties
        )

    async def link_sensor_anomaly_to_failure_mode(
        self, sensor_id: str, failure_mode_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        # Required edge props per catalog: metric (str), confidence_weight (0..1).
        return await self.link_nodes(
            "Sensor", sensor_id, "EXHIBITS_ANOMALY", "FailureMode", failure_mode_id, properties
        )

    async def link_failure_mode_to_root_cause(
        self, failure_mode_id: str, root_cause_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        return await self.link_nodes(
            "FailureMode", failure_mode_id, "TRIGGERED_BY", "RootCause", root_cause_id, properties
        )

    async def link_failure_mode_to_sop(
        self, failure_mode_id: str, sop_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        return await self.link_nodes(
            "FailureMode", failure_mode_id, "MITIGATED_BY", "SOP", sop_id, properties
        )

    async def link_sop_to_step(
        self, sop_id: str, sop_step_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        # Required edge prop: sequence_number (int).
        return await self.link_nodes(
            "SOP", sop_id, "HAS_STEP", "SOPStep", sop_step_id, properties
        )

    async def link_sop_to_tool(
        self, sop_id: str, tooling_id: str, properties: Optional[dict[str, Any]] = None
    ) -> dict:
        return await self.link_nodes(
            "SOP", sop_id, "REQUIRES_TOOL", "Tooling", tooling_id, properties
        )
