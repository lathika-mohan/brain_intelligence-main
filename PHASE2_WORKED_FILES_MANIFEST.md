# Phase 2 Worked Files Manifest

Generated: 2026-07-02
Scope: Neo4j Knowledge Graph database layer (Phase 2 — Member 3, AI & Knowledge Engineer).
No UI changes (`src/components/GraphRagPanel.tsx` untouched). No document parsing, no ML logic.

## New deliverables

| Path | Purpose |
|---|---|
| `app/graph/client.py` | Async Neo4j connection lifecycle manager (cached driver, pool/lifetime tuning, backoff retry, edition detection, healthcheck). |
| `app/graph/schema_migrations.py` | Single source of truth for constraints, RANGE/TEXT indexes, and the native VECTOR index; idempotent `apply_migrations()` runner. |
| `app/graph/graph_repository.py` | Idempotent MERGE-based Cypher builders, property flattening, async repository (upsert/get/patch/delete, guarded relationship linkage). |
| `app/graph/graph_services.py` | Typed CRUD, graph validation engine, sub-graph traversal + TEXT/VECTOR search, `GraphContextMap` mapping. |
| `migrations/neo4j/001_constraints.cypher` | Uniqueness constraints on `id` for all 16 Phase 1 labels. |
| `migrations/neo4j/002_indexes.cypher` | 42 RANGE + 23 TEXT indexes for fast GraphRAG retrieval. |
| `migrations/neo4j/003_vector_index.cypher` | Native VECTOR indexes on `FailureMode.embedding` / `SOPStep.embedding`. |
| `migrations/neo4j/004_existence_constraints_enterprise.cypher` | IS NOT NULL property constraints (Enterprise only). |
| `scripts/init_neo4j_constraints.py` | Rewritten bootstrap CLI (idempotent, full Phase 1 coverage, `--apply-existence`, `--export-cypher`). |
| `tests/conftest.py` | Live-Neo4j integration fixtures (gated/skip when no DB). |
| `tests/test_phase2_graph_unit.py` | Offline unit tests (registry, cypher builders, serialization, record mapping, contracts). |
| `tests/test_phase2_graph_integration.py` | Integration tests against a real Neo4j. |
| `docs/neo4j_phase2_implementation.md` | Phase 2 implementation & handoff documentation. |

## Reconstructed wiring (genuine missing package modules)

These were absent from the cloned snapshot but are imported across the codebase.
Reconstructed as real Phase 0 contract modules so the package imports and runs:

| Path | Why |
|---|---|
| `app/models/common.py` | Defines `AssetType`, `AssetStatus`, `TimeRange`, `APIResponse[T]`, `utc_now` used by `config.py`, `ontology.py`, `graphrag.py`, `xai.py`, routers, and tests. |
| `app/models/xai.py` | XAI contracts (`ExplanationRequest`/`ExplanationResponse`/…) imported by `app/api/v1/xai.py`. |
| `app/api/v1/router.py` | Aggregates the existing `graphrag` + `xai` routers so `app.main:app` imports. Other members' routers (decision/predictive/ingestion/health) are intentionally not stubbed here. |

## Integration points (unchanged contracts)

* Credentials come from the Phase 0 env via `app.core.config.Settings` (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, pool/timout knobs).
* Graph reads map to `app.models.graphrag.GraphNode` / `GraphEdge` / `GraphContextMap` (the contract `GraphRagPanel.tsx` renders).
* IDs follow `app.models.ontology.ID_STRATEGY_BY_LABEL`; relationship directions follow `RELATIONSHIP_CATALOG`.

## Validation performed

```
python -m pytest tests/test_phase2_graph_unit.py -q            -> 16 passed
python -m pytest tests/test_phase2_graph_integration.py -q     -> 7 passed  (live Neo4j 5.23)
python -m pytest tests/test_phase1_ontology.py -q              -> 3 passed  (regression: still green)
python scripts/init_neo4j_constraints.py                       -> 16 constraints + 67 indexes applied, 70 enterprise existence constraints skipped, 0 errors
```

Integration coverage:
* All 16 labels get uniqueness constraints; RANGE/TEXT/VECTOR indexes exist and are queryable.
* Writing a duplicate `id` fails natively (constraint enforcement); MERGE upserts are idempotent.
* A 3+ degree traversal (Asset → Component → Sensor → FailureMode → SOP) populates `GraphContextMap` with edge metadata (e.g. `EXHIBITS_ANOMALY.confidence_weight`, `MITIGATED_BY.effectiveness`).
* The validation engine flags (and clears) structural integrity gaps.
* Deleting a `:Component` decouples it (`DETACH DELETE`) without orphaning the owning `:Asset`.
* Relationship linkage is idempotent and raises a clear error when an endpoint is missing.
* The native vector index resolves even before `embedding` is populated.

## Lint / compile

```
ruff check app tests   -> clean
python -m py_compile <all package + test modules>
```
