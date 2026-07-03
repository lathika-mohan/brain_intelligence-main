"""
Phase 2 — INTEGRATION tests (require a live Neo4j 5.x).

These execute against an isolated test graph database and assert the database
engine behaves exactly as the ontology/migration contract promises:

* all 16 labels get uniqueness constraints; TEXT/RANGE/VECTOR indexes exist;
* writing a duplicate ``id`` fails natively (constraint enforcement);
* MERGE upserts are idempotent;
* a 3+ degree traversal (Asset → Component → Sensor → FailureMode → SOP)
  populates the Phase 0 ``GraphContextMap`` with the expected metadata;
* the validation engine flags (and then clears) structural integrity gaps;
* deletion decouples children without orphaning the parent;
* relationship linkage is idempotent and guards missing endpoints;
* the native vector index is queryable even before ``embedding`` is populated.

Run with a database available (see tests/conftest.py for env overrides).
"""
from __future__ import annotations

import pytest
from neo4j.exceptions import ClientError

from app.graph import schema_migrations as mig
from app.graph.graph_repository import (
    GraphLinkError,
    Neo4jGraphRepository,
)
from app.graph.graph_services import GraphAPIService, GraphValidationService
from tests.conftest import NEO4J_TEST_DATABASE


@pytest.fixture
def repo(neo4j_driver):
    return Neo4jGraphRepository(neo4j_driver, database=NEO4J_TEST_DATABASE)


# --------------------------------------------------------------------------- #
# Schema bootstrap
# --------------------------------------------------------------------------- #
async def test_apply_migrations_creates_full_schema(repo):
    report = await mig.apply_migrations(repo._driver, database=NEO4J_TEST_DATABASE)
    assert not report.errors, report.errors
    # On Community the 70 Enterprise-only existence constraints are skipped.
    if report.edition != "enterprise":
        assert len(report.skipped) == len(mig.existence_statements())

    async with repo._driver.session(database=NEO4J_TEST_DATABASE) as session:
        constraints = [r async for r in await session.run("SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties RETURN *")]
        indexes = [r async for r in await session.run("SHOW INDEXES YIELD name, type, labelsOrTypes, properties RETURN *")]

    # Every Phase 1 label must carry a uniqueness constraint on `id`.
    constrained_labels = {
        (c.get("labelsOrTypes") or [None])[0] for c in constraints
    }
    for label in mig.NODE_LABELS:
        assert label in constrained_labels, f"missing uniqueness constraint for {label}"

    index_types = {i.get("type") for i in indexes}
    assert "RANGE" in index_types
    assert "TEXT" in index_types
    assert "VECTOR" in index_types
    vector_index_names = {i["name"] for i in indexes if i.get("type") == "VECTOR"}
    assert "vector_FailureMode_embedding" in vector_index_names
    assert "vector_SOPStep_embedding" in vector_index_names


# --------------------------------------------------------------------------- #
# Constraint enforcement + idempotent upsert
# --------------------------------------------------------------------------- #
async def test_duplicate_unique_id_fails_natively(repo):
    await repo.upsert_node("Asset", "asset:dup:1", {"display_name": "Dup", "status": "OPERATIONAL"})
    # A second MERGE with the same id must NOT create a duplicate.
    await repo.upsert_node("Asset", "asset:dup:1", {"display_name": "Dup v2"})
    count = (await repo._read("MATCH (n:Asset {id:$id}) RETURN count(n) AS c", {"id": "asset:dup:1"}))[0]["c"]
    assert count == 1

    # A raw CREATE with a duplicate id must be rejected by the engine natively.
    with pytest.raises(ClientError) as exc:
        await repo._write("CREATE (n:Asset {id:$id}) RETURN n", {"id": "asset:dup:1"})
    assert "already exists" in str(exc.value) or "ConstraintValidation" in str(exc.value)


# --------------------------------------------------------------------------- #
# 3+ degree traversal with metadata
# --------------------------------------------------------------------------- #
def _seed_chain(repo):
    asset = {
        "id": "asset:SRP:P-101A", "display_name": "Pump P-101A", "asset_type": "PUMP",
        "equipment_class": "ROTARY_EQUIPMENT", "tag": "P-101A", "status": "OPERATIONAL",
        "criticality": "PRODUCTION_CRITICAL", "location_id": "location:SRP:plant-1",
        "process_function": "transfer fluid",
    }
    component = {
        "id": "component:P-101A:BEARING:DE", "display_name": "DE Bearing", "asset_id": asset["id"],
        "component_type": "BEARING", "criticality": "PRODUCTION_CRITICAL",
    }
    sensor = {
        "id": "sensor:SRP:TE-101A-DE", "display_name": "DE RTD", "sensor_category": "THERMAL",
        "metric": "bearing_temp", "unit": "C", "asset_id": asset["id"], "component_id": component["id"],
        "tag": "TE-101A-DE", "sampling_method": "CONTINUOUS", "sampling_frequency_hz": 1.0,
    }
    failure = {
        "id": "failuremode:ROTARY_EQUIPMENT:BEARING:overheat", "display_name": "Bearing Overheat",
        "equipment_class": "ROTARY_EQUIPMENT", "component_type": "BEARING",
        "severity_tier": "DEGRADED", "mechanisms": ["OVERHEATING", "WEAR"],
        "failure_effect": "elevated bearing temperature",
    }
    root = {"id": "rootcause:MAINTENANCE:under_lube", "display_name": "Under-lubrication",
            "category": "MAINTENANCE", "causal_statement": "insufficient lube"}
    sop = {"id": "sop:SOP-114:REV-C", "display_name": "Bearing Lube", "sop_number": "SOP-114",
           "title": "Bearing Lubrication", "revision": "REV-C", "status": "ACTIVE"}

    async def _run():
        await repo.upsert_node("Asset", asset["id"], asset)
        await repo.upsert_node("Component", component["id"], component)
        await repo.upsert_node("Sensor", sensor["id"], sensor)
        await repo.upsert_node("FailureMode", failure["id"], failure)
        await repo.upsert_node("RootCause", root["id"], root)
        await repo.upsert_node("SOP", sop["id"], sop)
        await repo.link_component_to_asset(component["id"], asset["id"])
        await repo.link_sensor_to_component(sensor["id"], component["id"])
        await repo.link_sensor_anomaly_to_failure_mode(
            sensor["id"], failure["id"], {"metric": "bearing_temp", "confidence_weight": 0.82}
        )
        await repo.link_failure_mode_to_root_cause(failure["id"], root["id"], {"causal_confidence": 0.7})
        await repo.link_failure_mode_to_sop(
            failure["id"], sop["id"], {"effectiveness": 0.9, "required_severity_tier": "DEGRADED"}
        )

    return _run(), asset, component, sensor, failure, root, sop


async def test_three_plus_degree_traversal_populates_context(repo):
    runner, asset, component, sensor, failure, root, sop = _seed_chain(repo)
    await runner

    api = GraphAPIService(repo)
    ctx = await api.query.get_asset_subgraph(asset["id"], max_hops=4)

    labels_present = {n.label for n in ctx.nodes}
    assert {"Asset", "Component", "Sensor", "FailureMode", "SOP", "RootCause"} <= labels_present

    edges = {(e.source_id, e.relationship, e.target_id) for e in ctx.edges}
    assert (asset["id"], "COMPRISED_OF", component["id"]) in edges
    assert (component["id"], "MONITORED_BY", sensor["id"]) in edges
    assert (sensor["id"], "EXHIBITS_ANOMALY", failure["id"]) in edges
    assert (failure["id"], "MITIGATED_BY", sop["id"]) in edges

    anomaly = next(e for e in ctx.edges if e.relationship == "EXHIBITS_ANOMALY")
    assert anomaly.properties["metric"] == "bearing_temp"
    assert anomaly.properties["confidence_weight"] == 0.82
    mitigation = next(e for e in ctx.edges if e.relationship == "MITIGATED_BY")
    assert mitigation.properties["effectiveness"] == 0.9

    # Node metadata surfaced for the renderer.
    fm_node = next(n for n in ctx.nodes if n.id == failure["id"])
    assert fm_node.properties["severity_tier"] == "DEGRADED"
    assert fm_node.display_name == "Bearing Overheat"
    assert ctx.root_node_ids == [asset["id"]]


# --------------------------------------------------------------------------- #
# Validation engine
# --------------------------------------------------------------------------- #
async def test_validation_engine_flags_and_clears_gaps(repo):
    # Create a dangling sensor (no MONITORED_BY) and dangling component.
    await repo.upsert_node("Sensor", "sensor:orphan:1", {"display_name": "Orphan sensor", "metric": "x", "unit": "C"})
    await repo.upsert_node("Component", "component:orphan:1", {"display_name": "Orphan comp", "asset_id": "nope", "component_type": "BEARING"})

    validator = GraphValidationService(repo)
    report = await validator.validate()
    by_name = {f.check_name: f for f in report.findings}
    assert by_name["sensor_without_monitoring"].offending_ids == ["sensor:orphan:1"]
    assert by_name["component_without_owning_asset"].offending_ids == ["component:orphan:1"]
    assert report.healthy is False

    # Now wire them properly and re-validate: the gaps should clear.
    await repo.upsert_node("Asset", "asset:fix:1", {"display_name": "Fixer", "status": "OPERATIONAL", "tag": "F-1", "asset_type": "PUMP", "equipment_class": "ROTARY_EQUIPMENT", "criticality": "NON_CRITICAL", "location_id": "location:SRP:plant-1", "process_function": "pf"})
    await repo.link_component_to_asset("component:orphan:1", "asset:fix:1")
    await repo.upsert_node("Component", "component:host:1", {"display_name": "Host", "asset_id": "asset:fix:1", "component_type": "BEARING"})
    await repo.link_component_to_asset("component:host:1", "asset:fix:1")
    await repo.link_sensor_to_component("sensor:orphan:1", "component:host:1")

    report2 = await validator.validate()
    by_name2 = {f.check_name: f for f in report2.findings}
    assert by_name2["sensor_without_monitoring"].offending_ids == []
    assert by_name2["component_without_owning_asset"].offending_ids == []


# --------------------------------------------------------------------------- #
# Deletion decoupling
# --------------------------------------------------------------------------- #
async def test_delete_component_decouples_asset(repo):
    await repo.upsert_node("Asset", "asset:del:1", {"display_name": "A", "status": "OPERATIONAL", "tag": "A", "asset_type": "PUMP", "equipment_class": "ROTARY_EQUIPMENT", "criticality": "NON_CRITICAL", "location_id": "l", "process_function": "pf"})
    await repo.upsert_node("Component", "component:del:1", {"display_name": "C", "asset_id": "asset:del:1", "component_type": "BEARING"})
    await repo.link_component_to_asset("component:del:1", "asset:del:1")

    deleted = await repo.delete_node("Component", "component:del:1")
    assert deleted == 1

    # Asset still exists and is not left pointing at a missing child.
    assert await repo.node_exists("Asset", "asset:del:1") is True
    assert await repo.node_exists("Component", "component:del:1") is False
    rels = await repo._read(
        "MATCH (a:Asset {id:$a})-[r]->(c) RETURN count(r) AS c", {"a": "asset:del:1"}
    )
    assert rels[0]["c"] == 0


# --------------------------------------------------------------------------- #
# Relationship linkage semantics
# --------------------------------------------------------------------------- #
async def test_linkage_is_idempotent_and_guards_endpoints(repo):
    await repo.upsert_node("Component", "c:link:1", {"display_name": "C", "asset_id": "a", "component_type": "SEAL"})
    await repo.upsert_node("Sensor", "s:link:1", {"display_name": "S", "metric": "m", "unit": "C"})

    await repo.link_sensor_to_component("s:link:1", "c:link:1", {"position": "DE"})
    await repo.link_sensor_to_component("s:link:1", "c:link:1", {"position": "NDE"})

    edge_count = await repo._read(
        "MATCH (c:Component {id:$c})-[r:MONITORED_BY]->(s:Sensor {id:$s}) RETURN count(r) AS c",
        {"c": "c:link:1", "s": "s:link:1"},
    )
    assert edge_count[0]["c"] == 1
    # Last-write property wins (idempotent MERGE + ON MATCH SET +=).
    props = await repo._read(
        "MATCH (c:Component {id:$c})-[r]->(s) RETURN properties(r) AS r", {"c": "c:link:1", "s": "s:link:1"}
    )
    assert props[0]["r"]["position"] == "NDE"

    # Linking to a missing endpoint must raise a clear error.
    with pytest.raises(GraphLinkError):
        await repo.link_sensor_to_component("s:link:1", "component:does-not-exist")


# --------------------------------------------------------------------------- #
# Vector index availability
# --------------------------------------------------------------------------- #
async def test_vector_index_queryable_before_population(repo):
    await mig.apply_migrations(repo._driver, apply_existence=False, database=NEO4J_TEST_DATABASE)
    api = GraphAPIService(repo)
    # No embeddings populated yet → empty result, but the index/procedure resolves.
    # Must be a finite-norm (non-zero) vector or the engine rejects it.
    finite_embedding = [1.0] + [0.0] * (mig.DEFAULT_VECTOR_DIMENSIONS - 1)
    results = await api.query.vector_search_failure_modes(finite_embedding, k=5)
    assert results == []
