# IOB AI Intelligence Platform (`ai-platform/`)

Industrial Operating Brain — AI & Knowledge Engineering subsystem.
**Phase 0: AI Architecture & Contracts.**

Owner: Member 3 (AI & Knowledge Engineer).

> Scope note: this phase freezes API/graph/vector contracts and stands up
> a runnable, contract-valid FastAPI skeleton. **No ML pipeline logic**
> (real GraphRAG fusion, XGBoost training, SHAP computation, LangGraph
> agent flows) is implemented yet — every route below returns a
> schema-accurate stub payload so downstream teams (Frontend, Platform
> Backend) can integrate today.

---

## Directory Structure

```
ai-platform/
├── app/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── core/
│   │   └── config.py            # Pydantic Settings (env-driven)
│   ├── api/
│   │   └── v1/
│   │       ├── router.py        # Aggregates all v1 routers
│   │       ├── health.py        # /health, /health/ready
│   │       ├── ingestion.py     # POST /ingestion/telemetry (upstream contract)
│   │       ├── graphrag.py      # POST /graphrag/query
│   │       ├── predictive.py    # POST /predictive/infer
│   │       ├── xai.py           # POST /xai/explain
│   │       └── decision.py      # POST /decision/recommend
│   ├── graph/
│   │   ├── schema.py            # Neo4j label/relationship constants
│   │   └── client.py            # Neo4j driver lifecycle
│   ├── vector/
│   │   ├── schema.py            # Qdrant collection constants
│   │   └── client.py            # Qdrant client lifecycle
│   ├── models/                  # Pydantic v2 schemas (the frozen contracts)
│   │   ├── common.py            # Shared envelope/enums (APIResponse, etc.)
│   │   ├── telemetry.py         # Upstream contract (Member 2)
│   │   ├── graphrag.py          # GraphRAG Engine contracts
│   │   ├── predictive.py        # Predictive Maintenance contracts
│   │   ├── xai.py               # Explainability contracts
│   │   └── decision.py          # Decision Engine contracts
│   └── agents/                  # Reserved for LangGraph orchestration (later phase)
├── docs/
│   ├── neo4j_schema.md          # Graph schema specification
│   ├── qdrant_schema.md         # Vector collection specification
│   ├── api_contracts.md         # Human-readable API contract reference
│   └── team_coordination.md     # Upstream/downstream integration notes
├── scripts/
│   ├── init_neo4j_constraints.py
│   └── init_qdrant_collections.py
├── tests/
│   └── test_contracts.py        # Schema + endpoint smoke tests
├── docker-compose.yml           # Neo4j + Qdrant local dev stack
├── Dockerfile                   # AI platform service container
├── requirements.txt             # Frozen pinned dependencies
├── pyproject.toml               # Project metadata + tool config
└── .env.example                 # Full environment contract
```

---

## Quickstart

### 1. Python environment

```bash
cd ai-platform
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit secrets as needed
```

### 2. Start Neo4j + Qdrant (Docker)

```bash
docker compose up -d
```

- Neo4j Browser: http://localhost:7474 (user: `neo4j`, password from `.env`)
- Qdrant REST: http://localhost:6333/dashboard

### 3. Bootstrap graph constraints & vector collections

```bash
python scripts/init_neo4j_constraints.py
python scripts/init_qdrant_collections.py
```

### 4. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json
- Health: http://localhost:8000/api/v1/health

### 5. Run tests

```bash
pytest -q
```

---

## Contract Freeze Summary

| Concern                        | Spec file                     | Code module                  |
|---------------------------------|--------------------------------|--------------------------------|
| Response envelope               | `docs/api_contracts.md`        | `app/models/common.py`        |
| GraphRAG (`GraphRagPanel.tsx`)  | `docs/api_contracts.md` §1     | `app/models/graphrag.py`      |
| Predictive Maintenance (`DigitalTwinView.tsx`) | `docs/api_contracts.md` §2 | `app/models/predictive.py` |
| XAI (`ShapExplainability.tsx`)  | `docs/api_contracts.md` §3     | `app/models/xai.py`           |
| Decision Engine                 | `docs/api_contracts.md` §4     | `app/models/decision.py`      |
| Telemetry ingestion (upstream)  | `docs/api_contracts.md` §5     | `app/models/telemetry.py`     |
| Graph storage schema            | `docs/neo4j_schema.md`         | `app/graph/schema.py`         |
| Vector storage schema           | `docs/qdrant_schema.md`        | `app/vector/schema.py`        |
| Team boundaries                 | `docs/team_coordination.md`    | —                              |

No frontend files were created or modified as part of this delivery.
