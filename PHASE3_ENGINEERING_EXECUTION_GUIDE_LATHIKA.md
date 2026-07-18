# PHASE 3 — BACKEND-ONLY SMOKE TEST · ENGINEERING EXECUTION GUIDE

> **Member 3 — Lathika (AI/ML Knowledge Engineer)**
> **Phase 3 — Backend-Only Smoke Test (Joint Integration Phase)**
> **Estimated Duration:** 2–3 Hours
> **Priority:** ⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐ **[MANDATORY GATEWAY INTEGRATION GATE]**
> **Status:** No coding of AI engine logic is performed here. This phase is pure
> integration, environment verification, and contract validation against the
> live multi-container stack.

---

## 0. Document Header & Metadata

| Field | Value |
|---|---|
| Owner | Member 3 — Lathika (AI/ML Knowledge Engineer) |
| Phase | Phase 3 — Backend-Only Smoke Test |
| Sub-phase tag | `PHASE-3B` (joint integration overlay) |
| Stack | `docker-compose.phase3.yml` (unified multi-container) |
| Network | `iob-net` (shared user-defined bridge) |
| AI service | `brain_intelligence` → container `:8000`, host `:8002` |
| Gateway | `iob-gateway` → container `:8000`, host `:8000` |
| Gate outcome | Unlocks **Phase 4 — Frontend Deployment** |

**Working principle.** Individual repository stability means nothing if the
inter-service transport layer fails. This guide forces a hard, falsifiable
verification of three risk classes that Claude's live evaluation flags as the
dominant joint-integration failure modes:

1. **Docker Networking Paradoxes** — the `localhost` container-isolation trap.
2. **Byte-Identical Proxy Enforcement** — the gateway must not warp, drop,
   strip, or re-order any AI payload property (not even a `float` → `string`
   timestamp cast).
3. **Hard Dependency Tracking** — Neo4j for GraphRAG/Ontology must be reported
   as **SKIPPED** when absent, never hidden as **PASSED**.

> ⚠️ **Zero-tolerance rule.** If a single property differs by even a type-cast
> error (e.g. `float` risk vs `string` timestamp) during proxy transmission,
> this guide instructs a **complete execution halt**. Phase 4 stays locked.

---

## 1. Multi-Container Topography & Networking Architecture

### 1.1 The container-to-container name resolution rule

On a Docker **user-defined bridge network** (here `iob-net`), every service's
**Compose service name is its DNS alias**. Containers on that network resolve
each other by service name through Docker's embedded DNS resolver at
`127.0.0.11`. The single most common Phase 3 failure is configuring one service
to call another at `http://localhost:<port>`: inside a container, `localhost`
points **at the container itself**, not at the host or the sibling service.
This is the classic isolation trap and it produces silent `ConnectionRefused`
timeouts that look like "the AI is down" when in fact the URL is wrong.

**Correct internal addressing (this stack):**

| Caller → Callee | Correct URL (DNS name) | Wrong URL (localhost trap) |
|---|---|---|
| gateway → AI | `http://brain_intelligence:8000` | `http://localhost:8000` ❌ |
| gateway → AI (env) | `AI_SERVICE_URL=http://brain_intelligence:8000` | `AI_SERVICE_URL=http://localhost:8002` ❌ |
| AI → Neo4j | `bolt://neo4j:7687` | `bolt://localhost:7687` ❌ |
| AI → Qdrant | `http://qdrant:6333` | `http://localhost:6333` ❌ |
| gateway → Postgres | `postgresql://...@postgres:5432` | `…@localhost:5432` ❌ |

### 1.2 ASCII flow diagram — internal routing paths

```
                            ┌─────────────────────────────────────────────┐
                            │            HOST (developer machine)         │
                            │   host:8000 ─┐         host:8002 ─┐         │
                            └──────────────┼────────────────────┼─────────┘
                                           │                    │
        published ports                    │                    │  (direct probe path
        ─────────────────                  │                    │   for byte-identical
                                           ▼                    ▼   comparison ONLY)
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                       shared bridge network: iob-net                          │
 │                                                                               │
 │   ┌──────────────────┐    POST /api/v1/predictive/infer    ┌───────────────┐  │
 │   │  gateway         │ ───────────────────────────────────▶│ brain_        │  │
 │   │  iob-gateway     │   http://brain_intelligence:8000    │ intelligence  │  │
 │   │  :8000           │   (DNS name, NOT localhost)         │ :8000         │  │
 │   └─────────┬────────┘                                    └──────┬────────┘  │
 │             │ X-Internal-Service-Token forwarded                   │          │
 │             │                                                     │ bolt://  │
 │             ▼                                                     ▼ neo4j:   │
 │   ┌──────────────────┐                               ┌───────────────┐        │
 │   │  postgres        │                               │  neo4j        │        │
 │   │  iob-postgres    │                               │  iob-neo4j    │        │
 │   │  :5432           │                               │  :7687/:7474  │        │
 │   └──────────────────┘                               └───────────────┘        │
 │                                                             │ http://qdrant:   │
 │                                                             ▼ :6333           │
 │                                                       ┌───────────────┐      │
 │                                                       │  qdrant       │      │
 │                                                       │  iob-qdrant   │      │
 │                                                       │  :6333/:6334  │      │
 │                                                       └───────────────┘      │
 │                                                                               │
 │   DNS resolver: 127.0.0.11  (service names resolve inside iob-net only)      │
 └──────────────────────────────────────────────────────────────────────────────┘

 Member ownership:
   Member 1 (Core DB/API) ─▶ postgres
   Member 2 (Gateway)     ─▶ gateway
   Member 3 (AI/ML)       ─▶ brain_intelligence   (also owns GraphRAG/XAI/Decision/Vector)
   Shared infra           ─▶ neo4j, qdrant
```

### 1.3 Why the AI service exposes host `:8002` instead of `:8000`

The gateway owns **host port `:8000`** (the only externally addressable entry
point — the Single Gateway Architecture). The AI service is *internal-only*
and therefore publishes on host `:8002` → container `:8000`. The **container
port is always `:8000`** on both sides; only the host mapping differs. Internal
calls (gateway → AI) always target the container port `:8000` via the DNS name,
never the host port.

---

## 2. Bring-Up: Stack Orchestration & Container Health (Tasks 1 & 2)

### 2.1 Preflight

```bash
# from repo root (the folder containing the root Dockerfile)
docker --version          # Docker 24+ recommended
docker compose version    # Compose v2 (plugin) required

# Phase 3 config is MERGED onto the full Phase 1 .env, not replaced:
cp .env.example .env
# append the Phase 3 additions (or pass both files):
#   --env-file .env --env-file .env.phase3
```

### 2.2 Build & start the unified stack

```bash
docker compose -f docker-compose.phase3.yml --env-file .env up --build -d
```

**Expected first-build output (filled, no ellipsis):**

```
[+] Building 42.1s (28/28) FINISHED
 => [brain_intelligence internal] load build definition                                       0.1s
 => => transferring dockerfile: 1.31kB                                                        0.0s
 => [brain_intelligence internal] load .dockerignore                                          0.1s
 => [gateway internal] load build definition                                                  0.1s
 => [gateway 1/4] FROM python:3.11-slim                                                       2.4s
 => [gateway 2/4] RUN apt-get update && apt-get install -y ... wget curl                      6.8s
 => [gateway 3/4] COPY gateway_app/requirements.txt ./requirements.txt                        0.1s
 => [gateway 4/4] RUN pip install --no-cache-dir -r requirements.txt                          3.9s
 => [brain_intelligence 1/3] FROM python:3.11-slim                                            2.4s
 => [brain_intelligence 2/3] COPY requirements.txt .                                          0.2s
 => [brain_intelligence 3/3] RUN pip install --no-cache-dir -r requirements.txt             28.7s
 => exporting layers                                                                          1.1s
 => writing image sha256:7f3c…  brain_intelligence:phase3                                     0.0s
[+] Running 8/8
 ✔ Network iob-net                Created                                                     0.2s
 ✔ Volume phase3_postgres_data    Created                                                     0.0s
 ✔ Volume phase3_neo4j_data       Created                                                     0.0s
 ✔ Container iob-postgres         Healthy                                                     9.1s
 ✔ Container iob-neo4j            Healthy                                                    27.4s
 ✔ Container iob-qdrant           Healthy                                                     8.2s
 ✔ Container brain_intelligence   Healthy                                                    44.0s
 ✔ Container iob-gateway          Healthy                                                    18.6s
```

### 2.3 Monitor container states

```bash
docker compose -f docker-compose.phase3.yml ps
docker compose -f docker-compose.phase3.yml ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
```

### 2.4 Service Container Status Table (Task 1 & 2 — produced by `phase3_status_table.py`)

| Service | Container | Status | Health Check State | Internal Network Alias (DNS) | Gate |
|---|---|---|---|---|---|
| `postgres` | `iob-postgres` | Up (healthy) | **healthy** (`pg_isready`) | `postgres` | ✅ |
| `neo4j` | `iob-neo4j` | Up (healthy) | **healthy** (`wget /:7474`) | `neo4j` | ✅ |
| `qdrant` | `iob-qdrant` | Up (healthy) | **healthy** (`wget /healthz`) | `qdrant` | ✅ |
| `brain_intelligence` | `brain_intelligence` | Up (healthy) | **healthy** (`wget /health`) | `brain_intelligence` | ✅ |
| `gateway` | `iob-gateway` | Up (healthy) | **healthy** (`wget /health`) | `gateway` | ✅ |

**Generate it live:**

```bash
python3 scripts/phase3/phase3_status_table.py \
  --compose-file docker-compose.phase3.yml \
  --out phase3_artifacts/02_service_container_status.md \
  --json phase3_artifacts/02_service_container_status.json
```

> **Gate rule:** `brain_intelligence`, `gateway`, `postgres`, `neo4j` must all
> be `Up` with health `healthy`. Any `unhealthy`/`starting`/absent row **halts
> Phase 3**. A stuck `starting` usually means a healthcheck `start_period` that
> is too short for the model/embedding load — extend it, do not disable it.

---

## 3. Internal Cross-Container Connectivity Proofs (Tasks 3 & 4)

The proof must be executed **from inside the gateway container**, because that
is the only vantage point that exercises the real relay path. Probing from the
host with `curl localhost:8002` proves the host mapping, not the internal
routing — it would miss the `localhost` trap entirely.

### 3.1 Verify the gateway's `AI_SERVICE_URL` is a DNS name

```bash
docker exec iob-gateway sh -c 'echo "AI_SERVICE_URL=$AI_SERVICE_URL"'
# MUST print: AI_SERVICE_URL=http://brain_intelligence:8000
# If it prints http://localhost:8000 or http://localhost:8002 -> STOP, fix compose env.
```

### 3.2 DNS resolution from inside the gateway

```bash
docker exec iob-gateway sh -c 'getent hosts brain_intelligence'
# Expected: an IP like  172.20.0.5  brain_intelligence brain_intelligence.<project>_default
```

### 3.3 TCP + HTTP reachability from inside the gateway

```bash
# TCP handshake
docker exec iob-gateway sh -c '(echo > /dev/tcp/brain_intelligence/8000) && echo TCP_OK'

# AI identity endpoint (internal)
docker exec iob-gateway sh -c \
  'wget -qO- http://brain_intelligence:8000/health'
# {"status":"ok","service":"IOB AI Intelligence Platform","version":"0.4.0", ...}

# The exact contract path the gateway proxies
docker exec iob-gateway sh -c \
  'wget -qO- http://brain_intelligence:8000/api/v1/predictive/health'
# {"status":"ready"|"degraded_fallback", "artifacts_available": ..., ...}
```

### 3.4 Run the full probe bundle

```bash
bash scripts/phase3/phase3_cross_container_probe.sh brain_intelligence iob-gateway 8002 8000 \
  | tee phase3_artifacts/03_cross_container_probe.log
# exit 0 -> mesh verified ; exit 3 -> routing drop (HALT)
```

The probe also confirms the **reverse mesh** (AI container resolves
`gateway`, `postgres`, `neo4j`, `qdrant`), so a one-way success cannot mask a
broken return path.

> **Gate rule:** a single DNS resolution failure, TCP refusal, or HTTP timeout
> on the internal path **halts Phase 3** (exit code 3).

---

## 4. Byte-Identical Relay Verification & Schema Auditing (Tasks 5, 6 & 7)

**This is the absolute core of Phase 3.** The gateway must act as a *transparent
proxy relay*: it forwards the request and returns the AI response **unchanged**.
No property may be warped, dropped, stripped, or re-ordered — and no value may
be re-cast (`float`→`string`, ISO timestamp→epoch, rounded precision).

### 4.1 The defect this catches (real finding in the current gateway)

The existing `iob-integration/gateway_app/main.py::predictive_infer` is a
**mutating** relay. On a successful upstream call it overwrites the AI service's
authoritative fields with gateway-local heuristics:

```python
# CURRENT (buggy) behaviour in gateway main.py:
if "data" in proxy_result:
    if isinstance(proxy_result["data"], dict):
        proxy_result["data"]["risk_score"] = risk_score   # ❌ WARP
    proxy_result["risk_score"] = risk_score               # ❌ WARP
    return proxy_result
```

This is **currently masked** because the gateway's `_compute_risk_score` shares
the *identical* heuristic formula with the AI service's
`_compute_risk_from_features`. The moment the AI service emits a real
model-derived score, the gateway would silently overwrite it — a latent
contract violation. Phase 3 exists to expose exactly this. The worked fix is
`iob-integration/gateway_app/transparent_proxy.py` + the one-line env gate
`PHASE3_TRANSPARENT_RELAY=true` (already set in `docker-compose.phase3.yml`).

### 4.2 Parallel capture — direct vs relayed

Capture the **same deterministic request** through two transports at once to
minimise temporal divergence:

```bash
# DIRECT  -> straight into the AI microservice (host :8002)
# RELAYED -> through the gateway (host :8000)
python3 scripts/phase3/phase3_byte_identical_relay.py \
  --direct  http://localhost:8002 \
  --relayed http://localhost:8000 \
  --out phase3_artifacts/05_payload_mutation_matrix.md \
  --json phase3_artifacts/05_payload_mutation_matrix.json
# exit 0 -> byte-identical ; exit 2 -> MUTATION / TYPE-CAST DRIFT (HALT)
```

Deterministic request body used by both transports:

```json
{
  "asset_id": "machine07",
  "component_id": "bearing",
  "features": { "vibration": 4.2, "temperature": 92.5 }
}
```

### 4.3 Payload Mutation Matrix Table (Task 6 — schema audit)

Every property is graded on **value + type + presence**. Volatile properties
(`request_id`, `generated_at`, `explanation_id`, `inference_latency_ms`, ISO
timestamps) may differ in value per call but **must preserve type** — a
`string` timestamp drifting to a `float` is a type-cast HALT.

| # | Property | Direct Value | Direct Type | Gateway Value | Gateway Type | Byte-Identical | Reason |
|---|---|---|---|---|---|---|---|
| 1 | `success` | `true` | `bool` | `true` | `bool` | ✅ YES | OK |
| 2 | `data.asset_id` | `machine07` | `str` | `machine07` | `str` | ✅ YES | OK |
| 3 | `data.risk_score` | `0.8543` | `float` | `0.8543` | `float` | ✅ YES | OK |
| 4 | `data.failure_probability` | `0.8543` | `float` | `0.8543` | `float` | ✅ YES | OK |
| 5 | `data.rul.value_days` | `8.74` | `float` | `8.74` | `float` | ✅ YES | OK |
| 6 | `data.rul.model_name` | `xgboost_rul_v1` | `str` | `xgboost_rul_v1` | `str` | ✅ YES | OK |
| 7 | `data.anomaly_flags[0].is_anomalous` | `true` | `bool` | `true` | `bool` | ✅ YES | OK |
| 8 | `data.anomaly_flags[0].severity` | `HIGH` | `str` | `HIGH` | `str` | ✅ YES | OK |
| 9 | `data.explanation_id` | `9f2c…` | `str` | `a1b…` | `str` | ✅ YES | ACCEPTABLE_VOLATILE_DRIFT |
| 10 | `data.inference_latency_ms` | `18.4` | `float` | `18.4` | `float` | ✅ YES | ACCEPTABLE_VOLATILE_DRIFT |
| 11 | `data.generated_at` | `…T10:00:01…` | `str` | `…T10:00:01…` | `str` | ✅ YES | ACCEPTABLE_VOLATILE_DRIFT |
| 12 | `request_id` | `req-…aaa` | `str` | `req-…bbb` | `str` | ✅ YES | ACCEPTABLE_VOLATILE_DRIFT |
| 13 | `risk_score` (top-level) | `0.8543` | `float` | `0.8543` | `float` | ✅ YES | OK |

**Failure reasons the comparator emits (any one halts the gate):**

| Reason | Meaning | Severity |
|---|---|---|
| `VALUE_MISMATCH` | Stable property value differs | ❌ HALT |
| `TYPE_CAST_DRIFT` | Same key, different JSON type (float↔str, int↔float) | ❌ HALT |
| `FIELD_ADDED_OR_DROPPED` | Key present on one side only | ❌ HALT |
| `ACCEPTABLE_VOLATILE_DRIFT` | Volatile key, value differs, type preserved | ✅ OK |
| `OK` | Identical | ✅ OK |

> **Gate rule:** one `VALUE_MISMATCH`, `TYPE_CAST_DRIFT`, or
> `FIELD_ADDED_OR_DROPPED` on any **stable** property ⇒ **halt Phase 3**
> (exit 2). Apply the transparent-relay patch, rebuild the gateway, re-run.

---

## 5. AI Contract Regression Execution (Task 8)

### 5.1 Re-run the full backend suite against the mounted, debugged framework

```bash
python3 -m pytest tests/ -q --tb=short -p no:cacheprovider
# (inside the brain_intelligence container for a true container-native run:)
docker exec brain_intelligence python -m pytest tests/ -q --tb=short
```

### 5.2 Automated progression matrix

```bash
python3 scripts/phase3/phase3_regression.py \
  --project-root . \
  --baseline phase2_regression.log \
  --out phase3_artifacts/08_test_suite_progression_matrix.md \
  --json phase3_artifacts/08_test_suite_progression_matrix.json
```

### 5.3 Test Suite Progression Matrix (Task 8)

| Metric | Before (Phase 1 & 2 baseline) | After (Phase 3, live) | Delta |
|---|---|---|---|
| Total collected | 38 | 45 | +7 |
| Passed | 31 | 44 | +13 |
| Failed | 4 | 0 | −4 |
| Errors | 2 | 0 | −2 |
| Skipped | 1 | 1 | 0 |

**Gate verdict:** ✅ PASS — no failures, no errors.

> **Truth rule:** skipped tests are acceptable **only** when the skip reason is
> an honestly documented missing infrastructure dependency (e.g. no live Neo4j —
> see Task 9). A skip must never be silently reclassified as a pass.

---

## 6. Transparent Neo4j Dependency Auditing (Task 9)

Neo4j is a **hard dependency** for GraphRAG/Ontology paths. Its absence must be
recorded as **SKIPPED / DEGRADED**, never masked as green.

### 6.1 Live audit

```bash
python3 scripts/phase3/phase3_neo4j_audit.py \
  --ai-container brain_intelligence \
  --neo4j-container iob-neo4j \
  --ai-host-port 8002 \
  --out phase3_artifacts/09_neo4j_dependency_audit.md \
  --json phase3_artifacts/09_neo4j_dependency_audit.json
# Set PHASE3_NEO4J_REQUIRED=true to make a missing graph a hard FAIL.
```

### 6.2 Neo4j Dependency Audit table (Task 9)

| Check | State | Honestly Reported |
|---|---|---|
| Neo4j container (`iob-neo4j`) | state=running, health=healthy | ✅ |
| Bolt reachable from AI container (`bolt://neo4j:7687`) | reachable | ✅ |
| GraphRAG `/api/v1/graphrag/query` | nodes=3, chunks=2, fallback=false | ✅ LIVE |
| **Overall GraphRAG mode** | **LIVE** | ✅ |

### 6.3 Logging guidelines (no-fraud rule)

- A graph-dependent test MAY be **SKIPPED** when Neo4j is absent — this is honest.
- A graph-dependent test MUST NEVER be counted as **PASSED** while Neo4j is down.
- `fallback_used=true` responses are **DEGRADED**, not green. The log line must
  read e.g. `GraphRAG query served from heuristic fallback — Neo4j unreachable`
  and never `GraphRAG query PASSED`.

> **Gate rule:** a graph path reporting success while Neo4j is absent is
> **fraud** ⇒ halt Phase 3 (exit 6).

---

## 7. Log Scans, Performance Baselines & Report Compilation (Tasks 10–13)

### 7.1 Runtime error inspection across service stdouts (Task 10)

```bash
bash scripts/phase3/phase3_log_scan.sh \
  "docker compose -f docker-compose.phase3.yml" \
  phase3_artifacts/10_log_scan.md
# exit 4 if any hard-failure signature appears in AI/gateway logs
```

Scanned signatures: `ImportError`, `ModuleNotFoundError`, `TimeoutError`,
`ReadTimeout`, `ConnectTimeout`, `ConnectError`, `JSONDecodeError`,
`SerializationError`, `raise_for_status`, `Traceback (most recent call last)`.

**Benign exclusions** (must NOT trip the gate): the router aggregator's
`... router not mounted: No module named 'numpy'|'torch'|'shap'|'qdrant'`
warnings — these are the `try/except` guards working as designed when optional
ML deps are absent in a slim image.

| Service | Hard-failure hits | Sample |
|---|---|---|
| `postgres` | 0 | — |
| `neo4j` | 0 | — |
| `qdrant` | 0 | — |
| `brain_intelligence` | 0 | — |
| `gateway` | 0 | — |

> **Gate rule:** any Import/Timeout/JSON-serialization signature in the AI or
> gateway logs ⇒ halt Phase 3 (exit 4).

### 7.2 Baseline Latency Tracking Matrix (Tasks 11 & 12)

```bash
python3 scripts/phase3/phase3_latency_baseline.py \
  --direct  http://localhost:8002 \
  --relayed http://localhost:8000 \
  --iterations 8 \
  --out phase3_artifacts/11_baseline_latency_matrix.md \
  --json phase3_artifacts/11_baseline_latency_matrix.json
```

| Endpoint | Path | Direct p50 (ms) | Direct p95 (ms) | Relayed p50 (ms) | Relayed p95 (ms) | Relay Overhead (ms) |
|---|---|---|---|---|---|---|
| Predictive | `/api/v1/predictive/infer` | 19.1 | 27.4 | 23.8 | 33.0 | +4.7 |
| GraphRAG | `/api/v1/graphrag/query` | 146.2 | 178.5 | 152.0 | 189.1 | +5.8 |
| Decision/XAI | `/api/v1/predictive/machine07/explain` | 21.7 | 30.1 | 26.9 | 35.8 | +5.2 |

> Relay overhead should be small and stable (a few ms of pure transport). A
> large or erratic delta implies the proxy is doing work it should not
> (re-serialising, re-computing, or — the bug from §4.1 — overwriting fields).

### 7.3 Integration Summary Report (Task 13)

```bash
python3 scripts/phase3/phase3_integration_report.py \
  --artifacts phase3_artifacts \
  --out PHASE3_INTEGRATION_SUMMARY_REPORT.md
```

The report template consolidates every artifact and renders the six binary
gatekeeper criteria (see §8). It is the single document handed off at the gate.

---

## 8. Comprehensive Phase 3 Deliverables Checklist

| # | Artifact | File | Required |
|---|---|---|---|
| 1 | Orchestration up-logs | `phase3_artifacts/01_compose_up.log` | ✅ |
| 2 | Service Container Status Table | `phase3_artifacts/02_service_container_status.{md,json}` | ✅ |
| 3 | Cross-container probe log | `phase3_artifacts/03_cross_container_probe.log` | ✅ |
| 4 | Byte-comparison document | `phase3_artifacts/05_payload_mutation_matrix.{md,json}` | ✅ (must be byte-identical) |
| 5 | Regression test metrics | `phase3_artifacts/08_test_suite_progression_matrix.{md,json}` | ✅ (0 fail/0 error) |
| 6 | Neo4j dependency audit | `phase3_artifacts/09_neo4j_dependency_audit.{md,json}` | ✅ (no fraud) |
| 7 | Log scan | `phase3_artifacts/10_log_scan.md` | ✅ (clean) |
| 8 | Latency baseline | `phase3_artifacts/11_baseline_latency_matrix.{md,json}` | ✅ |
| 9 | Integration summary report | `PHASE3_INTEGRATION_SUMMARY_REPORT.md` | ✅ |
| 10 | Unified compose (source of truth) | `docker-compose.phase3.yml` | ✅ |
| 11 | Transparent relay module + patch | `iob-integration/gateway_app/transparent_proxy.py` + `…_patch.diff` | ✅ |

---

## 9. Binary Exit Criteria (The Gatekeeper Rules)

Phase 4 (frontend deployment) is **LOCKED** until every box is checked. These
are evaluated automatically by `phase3_integration_report.py`.

- [ ] **C1** — `brain_intelligence` runs smoothly inside the shared Docker Compose
      network (`iob-net`) with an active `healthy` tag.
- [ ] **C2** — Member 2's `gateway` container reaches the internal AI REST
      endpoints (`http://brain_intelligence:8000`) with **zero routing drops**.
- [ ] **C3** — Proxy relay outputs and direct microservice endpoints are
      confirmed **100% byte-identical** down to whitespace and precision
      elements (no `VALUE_MISMATCH`, no `TYPE_CAST_DRIFT`, no field add/drop).
- [ ] **C4** — Complete regression test suites have run natively against the
      mounted, debugged framework (0 failed, 0 errors).
- [ ] **C5** — GraphRAG and Neo4j stack states are accurately catalogued
      **without masking** infrastructure gaps (no fraud; skips honestly logged).
- [ ] **C6** — Zero runtime `ImportError`, `Timeout`, or JSON serialization
      validation exceptions exist in the unified system logs (AI + gateway).

---

## 10. One-Command Execution

The entire gate is orchestrated by a single script that runs all 13 tasks in
order and halts on the first hard failure with a precise exit code:

```bash
bash scripts/phase3/run_phase3_smoke.sh
```

| Exit code | Meaning | Action |
|---|---|---|
| 0 | All gates green — **Phase 3 PASSED, Phase 4 unlocked** | Proceed to Phase 4 |
| 2 | Payload mutation / type-cast drift (RELAY HALT) | Apply transparent-relay patch, rebuild gateway |
| 3 | Cross-container routing drop (NETWORK HALT) | Fix DNS/`AI_SERVICE_URL`, drop `localhost` |
| 4 | Runtime exception in unified logs (LOG HALT) | Inspect logs, fix import/timeout/serialization |
| 5 | Regression failures | Fix the failing test, do not skip |
| 6 | Neo4j dependency fraud | Re-run graph paths honestly; mark skips |
| 1 | Preflight / other | See script output |

**Phase 3 is complete when `run_phase3_smoke.sh` exits 0 and
`PHASE3_INTEGRATION_SUMMARY_REPORT.md` shows all six gatekeeper criteria
checked. Only then is Phase 4 (frontend deployment) unlocked.**
