# Phase 3B Worked Files Manifest

Generated: 2026-07-17
Scope: Phase 3 — Backend-Only Smoke Test (Joint Integration Gate)
Owner: Member 3 — Lathika (AI/ML Knowledge Engineer)
Repo: `brain_intelligence-main`

## Guiding principle

Phase 3 is integration, environment verification, and contract validation. **No
`app/` AI-engine source is modified** (editing a frozen Phase 0 contract here
would create the very defect this gate prevents). All deliverables are additive.

## Deliverables

### A. Unified multi-container stack (the integration substrate)

| Path | Purpose |
|---|---|
| `docker-compose.phase3.yml` | Single source of truth for the joint stack: `postgres` (M1), `gateway` (M2), `brain_intelligence` (M3), `neo4j`, `qdrant` on shared `iob-net`. Enforces internal DNS addressing (`AI_SERVICE_URL=http://brain_intelligence:8000`), healthchecks with `depends_on: condition: service_healthy`, and `PHASE3_TRANSPARENT_RELAY=true`. |
| `.env.phase3.example` | Phase 3 networking/integration tunables to **merge** into `.env` (AI_SERVICE_URL, AI_PLATFORM_URL, NEO4J_URI, QDRANT_URL, SERVICE_API_KEY, PHASE3_NEO4J_REQUIRED, etc.). Phase 1 embedding lock untouched. |
| `.dockerignore` | Build hygiene for the AI image (excludes frontend, node_modules, .git, caches, secrets). |

### B. Gateway transparent-relay fix (the byte-identical enforcement)

| Path | Purpose |
|---|---|
| `iob-integration/gateway_app/transparent_proxy.py` | Non-mutating relay (`relay_passthrough`) + shared `compare_payloads` comparator (value + type + presence checks; volatile-key aware). Self-tests included. |
| `iob-integration/gateway_app/Dockerfile.phase3` | Clean gateway image. Fixes the malformed `COPY __init__.py ./__init__.py 2>/dev/null \|\| true` line in the legacy Dockerfile; adds wget/curl for healthchecks. |
| `iob-integration/gateway_app_patch/phase3_main_patch.diff` | Surgical env-gated patch wiring `relay_passthrough` into `gateway_app/main.py` (Member 2 to apply). Inert unless `PHASE3_TRANSPARENT_RELAY=true`. |

### C. Phase 3 automation scripts (Tasks 1–13)

| Path | Task(s) | Artifact produced |
|---|---|---|
| `scripts/phase3/run_phase3_smoke.sh` | Master | orchestrates all 13; precise exit codes |
| `scripts/phase3/phase3_status_table.py` | 1 & 2 | Service Container Status Table |
| `scripts/phase3/phase3_cross_container_probe.sh` | 3 & 4 | internal DNS mesh proof log |
| `scripts/phase3/phase3_byte_identical_relay.py` | 5–7 | Payload Mutation Matrix |
| `scripts/phase3/phase3_regression.py` | 8 | Test Suite Progression Matrix |
| `scripts/phase3/phase3_neo4j_audit.py` | 9 | Neo4j dependency truth-tracking |
| `scripts/phase3/phase3_log_scan.sh` | 10 | runtime exception scan |
| `scripts/phase3/phase3_latency_baseline.py` | 11 & 12 | Baseline Latency Matrix |
| `scripts/phase3/phase3_integration_report.py` | 13 | Integration Summary Report + 6 gate criteria |

### D. Tests

| Path | Purpose |
|---|---|
| `tests/test_phase3_byte_identical_relay.py` | 7 pure (no-network) unit tests proving the comparator detects value warp, type-cast drift, field add/drop, and preserves numeric precision + volatile-type rules. |

### E. Documentation

| Path | Purpose |
|---|---|
| `PHASE3_ENGINEERING_EXECUTION_GUIDE_LATHIKA.md` | Exhaustive step-by-step execution guide (topography, all 13 tasks, matrices, exit criteria). |
| `PHASE3_GATEWAY_TRANSPARENT_RELAY_AUDIT.md` | Root-cause of the mutating-relay defect + the byte-identical fix. |
| `INSTALL_PHASE3B_OVERLAY.md` | Unzip/apply/rollback instructions. |
| `PHASE3_WORKED_FILES_MANIFEST_PHASE3B.md` | This file. |

## Key engineering decisions

1. **Service named `brain_intelligence`** (not the legacy `ai-platform`) so the
   internal DNS alias matches the platform identity and the gateway targets
   `http://brain_intelligence:8000` — the canonical Phase 3 address. Container
   port `:8000` everywhere; host `:8002` (AI) / `:8000` (gateway).
2. **`APP_ENV=development`** on the AI service so the `InternalOnlyGuardMiddleware`
   permits the gateway relay during smoke testing (the gateway does not yet
   forward `X-Internal-Service-Token`). Documented; production flips to
   `production` once Member 2 forwards the token.
3. **Volatile-vs-stable classification** in `compare_payloads`: timestamps and
   UUIDs may differ per call but must keep their JSON type — a `string`→`float`
   timestamp drift is a hard HALT, exactly per the zero-tolerance rule.
4. **Neo4j no-fraud rule**: a graph path may SKIP when Neo4j is absent, but may
   never be counted as PASSED; `fallback_used=true` is DEGRADED, not green.

## Verification performed (offline, no live Docker daemon)

```bash
# all Python compiles
python3 -m py_compile scripts/phase3/*.py iob-integration/gateway_app/transparent_proxy.py tests/test_phase3_byte_identical_relay.py

# compose is valid YAML, all services on iob-net
python3 -c "import yaml; d=yaml.safe_load(open('docker-compose.phase3.yml')); \
print(sorted(d['services']), list(d['networks']))"

# transparent relay self-test detects mutation, passes on clean copy
PYTHONPATH=iob-integration python3 iob-integration/gateway_app/transparent_proxy.py

# 7/7 relay comparator unit tests pass
PYTHONPATH=iob-integration python3 -m pytest tests/test_phase3_byte_identical_relay.py -q
# .......  7 passed

# bash scripts are syntactically valid
bash -n scripts/phase3/run_phase3_smoke.sh
bash -n scripts/phase3/phase3_cross_container_probe.sh
bash -n scripts/phase3/phase3_log_scan.sh
```

> The runtime stack (`docker compose up --build`) and the live probes are
> executed by Lathika via `bash scripts/phase3/run_phase3_smoke.sh` against the
> team's Docker host; this manifest records the offline pre-verification only.
