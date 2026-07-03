# Phase 2 — Neo4j Knowledge Graph Implementation

**Project:** Industrial Operating Brain (IOB) — AI Intelligence Platform
**Owner:** Member 3 — AI & Knowledge Engineer
**Status:** Implemented & integration-tested against Neo4j 5.x
**Upstream contracts:** `docs/neo4j_schema.md` (Phase 0, 5 labels) → `docs/industrial_knowledge_ontology.md` + `app/models/ontology.py` (Phase 1, 16 labels)

This document is the executable companion to the Phase 1 ontology. It describes
how the static ontology becomes a live, high-performance graph database layer:
constraints, indexes, a vector index, an async repository, typed CRUD/query
services, a validation engine, and a test suite. It does **not** touch the
frontend (`src/components/GraphRagPanel.tsx` is untouched) and contains no
parser or ML logic.

---

## 1. What was built

| Layer | Module | Responsibility |
|---|---|---|
| Connection lifecycle | `app/graph/client.py` | Thread-safe async driver singleton, pool/lifetime config, backoff retry, edition detection, healthcheck |
| Migration registry | `app/graph/schema_migrations.py` | Single source of truth for all constraints/indexes/vector index; idempotent `apply_migrations()` runner |
| Migration artifacts | `migrations/neo4j/*.cypher` | 4 generated, idempotent (``IF NOT EXISTS``) Cypher files |
| Bootstrap CLI | `scripts/init_neo4j_constraints.py` | Applies schema from env creds; can `--export-cypher` or `--apply-existence` |
| Repository | `app/graph/graph_repository.py` | Pure MERGE-based Cypher builders, property flattening, idempotent upserts, `DETACH DELETE`, guarded relationship linkage |
| Services | `app/graph/graph_services.py` | Typed CRUD, validation engine, sub-graph traversal, TEXT/VECTOR search, `GraphContextMap` mapping |
| Tests | `tests/test_phase2_graph_unit.py`, `tests/test_phase2_graph_integration.py`, `tests/conftest.py` | Offline unit + live-DB integration |

### Reconstructed wiring (genuine missing package modules)
`app/models/common.py`, `app/models/xai.py`, and `app/api/v1/router.py` were
missing from the cloned snapshot but are imported throughout the codebase
(`app.main:app`, the routers, `scripts/init_neo4j_constraints.py`). They were
reconstructed as real Phase 0 contract modules so the package imports cleanly:
`APIResponse[T]` envelope, `AssetType`/`AssetStatus`/`TimeRange`, the XAI
contract, and a router that aggregates the existing `graphrag` + `xai` routers.
No mock/dummy stubs were added.

---

## 2. Constraints & indexes

All statements are idempotent (`IF NOT EXISTS`).

* **Uniqueness (`IS UNIQUE`) on `id`** for all 16 Phase 1 labels
  (`001_constraints.cypher`).
* **IS NOT NULL property-existence constraints** on critical operational fields
  (`004_existence_constraints_enterprise.cypher`). These are **Enterprise
  Edition only** — Community silently cannot enforce them. `apply_migrations`
  detects the running edition from the *passed driver* and applies them only on
  Enterprise (or when `--apply-existence` is forced).
* **RANGE indexes** (42) on filtered/sorted fields (status, criticality,
  asset_id, equipment_class, severity_tier, …) in `002_indexes.cypher`.
* **TEXT indexes** (23) on searched string fields (display_name, tag, title,
  sop_number, causal_statement, chunk text, …) for index-backed `CONTAINS`.

### Vector index (hybrid structural + semantic readiness)
```
CREATE VECTOR INDEX vector_FailureMode_embedding IF NOT EXISTS
  FOR (n:`FailureMode`) ON (n.embedding)
  OPTIONS { indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'} }

CREATE VECTOR INDEX vector_SOPStep_embedding IF NOT EXISTS
  FOR (n:`SOPStep`) ON (n.embedding)
  OPTIONS { indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'} }
```
The `embedding` property is populated by Phase 3 (embeddings). The index is
created ahead of population so semantic similarity lookup via
`db.index.vector.queryNodes(...)` is ready immediately. Queryable now via
`GraphQueryService.vector_search_failure_modes(...)`.

---

## 3. Repository & services API (how downstream phases call it)

```python
from app.graph.client import GraphDriverManager
from app.graph.graph_services import GraphAPIService

# Connect (cached async driver from Phase 0 env).
api = await GraphAPIService.connect()

# Upsert any ontology entity (idempotent MERGE; never blind CREATE).
await api.crud.upsert_entity(asset)

# Draw canonical edges (directions follow RELATIONSHIP_CATALOG):
#   (Asset)-[:COMPRISED_OF]->(Component)
#   (Component)-[:MONITORED_BY]->(Sensor)
#   (Sensor)-[:EXHIBITS_ANOMALY]->(FailureMode)   # requires metric + confidence_weight
#   (FailureMode)-[:TRIGGERED_BY]->(RootCause)
#   (FailureMode)-[:MITIGATED_BY]->(SOP)          # carries effectiveness
await api.repository.link_component_to_asset(component.id, asset.id)
await api.repository.link_sensor_to_component(sensor.id, component.id)
await api.repository.link_sensor_anomaly_to_failure_mode(sensor.id, fm.id,
    {"metric": sensor.metric, "confidence_weight": 0.82})

# Expand an asset's knowledge sub-graph for GraphRAG (returns Phase 0 contract).
ctx: GraphContextMap = await api.query.get_asset_subgraph(asset.id, max_hops=3)

# Audit integrity against the ontology.
report = await api.validation.validate()   # GraphValidationReport
```

`build_subgraph_query`/`_records_to_graph_context` are pure functions (unit
testable without a database). The hop bound is inlined as a literal because
Cypher forbids parameterizing a variable-length quantifier.

---

## 4. Validation engine

`GraphValidationService.validate()` returns a `GraphValidationReport` flagging
structural gaps, e.g. any `:Sensor` lacking a `MONITORED_BY` edge, any
`:Component` without an owning `:Asset` (via `COMPRISED_OF`), any `:Asset`
without a location, any `:FailureMode` without `TRIGGERED_BY`/`MITIGATED_BY`,
and `:SOP`/`:SOPStep` pairing gaps. Each finding lists the offending node IDs so
automated remediation can resolve them before GraphRAG inference.

---

## 5. Running it

```bash
# 1. Start Neo4j (compose uses neo4j:5.24-community).
docker compose up -d neo4j

# 2. Apply the Phase 2 schema (reads NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD).
python scripts/init_neo4j_constraints.py
python scripts/init_neo4j_constraints.py --apply-existence   # also enforce IS NOT NULL (Enterprise)

# 3. Run the suites.
pytest tests/test_phase2_graph_unit.py -q                    # offline
NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_USER=neo4j \
  NEO4J_TEST_PASSWORD=neo4jtest123 pytest tests/test_phase2_graph_integration.py -q
```

---

## 6. Phase 2 → Phase 3 handoff

* `embedding` properties on `FailureMode`/`SOPStep` can be populated and queried
  immediately through the existing vector index.
* `get_asset_subgraph` already returns the Phase 0 `GraphContextMap` that
  `GraphRagPanel.tsx` renders — Phase 3 only needs to wire the fusion layer onto
  `GraphAPIService`.
* All IDs follow the Phase 1 `ID_STRATEGY_BY_LABEL` keys, so telemetry
  (`TelemetryReading.asset_id`/sensor IDs) resolves into the graph.
