# Phase 4 — Engineering Execution Guide: Frontend Integration & End-to-End Validation

**Role:** Member 3 (Lathika) — AI/ML Knowledge Engineer (Collaborating with Member 4 — Frontend)

**Phase:** Phase 4 — Support Frontend Integration & End-to-End Validation

**Estimated Duration:** 1–2 Hours (Synchronous Session)

**Priority:** ⭐⭐⭐⭐⭐⭐⭐⭐ [CRITICAL CAPABILITY HANDOFF]

**Date:** 2026-07-18

**Repository:** `https://github.com/lathika-mohan/brain_intelligence-main`

---

## Table of Contents

1. [Document Header & Metadata](#1-document-header--metadata)
2. [The Zero-Transformation Contract Architecture](#2-the-zero-transformation-contract-architecture)
3. [Step-by-Step Task Breakdowns (With Pair-Testing Protocols)](#3-step-by-step-task-breakdowns)
4. [Comprehensive Phase 4 Deliverables Checklist](#4-comprehensive-phase-4-deliverables-checklist)
5. [Binary Exit Criteria (The Ultimate Sign-off Gatekeeper)](#5-binary-exit-criteria)

---

## 1. Document Header & Metadata

| Field | Value |
|---|---|
| **Role** | Member 3 (Lathika) — AI/ML Knowledge Engineer |
| **Collaborator** | Member 4 — Frontend Engineer |
| **Phase** | Phase 4 — Support Frontend Integration & End-to-End Validation |
| **Estimated Duration** | 1–2 Hours (Synchronous Pair-Integration Session) |
| **Priority** | ⭐⭐⭐⭐⭐⭐⭐⭐ CRITICAL CAPABILITY HANDOFF |
| **Pre-Condition** | Phase 3 Gateway Transparent Relay verified, Phase 11 UI contracts frozen |
| **Post-Condition** | Member 4 signs off that zero client-side payload translation is present |
| **Backend Adapter** | `app/ai_service/integration/ui_router.py` |
| **Schema Source-of-Truth** | `app/ai_service/integration/schemas/ui_schemas.py` |
| **Formatter Suite** | `app/ai_service/integration/formatters/payload_formatters.py` |
| **Frontend Adapter** | `app/ai_service/integration/adapters/frontend_adapters.py` |
| **CORS Module** | `app/ai_service/integration/cors_headers.py` |
| **Contract Spec** | `docs/AI_PAYLOAD_SPEC.md` |
| **Existing Test Suite** | `tests/test_phase11_ui_router_contract.py` |

### Integration Risk Diagnosis

Claude's live evaluation emphasizes that a pristine API contract means nothing if the browser crashes during data rendering. This phase systematically eradicates the following integration defects:

1. **The Client-Side Transformation Trap:** Preventing Member 4 from writing complex map-and-reshape UI formatting layers. The backend adapter (`ui_router.py`) must deliver data directly ready for React component consumption.

2. **Asynchronous Finger-Pointing:** Eradicating isolated, ticket-based cross-talk by establishing a synchronized, live "Pair-Integration & Bug Bash" architecture.

3. **Visual Component Breakdowns:** Mitigating missing array schemas, malformed timestamps, or nested null exceptions within complex UI modules like XAI/SHAP panels and GraphRAG citation lists.

---

## 2. The Zero-Transformation Contract Architecture

### 2.1 Structural Hierarchy of Direct Consumption

The core principle governing Phase 4 is the **Zero-Transformation Rule**: the JSON payload emitted by `ui_router.py` must bind directly into React component state without any intermediate mapping, reshaping, renaming, or sorting step on the client.

#### Correct Flow (Phase 4 Target)

```
Backend Engine Output
        │
        ▼
Frontend Adapters (frontend_adapters.py)
        │  adapt_digital_twin_payload()
        │  adapt_graphrag_payload()
        │  adapt_explainability_payload()
        │  adapt_recommendations_to_actions()
        │  to_ui_api_envelope()
        ▼
Pydantic Schema Validation (ui_schemas.py)
        │  UIDigitalTwinPayload.model_validate()
        │  UIGraphRAGPayload.model_validate()
        │  UIShapExplanation.model_validate()
        ▼
JSONResponse (Section 11 UIAPIResponse envelope)
        │
        ▼  HTTP/JSON over wire
        │
React Component State (setState / useState)
        │  data.telemetry.speed → "Rotational Speed" card
        │  data.nodes[].x/y → SVG renderer
        │  data.features[].shapValue → SHAP bar chart
        ▼
Screen Render (Zero Transformation)
```

#### Incorrect Flow (Anti-Pattern to Eradicate)

```
Backend Engine Output
        │
        ▼
Raw Backend JSON (snake_case, nested nulls, unsorted arrays)
        │
        ▼  HTTP/JSON over wire
        │
Frontend Data Mapper/Parser ❌
        │  const camelCased = snakeToCamel(payload);  ← FORBIDDEN
        │  const sorted = features.sort(...);          ← FORBIDDEN
        │  const safe = payload ?? [];                 ← FORBIDDEN
        │  const mapped = nodes.map(reshapeNode);      ← FORBIDDEN
        ▼
React Component State (Mutated Shape)
        │
        ▼
Screen Render (with hidden transformation debt)
```

### 2.2 Side-by-Side Example: Raw Backend vs. UI-Ready Payload

#### Raw Backend `InferenceResponse` (Phase 6 model)

```json
{
  "asset_id": "P-101A",
  "component_id": null,
  "rul": {
    "value_days": 5.2,
    "lower_bound_days": 3.5,
    "upper_bound_days": 7.8
  },
  "failure_probability": {
    "probability": 0.64,
    "predicted_window": {
      "earliest": "2026-07-08T07:15:00Z",
      "most_likely": "2026-07-12T07:15:00Z",
      "latest": "2026-07-15T07:15:00Z"
    },
    "failure_mode_id": "fm-bearing-wear",
    "failure_mode_label": "Bearing wear"
  },
  "anomaly_flags": [
    {
      "sensor_id": "sns-vib-1",
      "metric": "vibration_rms",
      "anomaly_score": -0.42,
      "is_anomalous": true,
      "severity": "HIGH",
      "detected_at": "2026-07-07T07:15:00Z"
    }
  ],
  "anomalous_sensors": ["sns-vib-1"],
  "explanation_id": "pred-p101a-001",
  "inference_latency_ms": 9.8,
  "generated_at": "2026-07-07T07:15:00Z"
}
```

#### UI-Ready `UIPrediction` (After `adapt_inference_to_prediction`)

```json
{
  "id": "pred-p101a-001",
  "assetId": "P-101A",
  "remainingUsefulLifeDays": 5.2,
  "failureProbability": 0.64,
  "inferredFaultMechanism": "Bearing wear"
}
```

**Zero transformation required.** Member 4 binds `data.id`, `data.assetId`, `data.remainingUsefulLifeDays`, `data.failureProbability`, `data.inferredFaultMechanism` directly into the `prediction.service.ts` hook.

#### Full Digital Twin UI Payload (After `adapt_digital_twin_payload` + `to_ui_api_envelope`)

```json
{
  "success": true,
  "data": {
    "asset": {
      "id": "P-101A",
      "name": "P-101A",
      "type": "PUMP",
      "status": "OPERATIONAL",
      "parentId": null
    },
    "telemetry": {
      "speed": 1480.0,
      "vibration": 5.2,
      "pressure": 6.4,
      "temperature": 82.0,
      "flowRate": 240.0,
      "load": 312.0,
      "riskScore": 64.0,
      "status": "warning"
    },
    "history": [
      {
        "timestamp": "2026-07-07T07:00:00Z",
        "speed": 1480.0,
        "vibration": 1.2,
        "pressure": 6.4,
        "temperature": 80.0,
        "flowRate": 240.0,
        "load": 308.0,
        "riskScore": 64.0,
        "status": "ok"
      }
    ],
    "activeAnomaly": "bearing-wear",
    "generated_at": "2026-07-07T07:15:00.000000"
  },
  "error": null,
  "requestId": "req-dt-1",
  "generatedAt": "2026-07-07T07:15:00.123456"
}
```

**Binding map (zero transformation):**

| JSON Path | React Binding | Component |
|---|---|---|
| `data.telemetry.speed` | `telemetry.speed` | Rotational Speed card |
| `data.telemetry.vibration` | `telemetry.vibration` | Housing Vibration card |
| `data.telemetry.riskScore` | `telemetry.riskScore` | AI Risk Index pill |
| `data.telemetry.status` | `telemetry.status` | Status pill (ok/warning/critical/offline) |
| `data.history[]` | `history` | `renderMiniChart()` — reads `reading[dataKey]` |
| `data.activeAnomaly` | `activeAnomaly` | Branches SVG schematic |
| `data.asset.id` | `asset.id` | Branches SVG schematic variant |

---

## 3. Step-by-Step Task Breakdowns

### Tasks 1 & 2: Integration Session Logistics & Panel Inventory

#### Task 1: Synchronous Workshop Setup

**Protocol:**

1. **Shared Screen Session:** Both Member 3 and Member 4 share screens simultaneously — Member 3 on the FastAPI server logs, Member 4 on the browser DevTools Console + Network tab.

2. **Shared Terminal:** Member 3 runs `uvicorn app.main:app --reload --port 8002` in one terminal, and monitors with `tail -f` on the AI service logs. Member 4 runs `npm run dev` on port 3000.

3. **CORS Baseline:** Before any endpoint is tested, verify the preflight:
   ```bash
   curl -X OPTIONS http://localhost:8002/api/v1/ai/ui/options \
     -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type,x-request-id" \
     -v
   ```
   Expected: HTTP 204, `Access-Control-Allow-Origin: http://localhost:3000`, `Vary: Origin`.

4. **Health Gate:** Verify the AI health endpoint returns `status: "ready"` or `status: "degraded"` (degraded is acceptable; full crash is not):
   ```bash
   curl http://localhost:8002/api/v1/ai/health
   ```

#### Task 2: AI-to-Frontend Dependency Mapping Table

This table tracks every AI-backed UI panel, the subsystem it depends on, the target widget, and the exact data delivery format.

| # | Frontend Component / Page | AI Dependency Sub-System | Target UI Widget | Data Delivery Format (Pydantic Schema) | UI Endpoint |
|---|---|---|---|---|---|
| 1 | `DigitalTwinView.tsx` | Predictive Engine (Phase 6) | Telemetry cards (speed/vibration/pressure/temp/flow/load/risk), SVG schematic, mini charts | `UIDigitalTwinPayload` → `UIAPIResponse[UIDigitalTwinPayload]` | `GET /api/v1/ai/ui/digital-twin/{asset_id}` |
| 2 | `GraphRagPanel.tsx` | GraphRAG Engine (Phase 5) | SVG graph renderer, log timeline strip, answer panel, source-chip tray | `UIGraphRAGPayload` → `UIAPIResponse[UIGraphRAGPayload]` | `POST /api/v1/ai/ui/graphrag/query` |
| 3 | `ShapExplainability.tsx` | XAI Engine (Phase 7) | SHAP bar chart, waterfall chart, force plot, root cause header, confidence matrix | `UIShapExplanation` → `UIAPIResponse[UIShapExplanation]` | `GET /api/v1/ai/ui/explain/{prediction_id}` |
| 4 | Prescriptive-action card panel | Decision Engine (Phase 8) | Action cards (rank, priority, SOP linkage, cost avoidance) | `List[UIRecommendationAction]` → `UIAPIResponse[List]` | `POST /api/v1/ai/ui/recommendations` |
| 5 | Multi-agent chat panel | Orchestration Engine (Phase 9) | Chat message bubble, timeline strip, tool execution log, citation tray, sub-graph side panel | `UIChat` + `AgentStreamEvent[]` (NDJSON) | `POST /api/v1/ai/ui/agent/chat` and `/stream` |
| 6 | `prediction.service.ts` | Predictive Engine (Phase 6) | Prediction list, RUL badge, failure probability meter | `UIPrediction` → embedded in `UIDigitalTwinPayload` | Same as #1 |
| 7 | `chat.service.ts` | Agent Runtime (Phase 10) | Message list, sender badge, optimistic dedup | `UIChat` → `UIAPIResponse[UIChat]` | `POST /api/v1/ai/ui/agent/chat` |
| 8 | CORS preflight probe | CORS module (Phase 11) | CI verification, browser console diagnostics | `CORSStatus` dict | `GET /api/v1/ai/ui/cors-check` |
| 9 | Contract manifest | N/A | TypeScript type generation | `ContractManifest` dict | `GET /api/v1/ai/ui/contracts` |

---

### Tasks 3 & 4: UI Router Handoff & Response Shape Audit

#### Task 3: UI Router Handoff Verification

**Step-by-step protocol:**

1. Member 3 starts the FastAPI server:
   ```bash
   cd /home/user/brain_intelligence-main
   uvicorn app.main:app --reload --port 8002
   ```

2. Member 3 calls the contract manifest to confirm all 9 endpoints are registered:
   ```bash
   curl http://localhost:8002/api/v1/ai/ui/contracts | python -m json.tool
   ```
   **Expected:** `data.phase == "11-frontend-integration-support"`, `data.version == "0.11.0"`, `len(data.endpoints) == 9`.

3. Member 3 runs the existing Phase 11 test suite:
   ```bash
   python -m pytest tests/test_phase11_ui_router_contract.py -v
   ```
   **Expected:** All tests pass (9 test classes, ~25 test methods).

#### Task 4: UI Endpoint Verification Matrix

This matrix tracks the 5 core modules and the explicit field-level checks for each endpoint.

| Module | Endpoint | Nested Arrays Check | Enum Maps Check | Timestamp ISO Check | Null Allocation Check | Float Array Stability | Key Casing (camelCase) |
|---|---|---|---|---|---|---|---|
| **Predictive** (DigitalTwinView) | `GET /api/v1/ai/ui/digital-twin/{asset_id}` | `data.history[]` must be `list`, not `null`; each frame must have all 8 telemetry keys | `data.telemetry.status` ∈ {ok, warning, critical, offline}; `data.asset.status` ∈ {OPERATIONAL, DEGRADED, CRITICAL, OFFLINE} | `data.history[].timestamp` must be ISO-8601 (`2026-07-07T07:00:00Z`); `data.generated_at` must parse with `new Date()` | `data.asset.parentId` may be `null` — safe; `data.activeAnomaly` may be `null` — safe; `data.history` must never be `null` (empty `[]` is ok) | `data.telemetry.riskScore` must be `float` in [0, 100]; NaN/Inf guarded by `_safe_metric()` | All keys camelCase: `flowRate`, `riskScore`, `parentId`, `activeAnomaly` |
| **GraphRAG** (GraphRagPanel) | `POST /api/v1/ai/ui/graphrag/query` | `data.nodes[]`, `data.edges[]`, `data.logs[]`, `data.citations[]`, `data.highlightedNodes[]`, `data.highlightedEdges[]` — all must be `list`, never `null` | `data.nodes[].type` ∈ {asset, component, anomaly, procedure, record}; `data.badge` ∈ {very_low, low, medium, high, very_high} | `data.generatedAt` must be ISO-8601 | `data.warningLevel` may be `null`; `data.color` may be `null` — safe; all arrays must be `[]` not `null` | `data.nodes[].x`, `data.nodes[].y` must be `float` — deterministic layout; `data.confidence` ∈ [0.0, 1.0] | `data.highlightedNodes`, `data.highlightedEdges`, `data.vectorHits`, `data.generatedAt` |
| **XAI** (ShapExplainability) | `GET /api/v1/ai/ui/explain/{prediction_id}` | `data.features[]`, `data.confidenceMatrix[]` — must be `list`, never `null` | `data.method` ∈ {SHAP, LIME, INTEGRATED_GRADIENTS, PERMUTATION}; `data.scope` ∈ {LOCAL, GLOBAL} | `data.generatedAt` must be ISO-8601 | `data.rootCause` may be `{}` but never `null`; `data.waterfall` / `data.forcePlot` may be `null` — safe | `data.features[].shapValue` must be finite `float` (no NaN/Inf); `data.baseValue` and `data.predictionValue` must be finite | `data.predictionId`, `data.assetId`, `data.shapValue`, `data.generatedAt`, `data.forcePlot` |
| **Knowledge** (GraphRAG citations) | Same as GraphRAG above | `data.citations[]` — each must have `citation_id`, `claim_span`, `source_document`, `source_type`, `confidence_score` | `source_type` ∈ {SOP, INCIDENT, MANUAL, REPORT} | Timestamps within citations must be ISO-8601 | `page_number` may be `null`; `url` may be `null` | `confidence_score` ∈ [0.0, 1.0] | `citationId`, `claimSpan`, `sourceDocument`, `sourceType`, `confidenceScore`, `pageNumber` |
| **Decision** (Recommendations) | `POST /api/v1/ai/ui/recommendations` | `data[]` — must be `list`, never `null` | `data[].priority` ∈ {LOW, MEDIUM, HIGH, CRITICAL}; `data[].severityTier` ∈ {IMMINENT, SCHEDULED, MONITOR} | `data[].recommendedCompletionBy` must be ISO-8601 | `data[].sop` may be `null` — safe; `data[].sop.revision` may be `null` | `data[].riskScoreIfIgnored` ∈ [0.0, 1.0]; `data[].estimatedCostAvoidanceUsd` ≥ 0.0 | `actionId`, `actionType`, `severityTier`, `riskScoreIfIgnored`, `estimatedCostAvoidanceUsd`, `recommendedCompletionBy` |

**Pair-Testing Protocol for Each Check:**

1. Member 3 fires the endpoint with `curl` and pipes to `python -m json.tool`.
2. Member 4 opens browser DevTools → Network tab → selects the request → Preview tab.
3. Both verify the same field simultaneously: Member 3 checks the JSON, Member 4 checks that `typeof data.telemetry.riskScore === 'number'` in the Console.
4. If a discrepancy is found (e.g., `null` where array is expected), Member 3 fixes the adapter immediately and redeploys — Member 4 refreshes without clearing cache.

---

### Task 5: Enforcement of the Zero Client Transformation Rule

This is the **single most critical task** in Phase 4. The goal is to audit Member 4's data ingestion logic and guarantee that zero client-side field renamings, reshaping, or data munging exists.

#### Audit Protocol

1. **Code Scan:** Member 3 reviews every file in `src/services/` and `src/components/` for the following anti-patterns:

   **Anti-Pattern 1 — snake_case → camelCase conversion:**
   ```typescript
   // FORBIDDEN ❌
   const data = response.data.map(item => ({
     assetId: item.asset_id,        // ← Adapter already outputs "assetId"
     failureProb: item.failure_probability,  // ← Adapter already outputs "failureProbability"
   }));
   ```

   **Correct binding (zero transformation):**
   ```typescript
   // CORRECT ✅
   const data = response.data;  // Already camelCase from ui_router.py
   ```

2. **Anti-Pattern 2 — Client-side sorting of SHAP features:**
   ```typescript
   // FORBIDDEN ❌
   const sorted = features.sort((a, b) => Math.abs(b.shapValue) - Math.abs(a.shapValue));
   // The adapter already returns features pre-sorted by |shapValue| desc
   ```

3. **Anti-Pattern 3 — Null coalescing on arrays that should never be null:**
   ```typescript
   // FORBIDDEN ❌
   const nodes = data.nodes ?? [];  // If data.nodes is null, the adapter is broken
   ```

   **Correct approach:** If `data.nodes` is `null`, the adapter is broken and Member 3 fixes it. Member 4 should never need `?? []`.

4. **Anti-Pattern 4 — Date parsing / reformatting:**
   ```typescript
   // FORBIDDEN ❌
   const ts = new Date(item.timestamp).toISOString();
   // The adapter already outputs ISO-8601 strings
   ```

5. **Anti-Pattern 5 — Enum value mapping on the client:**
   ```typescript
   // FORBIDDEN ❌
   const statusMap = { OPERATIONAL: 'ok', DEGRADED: 'warning' };
   const status = statusMap[item.status];
   // The adapter already maps to DigitalTwinView's vocabulary (ok/warning/critical/offline)
   ```

#### Interception and Replacement

When a client-side transformation is found:

| Anti-Pattern Found | Member 3 Action | Member 4 Action |
|---|---|---|
| snake_case → camelCase conversion | Verify the adapter outputs the correct camelCase key; fix if not | Remove the `.map()` call; bind directly |
| Client-side SHAP sort | Verify `adapt_explainability_payload()` sorts desc by `\|shapValue\|` | Remove the `.sort()` call |
| `?? []` null guard on arrays | Verify the adapter always returns `[]` (never `null`) for array fields | Remove the `?? []` guard |
| Date reformatting | Verify the adapter outputs ISO-8601 via `.isoformat()` | Remove the `new Date().toISOString()` call |
| Client-side enum mapping | Verify the adapter maps to the component's exact vocabulary | Remove the mapping object |

#### Verification Command

After all anti-patterns are removed, Member 4 runs:

```bash
# From the Next.js project root
grep -rn "\.map(" src/services/ | grep -v "node_modules"
grep -rn "\.sort(" src/components/ShapExplainability.tsx
grep -rn "?? \[\]" src/components/
grep -rn "new Date.*toISOString" src/services/
```

All results must be **zero** for the sign-off to proceed.

---

### Tasks 6–9: Deep-Dive Component Workflows

#### Task 6: Predictive Module — DigitalTwinView.tsx

**Verification Scenario 1: Normal Operation**

```bash
curl -X GET "http://localhost:8002/api/v1/ai/ui/digital-twin/P-101A?horizon=24&include_inference=true" \
  -H "x-request-id: req-dt-e2e-001" | python -m json.tool
```

**Expected browser behavior:**
- `DigitalTwinView.tsx` renders the SVG schematic for pump-03 (asset.id branches the SVG variant)
- All 8 telemetry cards show numeric values (no "undefined" or "NaN")
- The AI Risk Index pill shows `64.0` with "warning" background colour
- Mini charts populate from `history[]` with ≥ 1 data point
- `activeAnomaly === "bearing-wear"` triggers the bearing-wear SVG branch
- Browser console: zero errors

**Verification Scenario 2: Long-Tail Loading State**

```bash
# Simulate slow predictive inference by introducing latency
curl -X GET "http://localhost:8002/api/v1/ai/ui/digital-twin/P-101A?horizon=168&include_inference=true" \
  -H "x-request-id: req-dt-e2e-002"
```

**Expected browser behavior:**
- The component shows a loading spinner while the request is in-flight
- On response (even if delayed), the telemetry data populates immediately
- No `TypeError: Cannot read properties of null (reading 'speed')` during the loading window
- Member 4 confirms: `if (loading) return <Spinner />` is in place before accessing `data.telemetry.speed`

**Verification Scenario 3: Degraded Mode (prediction engine unavailable)**

When the prediction engine returns `None` (degraded), the adapter falls back to `UITelemetry()` defaults (all zeros, `status: "ok"`).

**Expected browser behavior:**
- Telemetry cards show `0.0` values (not NaN, not undefined, not "—")
- Risk score shows `0.0`
- Status pill shows "ok" (green)
- No browser console errors
- The response envelope has `success: true` (the degraded telemetry is still valid data)

**Debugging Trace — What NOT to See:**

```
❌ TypeError: Cannot read properties of null (reading 'speed')
    at DigitalTwinView (DigitalTwinView.tsx:47:35)
```

This means `data.telemetry` was `null`. The adapter guarantees `telemetry` is always a populated `UITelemetry` object. If this error appears, the adapter is broken.

---

#### Task 7: GraphRAG Module — GraphRagPanel.tsx

**Verification Scenario 1: Normal Query**

```bash
curl -X POST "http://localhost:8002/api/v1/ai/ui/graphrag/query" \
  -H "Content-Type: application/json" \
  -H "x-request-id: req-rag-e2e-001" \
  -d '{"query": "Why is P-101A vibrating?", "asset_id": "P-101A", "top_k": 8}'
```

**Expected browser behavior:**
- GraphRagPanel renders `nodes[]` as SVG circles/ellipses at their `x`/`y` coordinates
- Edge arrows drawn between `source` → `target`
- Highlighted nodes/edges have bold borders / yellow colour
- Log timeline strip animates through `data.logs[]` entries
- Answer text renders in the answer panel without truncation
- Source-chip tray shows citation cards with `sourceDocument` and `confidenceScore`
- `data.badge === "high"`, `data.warningLevel === "industrial-status-ok"`

**Verification Scenario 2: Citation List Rendering (No Truncation)**

Each citation must render its full `claim_span` text. The adapter outputs citations as:

```json
{
  "citations": [
    {
      "citation_id": "cit-1",
      "claim_span": "vibration 5.2 mm/s exceeds threshold for bearing housing monitoring per SOP-MECH-042 Section 3.2.1",
      "source_document": "sop-p101a.pdf",
      "source_type": "SOP",
      "source_node_id": "sop:SOP-MECH-042",
      "confidence_score": 0.91
    }
  ]
}
```

**Key check:** `claim_span` must render in full. If the UI truncates at 50 chars, the citation is lost. Member 4 must use CSS `text-overflow: ellipsis` or a scrollable container — **never** `claimSpan.substring(0, 50)`.

**Verification Scenario 3: Empty Graph Result**

```bash
curl -X POST "http://localhost:8002/api/v1/ai/ui/graphrag/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "xyznonexistent", "asset_id": "FAKE-999"}'
```

**Expected browser behavior:**
- `data.nodes === []`, `data.edges === []` — empty graph, not `null`
- `data.answer === ""` — empty answer, not `null`
- `data.logs` still contains the "Vector search initiated" entry
- The panel shows "No results found" gracefully
- No `TypeError: data.nodes.map is not a function`

**Debugging Trace — What NOT to See:**

```
❌ TypeError: data.nodes.map is not a function
    at GraphRagPanel (GraphRagPanel.tsx:82:18)
```

This means `data.nodes` was `null` or `undefined` instead of `[]`. The adapter guarantees all arrays default to `[]`.

---

#### Task 8: XAI Module — ShapExplainability.tsx

**Verification Scenario 1: SHAP Feature Rendering**

```bash
curl -X GET "http://localhost:8002/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=SHAP" \
  -H "x-request-id: req-xai-e2e-001"
```

**Expected browser behavior:**
- Feature list renders top-to-bottom in descending `|shapValue|` order
- First feature is `vibration_rms` (highest absolute contribution)
- Each feature row shows: `name`, `value` (with unit like "9.5mm/s"), `shapValue` (signed float), `desc` (tooltip)
- Waterfall chart renders floating bars with `start`/`end`/`delta` keys
- Force plot renders positive/negative stacks with `baseValue` and `predictionValue` anchors
- Root cause header shows `headline` and `narrative`

**Verification Scenario 2: Stable Float Arrays for Chart Libraries**

SHAP visualization libraries (Recharts, d3) crash on `NaN` and `Infinity`. The adapter guards with:

```python
def _safe_metric(reading_map, key, default=0.0):
    f = float(val)
    if math.isnan(f) or math.isinf(f):
        return default
    return f
```

**Key check:** Every `shapValue` in `data.features[]` must be a finite float. Member 4 verifies in the browser console:

```javascript
data.features.every(f => Number.isFinite(f.shapValue))  // must be true
```

**Verification Scenario 3: LIME Method**

```bash
curl -X GET "http://localhost:8002/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=LIME"
```

**Expected:** `data.method === "LIME"`, same structural shape, features still sorted by `|shapValue|` desc.

**Debugging Trace — What NOT to See:**

```
❌ Error: <BarChart> attribute "data[0].shapValue": NaN is not a valid number
    at BarChart (recharts/es6/charts/BarChart.js:45:12)
```

This means a NaN leaked through the adapter. Member 3 must add a guard in `_safe_metric()` or `adapt_explainability_payload()`.

---

#### Task 9: Decision Module — Prescriptive Action Cards

**Verification Scenario 1: Normal Recommendations**

```bash
curl -X POST "http://localhost:8002/api/v1/ai/ui/recommendations" \
  -H "Content-Type: application/json" \
  -H "x-request-id: req-rec-e2e-001" \
  -d '{"asset_id": "P-101A", "risk_horizon_days": 30, "max_recommendations": 5}'
```

**Expected browser behavior:**
- Action cards render in `rank` ascending order
- Each card shows: action type, description, priority badge (HIGH → red), severity tier
- SOP linkage card shows `sopId`, `title`, `revision`, `effectiveness` percentage
- Cost avoidance shows formatted USD (e.g., "$42,000")
- Completion deadline shows human-readable date (not raw ISO)
- `riskScoreIfIgnored` shows as a progress bar or percentage

**Verification Scenario 2: No Recommendations Available**

When the decision engine returns an empty list, `data === []`.

**Expected browser behavior:**
- Panel shows "No maintenance actions recommended at this time."
- No `TypeError: Cannot read properties of undefined (reading 'actionId')`

---

### Task 10: Graceful Error Handling & Boundary Verification

**Validation Vector 1: Invalid Asset ID**

```bash
curl -X GET "http://localhost:8002/api/v1/ai/ui/digital-twin/NONEXISTENT-999" \
  -H "x-request-id: req-err-001"
```

**Expected response:**

```json
{
  "success": true,
  "data": {
    "asset": {"id": "NONEXISTENT-999", "name": "NONEXISTENT-999", "type": "PUMP", "status": "OPERATIONAL", "parentId": null},
    "telemetry": {"speed": 0.0, "vibration": 0.0, "pressure": 0.0, "temperature": 0.0, "flowRate": 0.0, "load": 0.0, "riskScore": 0.0, "status": "ok"},
    "history": [],
    "activeAnomaly": null,
    "generated_at": "2026-07-18T..."
  },
  "error": null,
  "requestId": "req-err-001",
  "generatedAt": "..."
}
```

**Key check:** The browser receives a valid envelope with `success: true` and safe defaults — no white-screen crash.

**Validation Vector 2: AI Infrastructure Timeout**

Simulate by temporarily disconnecting the prediction engine. The ui_router's `except` block catches the error:

```json
{
  "success": false,
  "data": {},
  "error": {"code": "DIGITAL_TWIN_FAILED", "message": "predictive engine unreachable", "details": null},
  "requestId": "req-err-002",
  "generatedAt": "..."
}
```

**Expected browser behavior:**
- Component renders a "Telemetry unavailable" fallback pill
- `success === false` triggers the error branch
- No uncaught exception in console
- No white-screen crash

**Validation Vector 3: Empty Chat Messages**

```bash
curl -X POST "http://localhost:8002/api/v1/ai/ui/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-1", "asset_id": "P-101A", "messages": []}'
```

**Expected:** HTTP 200 with `success: false`, `error.code: "INVALID_REQUEST"`, or HTTP 422. Either is acceptable. The browser must handle both gracefully.

**Validation Vector 4: CORS Rejection (Wrong Origin)**

```bash
curl -X OPTIONS "http://localhost:8002/api/v1/ai/ui/options" \
  -H "Origin: http://evil-site.com"
```

**Expected:** HTTP 204 with NO `Access-Control-Allow-Origin` header (the origin is not in the allow-list). The browser will block the actual request — this is correct behaviour.

**Validation Vector 5: Malformed JSON Body**

```bash
curl -X POST "http://localhost:8002/api/v1/ai/ui/graphrag/query" \
  -H "Content-Type: application/json" \
  -d '{invalid json'
```

**Expected:** HTTP 422 with structured error envelope (handled by `validation_exception_handler`):

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed. Check payload shape, field types, and allowed values.",
  "request_id": "...",
  "details": [...]
}
```

No stack trace leaked. No Python internals exposed. Browser receives a structured, handleable error.

---

### Tasks 11 & 12: Joint Bug Bash Execution & Isolation Protocol

#### Bug Bash Execution Rules

1. **Duration:** 30 minutes of focused testing across all 5 core modules.
2. **Method:** Member 4 performs every user action they can think of while Member 3 monitors server logs in real-time.
3. **Logging:** Every bug is immediately entered into the Bug Bash Triage Register below.
4. **Severity:** High = white-screen or data loss; Medium = visual corruption or missing data; Low = cosmetic or performance.

#### Bug Bash Triage Register Template

| Bug ID | Component Impacted | Observed Behavior | Severity (High/Med/Low) | Root-Cause Layer (AI vs. UI) | Verification Test Hash | Status |
|---|---|---|---|---|---|---|
| BUG-P4-001 | (to be filled during session) | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-002 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-003 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-004 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-005 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-006 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-007 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-008 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-009 | | | | | | OPEN/FIXED/CLOSED |
| BUG-P4-010 | | | | | | OPEN/FIXED/CLOSED |

#### Root-Cause Isolation Protocol

When a bug is found:

1. **Capture the browser console output verbatim.** Example:
   ```
   TypeError: Cannot read properties of null (reading 'nodes')
       at GraphRagPanel (GraphRagPanel.tsx:82:18)
       at renderWithHooks (react-dom.development.js:16305:18)
   ```

2. **Capture the network response.** In DevTools → Network → click the failed request → Response tab. Copy the full JSON.

3. **Determine root-cause layer:**
   - **AI Layer:** The JSON payload is malformed (null arrays, wrong casing, missing fields). Member 3 fixes the adapter.
   - **UI Layer:** The JSON payload is correct but the component doesn't handle it (missing null check, wrong key name). Member 4 fixes the component.

4. **Fix and verify:** The responsible member fixes the issue, redeploys, and the other member verifies the fix.

5. **Regression test:** Re-run the specific test case that exposed the bug to confirm the fix holds.

---

### Tasks 13–15: Stability Checks, Performance Baselines, & Final Handshakes

#### Task 13: Stability Checks

**Smoke Test Sequence (run 3 times consecutively):**

```bash
for i in 1 2 3; do
  echo "=== Stability Run $i ==="
  curl -s http://localhost:8002/api/v1/ai/ui/digital-twin/P-101A | python -c "import sys,json; d=json.load(sys.stdin); print('success:', d['success'], 'history_len:', len(d['data']['history']))"
  curl -s -X POST http://localhost:8002/api/v1/ai/ui/graphrag/query -H "Content-Type: application/json" -d '{"query":"vibration?","asset_id":"P-101A"}' | python -c "import sys,json; d=json.load(sys.stdin); print('success:', d['success'], 'nodes:', len(d['data']['nodes']))"
  curl -s http://localhost:8002/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A | python -c "import sys,json; d=json.load(sys.stdin); print('success:', d['success'], 'features:', len(d['data']['features']))"
  curl -s -X POST http://localhost:8002/api/v1/ai/ui/recommendations -H "Content-Type: application/json" -d '{"asset_id":"P-101A"}' | python -c "import sys,json; d=json.load(sys.stdin); print('success:', d['success'], 'actions:', len(d['data']))"
  echo ""
done
```

**Expected:** All 3 runs produce identical structural output (same key names, same array lengths, same enum values). Values may differ (timestamps, UUIDs) but structure must be identical.

#### Task 14: Performance Baselines

#### Frontend E2E Latency Observation Table

| # | User Action | Expected Click-to-Render Time | Acceptable Range | Actual Observed | Pass/Fail |
|---|---|---|---|---|---|
| 1 | Load DigitalTwinView for P-101A | 800ms | < 2000ms | | |
| 2 | Submit GraphRAG query "Why is P-101A vibrating?" | 1200ms | < 3000ms | | |
| 3 | Load SHAP explanation for pred-p101a-001 | 600ms | < 2000ms | | |
| 4 | Generate recommendations for P-101A | 500ms | < 1500ms | | |
| 5 | Send chat message "Diagnose P-101A" | 1000ms | < 3000ms | | |
| 6 | Open CORS check endpoint | 100ms | < 500ms | | |
| 7 | Stream chat response (first byte to final event) | 2000ms | < 5000ms | | |
| 8 | Re-fetch DigitalTwinView (cached) | 200ms | < 800ms | | |
| 9 | Load contract manifest | 50ms | < 200ms | | |

**Measurement method:** Member 4 uses browser DevTools → Performance tab → records the action → reads the "DOMContentLoaded" to "Last paint" duration.

#### Task 15: Final Handshake

**Step-by-step final inspection sequence:**

1. **Full Regression Run:**
   ```bash
   python -m pytest tests/test_phase11_ui_router_contract.py tests/test_phase11_frontend_adapters.py tests/test_phase11_payload_formatters.py tests/test_phase11_cors_headers.py tests/test_phase11_chat_event_adapter.py -v
   ```
   **Expected:** All tests pass.

2. **Cross-Origin Smoke Test:**
   Member 4 opens `http://localhost:3000` and performs every AI-backed action in the UI while Member 3 watches server logs.

3. **Zero Console Errors Check:**
   Member 4 opens DevTools Console, performs all 9 endpoint interactions, and confirms **zero** red error messages.

4. **Zero Client-Side Transformation Audit:**
   Member 3 reviews Member 4's code one final time for anti-patterns (see Task 5).

5. **Sign-off:** Member 4 signs the Phase 4 Exit Checklist.

---

## 4. Comprehensive Phase 4 Deliverables Checklist

| # | Deliverable | Physical Artifact | Status |
|---|---|---|---|
| 1 | Phase 4 Engineering Execution Guide | `PHASE4_ENGINEERING_EXECUTION_GUIDE_LATHIKA.md` | ✅ |
| 2 | Phase 4 Integration Validation Script | `scripts/phase4/phase4_integration_validation.py` | ✅ |
| 3 | Phase 4 Worked Files Manifest | `PHASE4_WORKED_FILES_MANIFEST_PHASE4.md` | ✅ |
| 4 | Signed Integration Matrix | `phase4_signed_integration_matrix.json` | Pending Member 4 sign-off |
| 5 | Bug Register Log | `phase4_bug_bash_register.json` | To be completed during session |
| 6 | Latency Profile Report | `phase4_latency_profile.json` | To be completed during session |
| 7 | Phase 4 Exit Checklist (updated) | `PHASE4_EXIT_CHECKLIST.md` | Pending completion |
| 8 | Zero-Transformation Audit Report | `phase4_zero_transform_audit.md` | Pending Member 4 code review |
| 9 | Updated CORS Verification | `scripts/phase4/phase4_cors_verify.sh` | ✅ |
| 10 | E2E Smoke Test Script | `scripts/phase4/phase4_e2e_smoke.sh` | ✅ |

---

## 5. Binary Exit Criteria (The Ultimate Sign-off Gatekeeper)

The following requirements must be **perfectly met** before Member 3 declares implementation responsibilities 100% complete. Each checkbox requires explicit verification — not assumption.

- [ ] **[EC-1]** Every single AI-backed panel inside Member 4's application renders seamlessly without a single browser console error.

  *Verification:* Member 4 opens DevTools Console, performs all 9 endpoint interactions sequentially, and confirms zero red error messages. Screenshot or copy-paste of empty console attached to sign-off.

- [ ] **[EC-2]** Member 4 issues an explicit technical sign-off confirming zero client-side payload translation is present.

  *Verification:* Member 4 runs `grep -rn "\.map(" src/services/ | grep -v node_modules` and confirms zero results for data reshaping. Member 4 signs `phase4_signed_integration_matrix.json` with `{ "signoff": true, "zeroTransformConfirmed": true, "signedBy": "Member 4", "date": "2026-07-18" }`.

- [ ] **[EC-3]** End-to-end routing (Frontend → Gateway → AI Platform → Core Engine) functions error-free on a composed deployment environment.

  *Verification:* `docker compose up` builds and starts all containers. `curl http://localhost:8080/api/v1/ai/ui/cors-check` returns `success: true`. All 9 UI endpoints respond with `success: true` through the gateway.

- [ ] **[EC-4]** All blocking integration bugs captured during the joint bug bash session are confirmed fixed and regression-tested.

  *Verification:* Every entry in `phase4_bug_bash_register.json` with `severity: "High"` or `severity: "Med"` must have `status: "CLOSED"`. Low-severity bugs may be deferred with a JIRA ticket reference.

- [ ] **[EC-5]** The application passes full regression test passes across every core module under local and joint conditions.

  *Verification:* `python -m pytest tests/ -v --tb=short` exits with code 0. All Phase 11 test suites pass. No skipped tests in the critical path.

---

**Document Prepared By:** Member 3 (Lathika) — AI/ML Knowledge Engineer

**Document Date:** 2026-07-18

**Document Version:** 1.0.0

**Next Action:** Schedule synchronous pair-integration session with Member 4.
