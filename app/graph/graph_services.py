"""
Phase 2 High-Performance Graph CRUD & Query Services (Neo4j).

This layer wraps :class:`~app.graph.graph_repository.Neo4jGraphRepository` and
exposes clean, typed, async interfaces for downstream pipeline stages:

* **Graph CRUD** — create/read/update/delete across the Phase 1 core entities
  with deletion rules that structurally decouple children (``DETACH DELETE``).
* **Graph Validation Engine** — programmatic integrity assertions that audit
  the graph against the ontology (e.g. flag any ``:Sensor`` lacking a
  ``MONITORED_BY`` edge, any ``:Asset`` without a location).
* **Graph Query / Traversal** — sub-graph expansion (Asset → Component →
  Sensor → FailureMode → SOP …) plus TEXT-index search and native VECTOR
  similarity search, with raw Cypher records mapped into the Phase 0
  :class:`~app.models.graphrag.GraphContextMap` contract that powers
  ``src/components/GraphRagPanel.tsx``.

No UI, no parser, and no ML logic lives here — this is the database service
boundary that Phase 3 (GraphRAG fusion) and beyond will call.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.graph.graph_repository import (
    GraphEntityNotFound,
    Neo4jGraphRepository,
    model_to_graph_props,
    to_graph_props,
)
from app.models.common import utc_now
from app.models.graphrag import GraphContextMap, GraphEdge, GraphNode

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.ontology import SemanticEntity

logger = logging.getLogger(__name__)

# Cypher-only relationship set used when expanding an asset sub-graph. Keeping
# traversal to the canonical failure→mitigation chain keeps fan-out bounded.
SUBGRAPH_RELATIONSHIPS = "COMPRISED_OF|MONITORED_BY|EXHIBITS_ANOMALY|MITIGATED_BY|TRIGGERED_BY|HAS_SYMPTOM|HAS_STEP"

# Traversal depth bound to protect the DETACH/return size on large graphs.
MAX_TRAVERSAL_HOPS = 5

_INTERNAL_PROP_KEYS = frozenset({"created_at", "updated_at"})


def _sanitize_props(props: dict[str, Any]) -> dict[str, Any]:
    """Strip internal bookkeeping properties from a payload shown downstream."""
    return {k: v for k, v in (props or {}).items() if k not in _INTERNAL_PROP_KEYS and not k.startswith("_")}


# --------------------------------------------------------------------------- #
# Validation report models
# --------------------------------------------------------------------------- #
class ValidationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_name: str
    label: str
    offending_ids: list[str] = Field(default_factory=list)
    severity: str = Field(default="WARNING")

    @property
    def count(self) -> int:
        return len(self.offending_ids)

    @property
    def healthy(self) -> bool:
        return not self.offending_ids


class GraphValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checked_at: datetime = Field(default_factory=utc_now)
    findings: list[ValidationFinding] = Field(default_factory=list)
    total_offenders: int = 0

    @property
    def healthy(self) -> bool:
        return self.total_offenders == 0


# Integrity checks: each `where` references the bound node variable `n`.
INTEGRITY_CHECKS: list[dict[str, str]] = [
    {
        "check_name": "sensor_without_monitoring",
        "label": "Sensor",
        "where": "NOT EXISTS { MATCH (n)<-[:MONITORED_BY]-(:Component) }",
        "severity": "HIGH",
    },
    {
        "check_name": "component_without_owning_asset",
        "label": "Component",
        "where": "NOT EXISTS { MATCH (n)<-[:COMPRISED_OF]-(:Asset) }",
        "severity": "HIGH",
    },
    {
        "check_name": "asset_without_location",
        "label": "Asset",
        "where": (
            "NOT EXISTS { MATCH (n)-[:LOCATED_IN]->(:Location) } "
            "AND NOT EXISTS { MATCH (n)<-[:CONTAINS]-(:Location) }"
        ),
        "severity": "MEDIUM",
    },
    {
        "check_name": "failure_mode_without_root_cause",
        "label": "FailureMode",
        "where": "NOT EXISTS { MATCH (n)-[:TRIGGERED_BY]->(:RootCause) }",
        "severity": "MEDIUM",
    },
    {
        "check_name": "failure_mode_without_mitigation",
        "label": "FailureMode",
        "where": "NOT EXISTS { MATCH (n)-[:MITIGATED_BY]->(:SOP) }",
        "severity": "LOW",
    },
    {
        "check_name": "sop_without_steps",
        "label": "SOP",
        "where": "NOT EXISTS { MATCH (n)-[:HAS_STEP]->(:SOPStep) }",
        "severity": "LOW",
    },
    {
        "check_name": "sop_step_without_sop",
        "label": "SOPStep",
        "where": "NOT EXISTS { MATCH (n)-[:HAS_STEP]-(:SOP) }",
        "severity": "MEDIUM",
    },
]


# --------------------------------------------------------------------------- #
# CRUD service
# --------------------------------------------------------------------------- #
class GraphCrudService:
    """Typed Create/Read/Update/Delete over the graph repository."""

    def __init__(self, repository: Neo4jGraphRepository) -> None:
        self._repo = repository

    # ----------------------------- generic ------------------------------ #
    async def upsert_entity(self, entity: "SemanticEntity") -> dict[str, Any]:
        label = type(entity).__name__
        return await self._repo.upsert_node(label, entity.id, model_to_graph_props(entity))

    async def get_entity(self, label: str, entity_id: str) -> Optional[dict[str, Any]]:
        return await self._repo.get_node(label, entity_id)

    async def patch_entity(self, label: str, entity_id: str, fields: dict[str, Any]) -> Optional[dict]:
        return await self._repo.update_node(label, entity_id, to_graph_props(fields))

    async def delete_entity(self, label: str, entity_id: str) -> int:
        return await self._repo.delete_node(label, entity_id)

    # ----------------------- typed core-entity upserts ------------------ #
    async def upsert_asset(self, asset: "SemanticEntity") -> dict:  # noqa: D401 - convenience
        return await self.upsert_entity(asset)

    async def upsert_component(self, component: "SemanticEntity") -> dict:
        return await self.upsert_entity(component)

    async def upsert_sensor(self, sensor: "SemanticEntity") -> dict:
        return await self.upsert_entity(sensor)

    async def upsert_failure_mode(self, failure_mode: "SemanticEntity") -> dict:
        return await self.upsert_entity(failure_mode)

    async def upsert_root_cause(self, root_cause: "SemanticEntity") -> dict:
        return await self.upsert_entity(root_cause)

    async def upsert_sop(self, sop: "SemanticEntity") -> dict:
        return await self.upsert_entity(sop)

    async def upsert_sop_step(self, sop_step: "SemanticEntity") -> dict:
        return await self.upsert_entity(sop_step)


# --------------------------------------------------------------------------- #
# Validation engine
# --------------------------------------------------------------------------- #
class GraphValidationService:
    """Audits graph integrity against the Phase 1 ontology rules."""

    def __init__(self, repository: Neo4jGraphRepository) -> None:
        self._repo = repository

    @staticmethod
    def build_integrity_query(label: str, where: str) -> str:
        return f"MATCH (n:`{label}`) WHERE {where} RETURN n.id AS id"

    async def run_check(self, check: dict[str, str]) -> ValidationFinding:
        records = await self._repo._read(  # noqa: SLF001 - single-read helper
            self.build_integrity_query(check["label"], check["where"])
        )
        offending = [r["id"] for r in records if r.get("id") is not None]
        return ValidationFinding(
            check_name=check["check_name"],
            label=check["label"],
            offending_ids=offending,
            severity=check.get("severity", "WARNING"),
        )

    async def validate(self) -> GraphValidationReport:
        findings = [await self.run_check(check) for check in INTEGRITY_CHECKS]
        return GraphValidationReport(
            findings=findings,
            total_offenders=sum(f.count for f in findings),
        )


# --------------------------------------------------------------------------- #
# Query / traversal service
# --------------------------------------------------------------------------- #
def build_subgraph_query(asset_id: str, max_hops: int = 3) -> tuple[str, dict[str, Any]]:
    """Pure builder for an asset knowledge sub-graph expansion.

    Returns the root asset plus every node/edge reachable along the canonical
    failure→mitigation chain within ``max_hops`` (defaults to the Phase 0/1
    depth of 3: Asset → Component → Sensor → FailureMode).

    The hop bound is inlined as a literal because Cypher does not permit
    parameterizing a variable-length quantifier (``*1..$n`` is a syntax error).
    ``hops`` is an int derived from clamping user input, so inlining is safe.
    """
    hops = max(1, min(int(max_hops), MAX_TRAVERSAL_HOPS))
    cypher = (
        "MATCH (root:Asset {id:$asset_id}) "
        "CALL { "
        f"  WITH root OPTIONAL MATCH path=(root)-[rels:{SUBGRAPH_RELATIONSHIPS}*1..{hops}]->(leaf) "
        "  RETURN collect(CASE WHEN path IS NULL THEN null ELSE { "
        "    nodes: [x IN nodes(path) | {element_id: elementId(x), labels: labels(x), props: properties(x)}], "
        "    rels: [r IN rels | { "
        "      element_id: elementId(r), type: type(r), props: properties(r), "
        "      start_id: elementId(startNode(r)), end_id: elementId(endNode(r)) "
        "    }] "
        "  } END) AS paths "
        "} "
        "RETURN root.id AS root_id, "
        "       {element_id: elementId(root), labels: labels(root), props: properties(root)} AS root_node, "
        "       [p IN paths WHERE p IS NOT NULL] AS paths"
    )
    return cypher, {"asset_id": asset_id}


def _node_to_graph_node(node: dict[str, Any]) -> GraphNode:
    props = node.get("props", node)
    labels = node.get("labels") or ["Node"]
    label = labels[0]
    return GraphNode(
        id=props.get("id") or node.get("element_id"),
        label=label,
        display_name=props.get("display_name") or label,
        properties=_sanitize_props(props),
    )


def _records_to_graph_context(records: list[dict[str, Any]]) -> GraphContextMap:
    """Map raw sub-graph records into the Phase 0 ``GraphContextMap`` contract.

    Pure (no driver access) so it is unit-testable with synthetic records.
    """
    if not records:
        raise GraphEntityNotFound("Asset sub-graph returned no records.")
    record = records[0]
    root_node = record.get("root_node")
    if not root_node:
        raise GraphEntityNotFound("Asset root node not found.")

    nodes_by_eid: dict[str, dict[str, Any]] = {}
    edges_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_node(node: dict[str, Any]) -> None:
        eid = node.get("element_id")
        if eid:
            nodes_by_eid.setdefault(eid, node)

    add_node(root_node)
    for path in record.get("paths", []) or []:
        for node in path.get("nodes", []):
            add_node(node)
        for rel in path.get("rels", []):
            start_id = rel.get("start_id")
            end_id = rel.get("end_id")
            if start_id in nodes_by_eid and end_id in nodes_by_eid:
                key = (start_id, rel.get("type", ""), end_id)
                edges_by_key[key] = rel

    graph_nodes = [_node_to_graph_node(n) for n in nodes_by_eid.values()]
    graph_edges = [
        GraphEdge(
            source_id=nodes_by_eid[start]["props"].get("id"),
            target_id=nodes_by_eid[end]["props"].get("id"),
            relationship=rel.get("type", ""),
            properties=_sanitize_props(rel.get("props", {})),
        )
        for (start, _, end), rel in edges_by_key.items()
    ]
    return GraphContextMap(
        nodes=graph_nodes,
        edges=graph_edges,
        root_node_ids=[record.get("root_id")],
    )


class GraphQueryService:
    """Structural traversal + hybrid semantic (TEXT / VECTOR) lookups."""

    def __init__(self, repository: Neo4jGraphRepository) -> None:
        self._repo = repository

    async def get_asset_subgraph(self, asset_id: str, max_hops: int = 3) -> GraphContextMap:
        cypher, params = build_subgraph_query(asset_id, max_hops)
        records = await self._repo._read(cypher, params)  # noqa: SLF001
        return _records_to_graph_context(records)

    async def find_nodes_text(
        self, label: str, property_name: str, term: str, limit: int = 25
    ) -> list[GraphNode]:
        # Index-backed CONTAINS search over the TEXT index on `property_name`.
        cypher = (
            f"MATCH (n:`{label}`) WHERE n.`{property_name}` CONTAINS $term "
            "RETURN n {.*} AS node LIMIT $limit"
        )
        records = await self._repo._read(cypher, {"term": term, "limit": limit})  # noqa: SLF001
        return [
            GraphNode(
                id=r["node"].get("id") or "",
                label=label,
                display_name=r["node"].get("display_name") or label,
                properties=_sanitize_props(r["node"]),
            )
            for r in records
            if r.get("node")
        ]

    async def vector_search_failure_modes(
        self, embedding: list[float], k: int = 10
    ) -> list[tuple[GraphNode, float]]:
        """Hybrid hook: query the native vector index once embeddings are populated."""
        cypher = (
            "CALL db.index.vector.queryNodes('vector_FailureMode_embedding', $k, $embedding) "
            "YIELD node, score RETURN node {.*} AS node, score AS score LIMIT $k"
        )
        records = await self._repo._read(cypher, {"k": k, "embedding": embedding})  # noqa: SLF001
        return [
            (
                GraphNode(
                    id=r["node"].get("id") or "",
                    label="FailureMode",
                    display_name=r["node"].get("display_name") or "FailureMode",
                    properties=_sanitize_props(r["node"]),
                ),
                float(r["score"]),
            )
            for r in records
            if r.get("node")
        ]


# --------------------------------------------------------------------------- #
# Facade
# --------------------------------------------------------------------------- #
class GraphAPIService:
    """Internal service facade consumed by downstream phases.

    Bundles repository + CRUD + validation + query behind one object so the
    GraphRAG engine can call a single interface that returns Phase 0 Pydantic
    contracts rather than raw Cypher records.
    """

    def __init__(
        self,
        repository: Neo4jGraphRepository,
        *,
        crud: Optional[GraphCrudService] = None,
        validation: Optional[GraphValidationService] = None,
        query: Optional[GraphQueryService] = None,
    ) -> None:
        self.repository = repository
        self.crud = crud or GraphCrudService(repository)
        self.validation = validation or GraphValidationService(repository)
        self.query = query or GraphQueryService(repository)

    @classmethod
    async def connect(cls) -> "GraphAPIService":
        from app.graph.client import GraphDriverManager

        driver = await GraphDriverManager.get_driver()
        from app.core.config import get_settings

        repo = Neo4jGraphRepository(driver, database=get_settings().neo4j_database)
        return cls(repo)
