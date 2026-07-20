# Phase 2 — Existing Endpoint Contract Corrections — Worked Files Manifest

## Summary

Phase 2 aligns the existing AI endpoint contracts (Digital Twin, GraphRAG,
Explain/XAI) exposed at `/api/v1/ai/ui/*` strictly with the frontend
specifications. **All corrections are response-shaping only** — no ML
algorithms, model inference, graph traversal, or business calculations
were modified. Existing engine outputs are wrapped/transformed immediately
before entering the Phase 1 (Phase 11) `UIAPIResponse` envelope.

**Baseline before Phase 2:** 24/24 router-contract tests passing, but the
payloads violated five frontend requirements (no top-level `riskScore`,
raw ontology node types, no explicit waterfall/forcePlot typing, snake_case
key leakage, `method` query param rejected lowercase values with 422 and
gave no HTTP 400 path).

**After Phase 2:** 41/41 router-contract tests passing
(17 new Phase 2 correction tests added), with zero regressions in the
sibling Phase 11 suites (123/123 across the integration layer).

---

## [DELIVERABLE 1] Endpoint Refactoring Log

### 1. Routes refactored (`app/ai_service/integration/ui_router.py`)

| Route | Change |
|---|---|
| `GET /api/v1/ai/ui/digital-twin/{asset_id}` | Payload now carries **top-level `riskScore`** (float 0..100, never null) attached by the adapter; explicit `sanitize_arrays()` pass runs before Pydantic validation. |
| `POST /api/v1/ai/ui/graphrag/query` | Payload now carries **stepwise execution `logs`** detailing retrieval/graph-traversal, **validated node types**, standardized node ids/labels/relation names, camelized citations; `sanitize_arrays()` pass added. |
| `GET /api/v1/ai/ui/explain/{prediction_id}` | `method` query param now **case-insensitive + alias-aware** (`shap`, `lime`, `integrated_gradients`, `ig`, `permutation`); unsupported values return a clear **HTTP 400** `XAI_UNSUPPORTED_METHOD` error in the envelope (was: 422 pattern rejection). Method is forwarded to the adapter for payload tailoring; `waterfall`/`forcePlot` validated against new explicit typed schemas; `sanitize_arrays()` pass added. |
| `_ui_response()` helper | New optional `http_status` parameter so client-side validation failures (400) can reuse the envelope; engine failures still default to 503. |

### 2. Schemas updated (`app/ai_service/integration/schemas/ui_schemas.py`)

| Model | Change |
|---|---|
| `UIDigitalTwinPayload` | Added top-level `riskScore: float (0..100, default 0.0)`; `generated_at` now serialized via alias **`generatedAt`** (camelCase everywhere). |
| `UIWaterfallStep` / `UIWaterfall` | **New.** Explicit waterfall typing: `feature, value, delta, start, end, cumulative, direction` per step; `baseValue`, `finalValue`, `bars[]` at the top. |
| `UIForceContribution` / `UIForcePlot` | **New.** Explicit force-plot typing: `baseValue`, `predictionValue`, `positive[]` / `negative[]` pushing-force stacks with feature mappings (`feature, value, weight, direction`). |
| `UIShapExplanation` | `waterfall` / `forcePlot` upgraded from loose `Dict[str, Any]` to the explicit `UIWaterfall` / `UIForcePlot` models. |

### 3. New module (`app/ai_service/integration/response_shaping.py`)

Pure response-shaping utilities shared by all three endpoint domains:

* `camelize_keys()` / `to_camel_case()` / `find_non_camel_keys()` — camelCase everywhere (explicit `shap_value → shapValue` coverage + full-payload sweeps).
* `sanitize_arrays()` — replaces any `None` list attribute with `[]` recursively before serialization.
* `compute_top_level_risk_score()` — top-level `riskScore` from the inference failure probability → telemetry fallback → safe `0.0` default.
* `validate_node_type()` / `normalize_node_id()` / `normalize_node_label()` / `normalize_relation_name()` — GraphRAG vocabulary alignment against the closed panel ontology `{asset, component, anomaly, procedure, record}`; unknown/raw types are mapped or deterministically degraded (never leaked).
* `build_graphrag_execution_logs()` — structured stepwise string traces (`vector_search → graph_traversal → node_type_validation → citation_binding → llm_synthesis`).
* `resolve_explain_method()` + `UnsupportedExplainMethodError` — `?method=` normalization and HTTP-400-ready validation.
* `sort_features_by_impact()` / `method_descriptor()` — |shapValue| desc ordering and per-method descriptor tailoring.

### 4. Adapters refactored (`app/ai_service/integration/adapters/frontend_adapters.py`)

* `adapt_digital_twin_payload` — attaches top-level `riskScore`, serializes `by_alias=True` (`generatedAt`), sanitizes arrays, and reads asset fields through a dict/object-safe accessor (`_field`) so the asset block is always populated.
* `adapt_graphrag_payload` — node vocabulary alignment, strict node-type validation (with remap audit trail surfaced in `logs`), canonicalized relation names, camelized citations, execution-log trace, non-null array guarantee.
* `adapt_explainability_payload` — `requested_method` tailoring (`SHAP contribution` vs `LIME local linear weight` vs `Integrated-gradients attribution`), camelCase sweep, |shapValue| desc re-sort, array sanitization.
* `adapt_asset` — dict/object-safe field access.

### 5. Tests updated

* `tests/test_phase11_ui_router_contract.py` — **+17 Phase 2 tests** (`TestPhase2DigitalTwinCorrections`, `TestPhase2GraphRagCorrections`, `TestPhase2ExplainCorrections`): top-level `riskScore` present/numeric/default-safe, non-null arrays, strict camelCase, execution logs, node vocabulary mapping, relation standardization, camelized citations, `shapValue` rename, method aliases, **HTTP 400** for unsupported methods, explicit waterfall arithmetic, explicit force-plot structure.
* `tests/test_phase11_frontend_adapters.py` — two legacy assertions updated to the **Phase 2 execution-log format** (`STEP n: vector_search…` replaces the superseded `Vector search initiated…` phrasing, which Phase 2 replaced with detailed stepwise traces).

### 6. Sample payloads generated

Captured from live endpoint calls (stubbed engines, same fixtures as the
contract suite) — see `docs/phase2_sample_payloads/`:

#### 6.1 Digital Twin — `GET /api/v1/ai/ui/digital-twin/P-101A?horizon=3` → 200

```json
{
  "success": true,
  "data": {
    "asset": { "id": "P-101A", "name": "P-101A", "type": "PUMP", "status": "OPERATIONAL", "parentId": null },
    "telemetry": { "speed": 2903.14, "vibration": 6.18, "pressure": 7.15, "temperature": 88.92,
                   "flowRate": 101.39, "load": 203.28, "riskScore": 64.0, "status": "critical" },
    "history": [ { "timestamp": "2026-01-10T23:30:00+00:00", "speed": 2907.33, "vibration": 6.17,
                   "pressure": 7.18, "temperature": 88.6, "flowRate": 101.94, "load": 211.49,
                   "riskScore": 64.0, "status": "ok" } ],
    "riskScore": 64.0,
    "activeAnomaly": "bearing-wear",
    "generatedAt": "2026-07-20T04:46:04Z"
  },
  "requestId": "…", "generatedAt": "…", "error": null
}
```

✔ top-level `riskScore` present + numeric · ✔ arrays never null · ✔ camelCase throughout

#### 6.2 GraphRAG — `POST /api/v1/ai/ui/graphrag/query` → 200

```json
{
  "success": true,
  "data": {
    "answer": "P-101A shows bearing wear signature.",
    "logs": [
      "STEP 1: vector_search: embedded query 'Why is P-101A vibrating?'",
      "STEP 2: vector_search: 3 chunk hit(s) retrieved",
      "STEP 3: graph_traversal: expanded 3 node(s) / 2 edge(s) from seed hits",
      "STEP 4: node_type_validation: remapped raw ontology type(s) [FailureMode, SOP] into panel vocabulary",
      "STEP 5: citation_binding: attached 1 citation(s)",
      "STEP 6: citation_binding: [1] SOP (confidence=0.91)",
      "STEP 7: llm_synthesis: answer drafted, overall_confidence=0.87",
      "STEP 8: completed: total latency 11.0 ms"
    ],
    "nodes": [
      { "id": "asset:P-101A", "label": "P-101A", "type": "asset", "x": 60.0, "y": 60.0, "details": "P-101A" },
      { "id": "fm:bearing", "label": "Bearing Wear", "type": "anomaly", "x": 320.0, "y": 60.0, "details": "Bearing Wear" },
      { "id": "sop:SOP-MECH-042", "label": "SOP-MECH-042", "type": "procedure", "x": 440.0, "y": 60.0, "details": "SOP-MECH-042" }
    ],
    "edges": [
      { "source": "asset:P-101A", "target": "fm:bearing", "label": "HAS_FAILURE_MODE", "highlighted": false },
      { "source": "fm:bearing", "target": "sop:SOP-MECH-042", "label": "MITIGATED_BY", "highlighted": false }
    ],
    "highlightedNodes": ["sop:SOP-MECH-042"],
    "highlightedEdges": [],
    "citations": [ { "citationId": "cit-1", "claimSpan": "vibration 5.2 mm/s", "sourceDocument": "sop-p101a.pdf",
                     "sourceType": "SOP", "sourceNodeId": "sop:SOP-MECH-042", "confidenceScore": 0.91,
                     "pageNumber": null, "url": null } ],
    "vectorHits": 3,
    "confidence": 0.87,
    "badge": "high",
    "warningLevel": "industrial-status-ok",
    "color": ["#22c55e", "text-green-600", "bg-green-50"],
    "generatedAt": "2026-07-20T04:46:04Z"
  },
  "requestId": "…", "generatedAt": "…", "error": null
}
```

✔ execution `logs` detail every step · ✔ raw types (`Asset`, `FailureMode`, `SOP`) validated/mapped into the panel vocabulary · ✔ relation names standardized · ✔ citations camelCased

#### 6.3 XAI — `GET /api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=shap` → 200

```json
{
  "success": true,
  "data": {
    "predictionId": "pred-p101a-001",
    "assetId": "P-101A",
    "method": "SHAP",
    "scope": "LOCAL",
    "baseValue": 0.31,
    "predictionValue": 0.72,
    "features": [
      { "name": "vibration_rms", "value": "9.5mm/s", "shapValue": 0.42, "desc": "SHAP contribution +0.42 (rank 1, observed 9.5mm/s)" },
      { "name": "bearing_temp", "value": "82°C", "shapValue": 0.31, "desc": "SHAP contribution +0.31 (rank 2, observed 82°C)" },
      { "name": "rpm", "value": "1480RPM", "shapValue": -0.05, "desc": "SHAP contribution -0.05 (rank 3, observed 1480RPM)" }
    ],
    "confidenceMatrix": [ { "label": "SHAP convergence", "confidence": 0.95 } ],
    "rootCause": { "headline": "Vibration dominated alert",
                   "narrative": "Elevated vibration is consistent with bearing wear.",
                   "contributingFailureModes": ["fm-bearing-wear"] },
    "waterfall": {
      "baseValue": 0.31,
      "finalValue": 0.99,
      "bars": [
        { "feature": "vibration_rms", "value": "9.5mm/s", "delta": 0.42, "start": 0.31, "end": 0.73, "cumulative": 0.73, "direction": "positive" },
        { "feature": "bearing_temp", "value": "82°C", "delta": 0.31, "start": 0.73, "end": 1.04, "cumulative": 1.04, "direction": "positive" },
        { "feature": "rpm", "value": "1480RPM", "delta": -0.05, "start": 1.04, "end": 0.99, "cumulative": 0.99, "direction": "negative" }
      ]
    },
    "forcePlot": {
      "baseValue": 0.31,
      "predictionValue": 0.72,
      "positive": [ { "feature": "vibration_rms", "value": "9.5mm/s", "weight": 0.42, "direction": "positive" },
                    { "feature": "bearing_temp", "value": "82°C", "weight": 0.31, "direction": "positive" } ],
      "negative": [ { "feature": "rpm", "value": "1480RPM", "weight": 0.05, "direction": "negative" } ]
    },
    "generatedAt": "2026-07-20T04:46:04Z"
  },
  "requestId": "…", "generatedAt": "…", "error": null
}
```

✔ `shapValue` rename · ✔ camelCase everywhere · ✔ features sorted by |shapValue| desc · ✔ explicit waterfall + forcePlot

#### 6.4 XAI method tailoring + HTTP 400 path

`GET …/explain/pred-p101a-001?method=lime` → **200**, `data.method = "LIME"`,
feature descs become `"LIME local linear weight +0.42 (…)"`.

`GET …/explain/pred-p101a-001?method=integrated_gradients` → **200**,
`data.method = "INTEGRATED_GRADIENTS"`.

`GET …/explain/pred-p101a-001?method=deeplift` → **400**:

```json
{
  "success": false,
  "data": { "predictionId": "pred-p101a-001", "assetId": "P-101A", "baseValue": 0.0,
            "predictionValue": 0.0, "features": [], "confidenceMatrix": [], "rootCause": {} },
  "requestId": "…",
  "generatedAt": "…",
  "error": {
    "code": "XAI_UNSUPPORTED_METHOD",
    "message": "Unsupported explainability method 'deeplift'. Supported methods: SHAP, LIME, INTEGRATED_GRADIENTS, PERMUTATION.",
    "details": { "method": "deeplift",
                 "supported": ["SHAP", "LIME", "INTEGRATED_GRADIENTS", "PERMUTATION"],
                 "acceptedAliases": ["shap", "lime", "integrated_gradients", "ig", "permutation"] }
  }
}
```

---

## [DELIVERABLE 2] Automated Verification Report

Raw terminal log: **`phase2_pytest_verification.log`** (committed alongside
this manifest). Final summary line:

```
======================= 41 passed, 17 warnings in 2.08s ========================
```

Full verbose listing of every test (24 pre-existing + 17 Phase 2) is in the
log file. The sibling integration suites also pass with zero regressions:

```
tests/test_phase11_frontend_adapters.py       25 passed
tests/test_phase11_payload_formatters.py      27 passed
tests/test_phase11_chat_event_adapter.py      24 passed
tests/test_phase11_cors_headers.py             6 passed
tests/test_phase11_ui_router_contract.py      41 passed   ← target suite
---------------------------------------------   --------
TOTAL                                        123 passed
```

---

## Worked Files (zip contents, paths relative to repo root)

### Added (4 + 6 artifacts)

| File | Purpose |
|---|---|
| `app/ai_service/integration/response_shaping.py` | Phase 2 response-shaping utilities (camelize, sanitize arrays, riskScore, node vocab/type gate, execution logs, method resolver, sorting) |
| `scripts/phase2/capture_phase2_samples.py` | Reproducible sample-payload capture script |
| `PHASE2_CONTRACT_CORRECTIONS_MANIFEST.md` | This file |
| `phase2_pytest_verification.log` | Deliverable 2 raw pytest log |
| `docs/phase2_sample_payloads/digital_twin.json` | Live sample — Digital Twin |
| `docs/phase2_sample_payloads/graphrag_query.json` | Live sample — GraphRAG |
| `docs/phase2_sample_payloads/xai_explain_shap.json` | Live sample — XAI (SHAP) |
| `docs/phase2_sample_payloads/xai_explain_lime.json` | Live sample — XAI (LIME tailoring) |
| `docs/phase2_sample_payloads/xai_explain_unsupported_method_400.json` | Live sample — HTTP 400 path |

### Modified (6)

| File | Purpose |
|---|---|
| `app/ai_service/integration/schemas/ui_schemas.py` | Top-level `riskScore`, `generatedAt` alias, explicit `UIWaterfall`/`UIForcePlot` models |
| `app/ai_service/integration/schemas/__init__.py` | Re-export new models |
| `app/ai_service/integration/adapters/frontend_adapters.py` | Phase 2 shaping in the three domain adapters + dict-safe `_field` accessor |
| `app/ai_service/integration/ui_router.py` | Method resolution + HTTP 400, sanitizer passes, `http_status` envelope support |
| `tests/test_phase11_ui_router_contract.py` | +17 Phase 2 contract-correction tests |
| `tests/test_phase11_frontend_adapters.py` | 2 assertions updated to the Phase 2 execution-log contract |

## Integration Notes (existing wiring preserved)

* **No new routes, no moved routers.** The corrections land inside the
  existing Phase 11 wiring: `app/main.py → /api/v1 → ai_router → ui_router`
  — no changes to `main.py`, `main_router.py`, or any raw `/api/v1/ai/*`
  engine endpoints.
* **Engines untouched.** `predictive`, `graphrag`, `decision`, `orchestration`
  services and all model files under `app/models/` are byte-identical; only
  the UI projection layer transforms their outputs.
* **Backwards compatible.** All 24 pre-existing contract tests pass
  unchanged; the new fields are additive and the `method` param accepts a
  superset of the old vocabulary.
