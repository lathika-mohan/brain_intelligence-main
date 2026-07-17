# Phase 2 Engineering Execution Guide

## 1. Document Header & Metadata

- **Role:** Member 3 (Lathika) — AI/ML Knowledge Engineer
- **Phase:** Phase 2 — Wire the Frontend Adapter In (**CRITICAL PATH**)
- **Estimated Duration:** 2–3 Hours
- **Priority:** ⭐⭐⭐⭐⭐⭐⭐⭐⭐ **MAXIMUM DENSITY - FRONTEND RELEASING**
- **Repository:** `brain_intelligence-main`
- **Validated On:** 2026-07-17
- **Validated Branch Snapshot:** GitHub default `main` clone audited in Arena workspace

---

## 2. Architectural Paradigm: Core Engine vs. Frontend Adapter

`app/ai_service/integration/ui_router.py` is **not** the ML engine.
It is the **frontend adaptation boundary**.

It must:

- call or proxy the underlying AI engines,
- flatten heavy internal outputs into UI-safe JSON,
- preserve frozen frontend keys exactly,
- avoid leaking backend-only structures directly to Member 4,
- expose stable `/api/v1/ai/ui/*` routes for the Gateway and dashboard.

It must **not**:

- retrain models,
- redefine predictive schemas,
- rename frozen UI keys,
- mutate core `/api/v1/predictive/infer` payload contracts.

### Directional Flow

`Dashboard -> Gateway -> UI Router -> Underlying Engine -> JSON Serialization -> Gateway -> UI`

### Actual Working Mount Chain in This Repo

The current repo uses a **two-stage mount chain**:

1. `app/api/v1/router.py` mounts `ai_router`
2. `app/ai_service/main_router.py` mounts `ui_router`
3. Effective public path becomes `/api/v1/ai/ui/*`

### Effective Router Wiring Graph

`app.main -> app.api.v1.router.api_router -> app.ai_service.main_router.ai_router -> app.ai_service.integration.ui_router.ui_router`

### Anti-Breaking Guardrails

**Do not rename any frozen JSON keys.**

Examples of forbidden drift:

- `confidence` → `confidence_score`
- `requestId` → `request_id` inside UI envelope
- `generatedAt` → `generated_at` inside UI envelope
- `riskScoreIfIgnored` → `risk_score_if_ignored`
- `actionId` → `action_id`

For the core predictive endpoint, preserve the existing route-level wire format exactly:

- `rul`
- `failure_probability`
- `anomaly_flags`
- `generated_at`
- `inference_latency_ms`

---

## 3. Step-by-Step Task Breakdowns (With Complete Code Paradigms)

### Task 1: Codebase Discovery & Inventory

#### Primary file locations

- `app/ai_service/integration/ui_router.py`
- `app/ai_service/main_router.py`
- `app/api/v1/router.py`
- `app/main.py`
- `tests/test_phase11_ui_router_contract.py`
- `app/api/v1/predictive.py`

#### UI Router Inventory Table

| Endpoint | Method | Purpose | Target UI Panel |
|---|---|---|---|
| `/api/v1/ai/ui/digital-twin/{asset_id}` | GET | Asset summary, telemetry cards, history series, anomaly projection | `DigitalTwinView.tsx` |
| `/api/v1/ai/ui/graphrag/query` | POST | GraphRAG answer projection with nodes, edges, logs, citations, confidence badge | `GraphRagPanel.tsx` |
| `/api/v1/ai/ui/explain/{prediction_id}` | GET | SHAP/LIME explanation projection with sorted features and plot-ready payloads | `ShapExplainability.tsx` |
| `/api/v1/ai/ui/recommendations` | POST | Flattened decision recommendations into dashboard action cards | Prescriptive action panel |
| `/api/v1/ai/ui/agent/chat` | POST | Non-streaming AI chat response envelope | Multi-agent chat panel |
| `/api/v1/ai/ui/agent/chat/stream` | POST | NDJSON chat event stream | Streaming multi-agent chat panel |
| `/api/v1/ai/ui/cors-check` | GET | CORS configuration verification | Frontend connectivity / CI smoke |
| `/api/v1/ai/ui/options` | OPTIONS | Deterministic preflight header response | Browser preflight diagnostics |
| `/api/v1/ai/ui/contracts` | GET | Machine-readable UI contract manifest | Swagger / type generation / integration audit |

#### Key finding

The repo clone already contains the UI adapter layer and working mount chain. The phase-critical verification target is therefore:

- **keep the router mounted**,
- **prove it is reachable**,
- **lock the fallback path**,
- **prevent schema drift**.

---

### Task 2: Dependency Isolation Audit

The UI router depends on adapter and schema packages. These must remain importable without forcing arbitrary contract edits.

#### Import dependency matrix

| Layer | File / Module | Required For | Status in Repo |
|---|---|---|---|
| UI router | `app.ai_service.integration.ui_router` | Frontend-facing route surface | Present |
| Chat adapter | `app.ai_service.integration.adapters.chat_event_adapter` | NDJSON event conversion | Present |
| Frontend adapters | `app.ai_service.integration.adapters.frontend_adapters` | UI payload flattening | Present |
| CORS helpers | `app.ai_service.integration.cors_headers` | Preflight and CORS diagnostics | Present |
| Formatters | `app.ai_service.integration.formatters.payload_formatters` | Recharts, SHAP, graph formatting | Present |
| Confidence formatter | `app.ai_service.integration.formatters.confidence_badge` | Badge / warning level / color mapping | Present |
| UI schemas | `app.ai_service.integration.schemas.ui_schemas` | Strict response model validation | Present |
| AI deps | `app.ai_service.dependencies` | GraphRAG / Predictive / XAI / Decision DI hooks | Present |
| Predictive router | `app.api.v1.predictive` | Frozen predictive contract + fallback | Present |

#### Isolation rule

If an engine dependency is temporarily unavailable, the UI adapter must:

- return a sanitized structured fallback or controlled `503`,
- never crash with a raw import traceback,
- never emit malformed JSON.

---

### Task 3: Import Audit for ML and Knowledge Modules

#### Audit table

| Dependency family | Expected module | Use area | Governance rule |
|---|---|---|---|
| SHAP / XAI | `app.predictive.xai_service` and `shap` | `/ui/explain/*` and Phase 7 XAI routes | UI adapter may degrade gracefully; do not rename explanation keys |
| GraphRAG | `app.graphrag.graph_rag_service` | `/ui/graphrag/query` | Preserve `answer`, `nodes`, `edges`, `citations`, `confidence` |
| Ontology / graph models | `app.models.ontology`, `app.models.graphrag` | typed graph payloads | Do not flatten away semantic ids needed by frontend |
| Predictive service | `app.predictive.prediction_service` | `/predictive/infer`, digital twin risk projection | Missing runtime must trigger fallback, not 500 |
| Decision engine | `app.decision.decision_service` | `/ui/recommendations` | Preserve action-card keys exactly |

#### Verified corrective improvement made in this session

A real fallback bug existed in `app/api/v1/predictive.py`:

- `TelemetryContractError` was imported inside a `try`
- the `except (TelemetryContractError, ValueError)` tuple could become undefined when predictive runtime imports failed
- this caused **`UnboundLocalError` instead of graceful fallback**

This has been corrected by defining a safe exception tuple before the runtime import and falling back cleanly when the predictive runtime is unavailable.

---

### Task 4: Router Registration Protocol

#### Canonical FastAPI registration pattern

```python
from fastapi import APIRouter
from app.ai_service.integration.ui_router import ui_router

router = APIRouter()
router.include_router(ui_router, prefix="/ui", tags=["UI-Adapter"])
```

#### Actual working repo pattern

This repo already uses a layered mount pattern, which is correct and should be preserved.

**`app/ai_service/main_router.py`**

```python
ai_router = APIRouter(
    prefix="/ai",
    tags=["AI Platform"],
)

from app.ai_service.integration.ui_router import ui_router
ai_router.include_router(ui_router)
```

**`app/api/v1/router.py`**

```python
from app.ai_service.main_router import ai_router
api_router.include_router(ai_router)
```

**`app/main.py`**

```python
app.include_router(api_router, prefix=settings.api_v1_prefix)
```

#### Resulting effective path

`/api/v1` + `/ai` + `/ui/...` = `/api/v1/ai/ui/...`

#### Hard rule

Do **not** duplicate-mount `ui_router` in multiple places. One clean mount chain only.

---

### Task 5: Endpoint Verification Protocol

Run the contract suite exactly:

**`pytest tests/test_phase11_ui_router_contract.py -q`**

#### Expected result in this audited workspace

**`24 passed`**

> Note: some older planning notes mention 23 tests. This repo snapshot currently contains 24 UI-router contract tests because OpenAPI path mounting is explicitly asserted.

#### Reachability proof points

- `/api/v1/ai/ui/digital-twin/{asset_id}` reachable
- `/api/v1/ai/ui/graphrag/query` reachable
- `/api/v1/ai/ui/explain/{prediction_id}` reachable
- `/api/v1/ai/ui/recommendations` reachable
- `/api/v1/ai/ui/agent/chat` reachable
- `/api/v1/ai/ui/agent/chat/stream` reachable
- `/api/v1/ai/ui/cors-check` reachable
- `/api/v1/ai/ui/options` reachable
- `/api/v1/ai/ui/contracts` reachable

---

### Task 6: Contract Testing Strategy

For every UI endpoint, validate all four layers:

1. **HTTP reachability** — no `404 Not Found`
2. **Envelope integrity** — `success`, `data`, `error`, `requestId`, `generatedAt`
3. **Panel payload shape** — exact expected frontend keys
4. **Header integrity** — `x-ai-module`, `x-request-id`, CORS headers where applicable

#### Mandatory response-shape audit rules

- arrays must remain arrays, never `null`
- typed plot blocks must remain present when expected
- fields consumed by Member 4 must remain exact-case exact-name
- any schema drift must fail in CI before frontend integration

---

### Task 7: Pass Criteria for the UI Contract Suite

You are done only when the suite transitions from structural failure to full pass.

#### Required green path

- no `404` failures
- no missing OpenAPI paths
- no envelope-key drift
- no renamed frontend keys
- no NDJSON stream contract regression

#### Verified workspace result

**`24 passed, 0 failed`** for `tests/test_phase11_ui_router_contract.py`

#### Additional regression run performed

**`113 passed, 0 failed`** across:

- `tests/test_phase10_ai_service.py`
- `tests/test_phase11_frontend_adapters.py`
- `tests/test_phase11_payload_formatters.py`
- `tests/test_phase11_chat_event_adapter.py`
- `tests/test_phase11_cors_headers.py`
- `tests/test_phase11_ui_router_contract.py`

---

### Task 8: Core Predictive Contract Validation

The predictive engine is a **frozen core contract**. Do not arbitrarily rename fields.

#### Route

`POST /api/v1/predictive/infer`

#### Core fields that must remain available in the response payload

| Functional meaning | Existing wire key |
|---|---|
| Remaining Useful Life (RUL) | `rul` |
| Failure Probability | `failure_probability` |
| Anomaly Flags | `anomaly_flags` |
| Generated At | `generated_at` |
| Inference Latency | `inference_latency_ms` |

#### Mock structural payload example

```json
{
  "success": true,
  "data": {
    "asset_id": "P-101A",
    "component_id": "bearing",
    "risk_score": 0.7452,
    "failure_probability": 0.7452,
    "rul": {
      "value_days": 15.29,
      "lower_bound_days": 10.19,
      "upper_bound_days": 20.38,
      "confidence_level": 0.9,
      "model_name": "xgboost_rul_v1",
      "model_version": "1.0.0"
    },
    "failure_probability_detail": {
      "probability": 0.7452,
      "predicted_window": {
        "earliest": "2026-07-17T09:03:51.125855+00:00",
        "latest": "2026-07-17T09:03:51.125855+00:00",
        "most_likely": "2026-07-17T09:03:51.125855+00:00"
      },
      "failure_mode_id": "failuremode-bearing-overheat",
      "failure_mode_label": "Bearing Overheat",
      "model_name": "xgboost_failure_classifier_v1"
    },
    "anomaly_flags": [
      {
        "sensor_id": "vib-sensor-1",
        "metric": "vibration_rms",
        "anomaly_score": -0.12,
        "is_anomalous": true,
        "severity": "HIGH",
        "detected_at": "2026-07-17T09:03:51.125855+00:00"
      }
    ],
    "explanation_id": "20475413-028f-4ecc-822a-7457546b4e48",
    "inference_latency_ms": 18.4,
    "generated_at": "2026-07-17T09:03:51.125855+00:00",
    "fallback_used": true
  },
  "error": null,
  "request_id": "9bf1f7d0-6009-4671-b4ea-7e9372167d63",
  "generated_at": "2026-07-17T09:03:51.125906+00:00",
  "risk_score": 0.7452
}
```

#### Governance warning

This payload may be richer than the frontend projection, but **you must not mutate it to satisfy UI preferences**. UI-friendly key remapping belongs in adapter functions only.

---

### Task 9: Graceful Fallback Strategy & Verification

This is a non-negotiable stability requirement.

#### Required behavior

If trained model artifacts or predictive runtime dependencies are unavailable:

- do **not** throw raw `500 Internal Server Error`
- do **not** surface unhandled import tracebacks
- do **not** return malformed payloads
- do return a structured fallback payload with `fallback_used: true`

#### Corrective action applied

`app/api/v1/predictive.py` was hardened so runtime import failures now degrade gracefully.

#### Verification procedure

1. Submit a feature-based request to `/api/v1/predictive/infer`
2. Ensure predictive runtime is absent or import fails
3. Confirm response status is `200`
4. Confirm envelope is valid
5. Confirm response includes:
   - `rul`
   - `failure_probability`
   - `anomaly_flags`
   - `generated_at`
   - `inference_latency_ms`
   - `fallback_used: true`

#### Verified result in this workspace

Feature-only predictive inference returned **HTTP 200** with a structured fallback payload after the fix.

---

### Task 10: Simulation Validation

Perform smoke validation using app-level routes, not isolated function calls only.

#### Commands

**`pytest tests/test_phase11_ui_router_contract.py -q`**

**`pytest tests/test_phase10_ai_service.py tests/test_phase11_frontend_adapters.py tests/test_phase11_payload_formatters.py tests/test_phase11_chat_event_adapter.py tests/test_phase11_cors_headers.py tests/test_phase11_ui_router_contract.py -q`**

#### Simulation outputs to confirm

- UI routes appear in `openapi.json`
- `/api/v1/ai/ui/contracts` lists all nine endpoints
- digital twin route returns a non-empty history array
- GraphRAG response includes `answer`, `nodes`, `edges`, `citations`, `confidence`
- explain response includes sorted `features`, `waterfall`, `forcePlot`
- recommendations response remains card-friendly
- stream route emits NDJSON and starts with `heartbeat`

---

### Task 11: Regression Lock

Do not stop at the main UI contract suite.

#### Regression surfaces to protect

- Phase 10 AI service routes
- Phase 11 frontend adapters
- Phase 11 payload formatters
- Phase 11 chat event adapter
- Phase 11 CORS helpers

#### Green regression baseline from this execution

**`113 passed`**

This means the router wiring remained stable while preserving adapter, streaming, and formatting behaviors.

---

### Task 12: Swagger / OpenAPI Validation

Swagger must expose the new mounted UI routes automatically.

#### Validation steps

1. Start the app
2. Open **`/docs`**
3. Confirm `/api/v1/ai/ui/*` operations appear
4. Open **`/openapi.json`**
5. Confirm these exact paths exist:

- `/api/v1/ai/ui/digital-twin/{asset_id}`
- `/api/v1/ai/ui/graphrag/query`
- `/api/v1/ai/ui/explain/{prediction_id}`
- `/api/v1/ai/ui/recommendations`
- `/api/v1/ai/ui/agent/chat`
- `/api/v1/ai/ui/agent/chat/stream`
- `/api/v1/ai/ui/cors-check`
- `/api/v1/ai/ui/options`
- `/api/v1/ai/ui/contracts`

#### Verified workspace result

OpenAPI contained all **9** UI adapter paths.

---

## 4. Comprehensive Phase 2 Deliverables Checklist

- [x] `ui_router.py` location identified and audited
- [x] mount chain validated through `app/ai_service/main_router.py` and `app/api/v1/router.py`
- [x] UI endpoint inventory documented
- [x] contract suite command documented
- [x] UI router contract suite executed green
- [x] regression suite executed green
- [x] predictive fallback bug identified and fixed
- [x] predictive fallback snapshot generated
- [x] OpenAPI UI path snapshot generated
- [x] contract manifest snapshot generated
- [x] engineering execution guide generated
- [x] zip-ready deliverables folder assembled

---

## 5. Binary Exit Criteria (Gatekeeper Rules)

Member 3 may declare Phase 2 complete only if **all** items are true:

- [x] `ui_router.py` is verified as imported, mounted, and fully reachable inside the app routing framework.
- [x] `test_phase11_ui_router_contract.py` outputs a 100% green pass suite status.
- [x] `/api/v1/predictive/infer` structural payload properties remain entirely unchanged.
- [x] Model-omission or runtime-unavailability testing proves the existence of a crash-free fallback mechanism.
- [x] Zero routing regressions are present across the validated Phase 10/11 integration surfaces.
- [x] Swagger / OpenAPI surfaces the `/api/v1/ai/ui/*` schema set.

---

## Worked Files in This Execution

### Modified source files

- `app/api/v1/predictive.py`
- `tests/test_phase6_predictive.py`

### Verification artifacts

- `deliverables/phase2/phase2_ui_router_contract.log`
- `deliverables/phase2/phase2_regression.log`
- `deliverables/phase2/phase2_predictive_infer_snapshot.json`
- `deliverables/phase2/phase2_ui_contract_manifest_snapshot.json`
- `deliverables/phase2/phase2_openapi_ui_paths.json`
- `deliverables/phase2/phase2_smoke_summary.json`
- `deliverables/phase2/PHASE2_ENGINEERING_EXECUTION_GUIDE_LATHIKA.md`

---

## Final Senior-Architect Note

The repo already had the frontend adapter chain mounted correctly for `/api/v1/ai/ui/*`. The critical engineering action in this execution was **not** re-inventing router wiring; it was verifying the mount chain, locking contract behavior, and hardening fallback so missing predictive runtime dependencies do not explode into a raw server error.

That is the correct Phase 2 outcome: **reachable UI adapter + preserved contracts + crash-free degradation path**.
