# AI PAYLOAD SPEC — Phase 11 Frontend Handoff Playbook

**Audience:** Member 4 (Frontend Engineer) — and any future integration work
that needs to bind the AI Intelligence platform to the Next.js dashboard.

**Status:** ✅ Frozen for Phase 11. Breaking changes require a new spec
revision and a migration note in this file.

**Source of truth:** [`app/ai_service/integration/`](../../app/ai_service/integration/)
on the backend. The TypeScript types in
[`src/types/index.ts`](../../src/types/index.ts) and the inline component
types in `src/components/*.tsx` are the *frontend* source of truth.

---

## 1. How to use this document

1. Find your component in the **§3 Component Contract Map** below.
2. Note the URL + method + section 11 envelope shape.
3. Copy the **Example Payload** straight into your data hook — every
   field is real, every type is the strict Pydantic-validated shape.
4. If your component reads a field that isn't in the example, **stop**:
   either the field is misnamed in your component, or you need a Phase
   11.1 enhancement. Open a ticket against Member 3 — do not silently
   infer or default it client-side.

---

## 2. The Section 11 envelope (every endpoint)

```ts
interface APIResponse<T> {
  success: boolean;
  data: T;
  error?: { code: string; message: string; details?: unknown };
  requestId: string;
  generatedAt: string; // ISO-8601 UTC
}
```

Every Phase 11 endpoint wraps its payload in this envelope. The
backend's frozen `app.models.common.APIResponse` uses `error: string`,
so the Phase 11 adapter normalises string errors into the
**object** form expected by `src/types/index.ts`. Components should
**always** check `success` first; if `false`, read `error.code` and
`error.message` for the diagnostic copy.

> **Tip:** the `requestId` is echoed back verbatim from the
> `x-request-id` request header (when present), so the front-end can
> stamp the same id into its own logging / Sentry breadcrumbs for
> end-to-end tracing.

---

## 3. Component Contract Map

| Component (`src/components/`)       | Method | URL                                              | Response Schema             | Pydantic model                            |
| ----------------------------------- | ------ | ------------------------------------------------ | --------------------------- | ----------------------------------------- |
| `DigitalTwinView.tsx`               | GET    | `/api/v1/ai/ui/digital-twin/{asset_id}`          | `UIDigitalTwinPayload`      | `UIDigitalTwinPayload`                    |
| `GraphRagPanel.tsx`                 | POST   | `/api/v1/ai/ui/graphrag/query`                   | `UIGraphRAGPayload`         | `UIGraphRAGPayload`                       |
| `ShapExplainability.tsx`            | GET    | `/api/v1/ai/ui/explain/{prediction_id}`          | `UIShapExplanation`         | `UIShapExplanation`                       |
| Prescriptive-action card panel      | POST   | `/api/v1/ai/ui/recommendations`                  | `UIRecommendationAction[]`  | `List[UIRecommendationAction]`            |
| Multi-agent chat (non-streaming)    | POST   | `/api/v1/ai/ui/agent/chat`                       | `UIChat`                    | `UIAPIResponse[UIChat]`                   |
| Multi-agent chat (NDJSON stream)    | POST   | `/api/v1/ai/ui/agent/chat/stream`                | `AgentStreamEvent[]` (NDJSON) | `AgentStreamEvent`                      |
| CORS preflight probe                | GET    | `/api/v1/ai/ui/cors-check`                       | `CORSStatus`                | (raw dict)                                |
| CORS preflight (manual)             | OPTIONS| `/api/v1/ai/ui/options`                          | (empty body, CORS headers)  | —                                         |
| Contract manifest (for type-gen)    | GET    | `/api/v1/ai/ui/contracts`                        | `ContractManifest`          | (raw dict)                                |

The frontend should call the **`/api/v1/ai/ui/*`** family in
production. The legacy `/api/v1/ai/*` family stays in place for the
existing tests and for Member 1's gateway, but the UI-shaped payload
is the contract Member 4 binds to.

---

## 4. `DigitalTwinView.tsx`

### Request

```http
GET /api/v1/ai/ui/digital-twin/P-101A?horizon=24&include_inference=true
Headers:
  x-request-id: <client-generated UUID>
```

| Query param         | Type | Default | Notes                                                   |
| ------------------- | ---- | ------- | ------------------------------------------------------- |
| `horizon`           | int  | `24`    | Lookback in hours. Clamped to 1..168.                   |
| `include_inference` | bool | `true`  | When true, runs the predictive engine to set riskScore. |

### Response

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

### Field-by-field binding

* `data.telemetry.speed` → "Rotational Speed" card (RPM)
* `data.telemetry.vibration` → "Housing Vibration" card (mm/s)
* `data.telemetry.pressure` → "Discharge Pressure" card (bar)
* `data.telemetry.temperature` → Casing Temperature label
* `data.telemetry.flowRate` → pumps/compressors flow rate label
* `data.telemetry.load` → Electrical Load label
* `data.telemetry.riskScore` → "AI Risk Index" (0..100)
* `data.telemetry.status` → top status pill; values: `ok` | `warning` | `critical` | `offline`
* `data.activeAnomaly` → branches the SVG schematic and the
  `getShapFeatures()` logic in `ShapExplainability.tsx`. Values the
  component checks: `bearing-wear`, `compressor-surge`,
  `electrical-trip`, `leakage`. `null` is safe (falls through to
  nominal rendering).
* `data.history[]` → the 24-frame chronological array used by
  `renderMiniChart()` for the four telemetry cards. **The mini
  chart in the component reads `reading[dataKey]`**, so we keep
  the same flat-key vocabulary as `telemetry`. No nested objects.
* `data.asset.id` → branches the SVG schematic (`turbine-01` /
  `compressor-02` / `pump-03`).
* `data.asset.status` → top asset-status pill.

### Error response

```json
{
  "success": false,
  "data": {},
  "error": {
    "code": "DIGITAL_TWIN_FAILED",
    "message": "predictive engine unreachable",
    "details": null
  },
  "requestId": "req-dt-1",
  "generatedAt": "2026-07-07T07:15:00.123456"
}
```

Components should display a fallback "Telemetry unavailable" pill
when `success === false`.

---

## 5. `GraphRagPanel.tsx`

### Request

```http
POST /api/v1/ai/ui/graphrag/query
Content-Type: application/json

{
  "query": "Why did the vibration on Turbine-01 spike?",
  "asset_id": "turbine-01",
  "top_k": 8
}
```

The `query` key mirrors the component's `setQuery(...)` state. The
adapter also accepts `query_text` (the raw backend vocabulary) for
backward compat. `top_k` is optional; default 8, max 50.

### Response

```json
{
  "success": true,
  "data": {
    "answer": "Vibration spike on Turbine-01 originates at Bearing B1. The matching failure mode is bearing wear (F-02) with 91% confidence. Recommended mitigation: SOP-MECH-042 (lubrication and rotor alignment).",
    "logs": [
      "Vector search initiated: 'Why did the vibration on Turbine-01 spike?'",
      "Vector hits: 4 chunks",
      "Citation 1: SOP (confidence=0.91)",
      "Sub-graph projected: 3 nodes / 2 edges",
      "Synthesizing response context via LLM..."
    ],
    "nodes": [
      {
        "id": "asset:turbine-01",
        "label": "Turbine-01",
        "type": "asset",
        "x": 60.0,
        "y": 60.0,
        "details": "Turbine-01 — Asset status: Warning. Telemetry stream: Active."
      },
      {
        "id": "fm:bearing",
        "label": "Bearing Wear (F-02)",
        "type": "anomaly",
        "x": 320.0,
        "y": 60.0,
        "details": "Confidence: 91%. Wear signature matching telemetry."
      },
      {
        "id": "sop:SOP-MECH-042",
        "label": "SOP-MECH-042",
        "type": "procedure",
        "x": 440.0,
        "y": 60.0,
        "details": "Lubrication & Rotor Alignment Procedure v2.1"
      }
    ],
    "edges": [
      {
        "source": "asset:turbine-01",
        "target": "fm:bearing",
        "label": "has_failure_mode",
        "highlighted": true
      },
      {
        "source": "fm:bearing",
        "target": "sop:SOP-MECH-042",
        "label": "mitigated_by",
        "highlighted": true
      }
    ],
    "highlightedNodes": ["sop:SOP-MECH-042"],
    "highlightedEdges": ["fm:bearing-sop:SOP-MECH-042"],
    "citations": [
      {
        "citation_id": "cit-1",
        "claim_span": "vibration 5.2 mm/s",
        "source_document": "sop-p101a.pdf",
        "source_type": "SOP",
        "source_node_id": "sop:SOP-MECH-042",
        "confidence_score": 0.91
      }
    ],
    "vectorHits": 4,
    "confidence": 0.87,
    "badge": "high",
    "warningLevel": "industrial-status-ok",
    "color": ["#22c55e", "text-green-600", "bg-green-50"],
    "generatedAt": "2026-07-07T07:15:00.000000"
  },
  "error": null,
  "requestId": "req-rag-1",
  "generatedAt": "2026-07-07T07:15:00.123456"
}
```

### Field-by-field binding

* `data.nodes[].id/label/type/x/y/details` → `GRAPH_NODES` shape; the
  component already destructures these by name.
* `data.nodes[].type` → drives `getNodeColor(type, isHighlighted)`
  in the SVG renderer. Vocabulary: `asset | component | anomaly |
  procedure | record`.
* `data.edges[].source/target/label/highlighted` → `GRAPH_EDGES` shape.
  `highlighted` is computed server-side from citation graph proximity.
* `data.highlightedNodes[]` / `data.highlightedEdges[]` → IDs the
  component matches against when styling. The `highlightedEdges`
  array is formatted as `"{source}-{target}"`.
* `data.logs[]` → consumed by `setLoadingLogs((prev) => [...prev,
  data.logs[currentStep]])`. The adapter pre-populates a
  chronological loading strip (vector search → citation retrieval →
  subgraph projection → LLM synthesis) so the panel's animation
  always has data to scroll through.
* `data.answer` → final text rendered in the answer panel.
* `data.confidence` → drives the `industrial-status-*` colour on the
  answer header. Use `data.warningLevel` for a single Tailwind class
  or `data.color[1]` for the inline text class.
* `data.badge` → `very_low | low | medium | high | very_high`. The
  component can use this to pick a label ("High confidence") for
  accessibility / aria-live announcements.
* `data.citations[]` → sources the panel renders in the source-chip
  tray. The component reads `claimSpan`, `sourceDocument`, and
  `confidenceScore` directly.

### Node layout (deterministic, no client-side force simulation)

The component's hand-rolled SVG renderer relies on absolute ``x``/``y``
coordinates. The Phase 11 adapter projects a **deterministic
left-to-right layered layout** when the upstream graph traversal
returns nodes without positions:

* Column 1 (`x = 60`)  → `asset` nodes
* Column 2 (`x = 200`) → `component` nodes
* Column 3 (`x = 320`) → `anomaly` / failure-mode nodes
* Column 4 (`x = 440`) → `procedure` / SOP nodes
* Column 5 (`x = 540`) → `record` / incident nodes

Y positions are spaced at 80px intervals in lexicographic node-id
order so the layout is **stable across re-renders** and re-fetches.

---

## 6. `ShapExplainability.tsx`

### Request

```http
GET /api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=SHAP
Headers:
  x-request-id: <client-generated UUID>
```

| Query param | Type   | Default | Notes                                                  |
| ----------- | ------ | ------- | ------------------------------------------------------ |
| `asset_id`  | string | `P-101A`| Required.                                              |
| `method`    | string | `SHAP`  | `SHAP | LIME | INTEGRATED_GRADIENTS | PERMUTATION`.    |

### Response

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
      {
        "name": "vibration_rms",
        "value": "9.5mm/s",
        "shapValue": 0.42,
        "desc": "SHAP contribution +0.42 (rank 1, observed 9.5mm/s)"
      },
      {
        "name": "bearing_temp",
        "value": "82°C",
        "shapValue": 0.31,
        "desc": "SHAP contribution +0.31 (rank 2, observed 82°C)"
      },
      {
        "name": "rpm",
        "value": "1480RPM",
        "shapValue": -0.05,
        "desc": "SHAP contribution -0.05 (rank 3, observed 1480RPM)"
      },
      {
        "name": "pressure",
        "value": "6.4bar",
        "shapValue": 0.02,
        "desc": "SHAP contribution +0.02 (rank 4, observed 6.4bar)"
      }
    ],
    "confidenceMatrix": [
      { "label": "SHAP convergence", "confidence": 0.95 }
    ],
    "rootCause": {
      "headline": "Vibration dominated alert",
      "narrative": "Elevated vibration is consistent with bearing wear.",
      "contributingFailureModes": ["fm-bearing-wear"]
    },
    "waterfall": {
      "baseValue": 0.31,
      "finalValue": 1.01,
      "bars": [
        { "feature": "vibration_rms", "value": "9.5mm/s", "delta": 0.42, "start": 0.31, "end": 0.73, "cumulative": 0.73, "direction": "positive" },
        { "feature": "bearing_temp", "value": "82°C", "delta": 0.31, "start": 0.73, "end": 1.04, "cumulative": 1.04, "direction": "positive" },
        { "feature": "rpm", "value": "1480RPM", "delta": -0.05, "start": 1.04, "end": 0.99, "cumulative": 0.99, "direction": "negative" },
        { "feature": "pressure", "value": "6.4bar", "delta": 0.02, "start": 0.99, "end": 1.01, "cumulative": 1.01, "direction": "positive" }
      ]
    },
    "forcePlot": {
      "baseValue": 0.31,
      "predictionValue": 0.72,
      "positive": [
        { "feature": "vibration_rms", "value": "9.5mm/s", "weight": 0.42, "direction": "positive" },
        { "feature": "bearing_temp", "value": "82°C", "weight": 0.31, "direction": "positive" },
        { "feature": "pressure", "value": "6.4bar", "weight": 0.02, "direction": "positive" }
      ],
      "negative": [
        { "feature": "rpm", "value": "1480RPM", "weight": 0.05, "direction": "negative" }
      ]
    },
    "generatedAt": "2026-07-07T07:15:00.000000"
  },
  "error": null,
  "requestId": "req-xai-1",
  "generatedAt": "2026-07-07T07:15:00.123456"
}
```

### Field-by-field binding

* `data.features[]` is **pre-sorted by `|shapValue|` descending** so
  the panel can render top-to-bottom with no client-side sort. The
  component still re-sorts in-place, which is fine — it's a stable
  sort.
* `data.features[].name` → label in the bar / waterfall / force
  component. Vocabulary: `rpm`, `vibration_rms`, `bearing_temp`,
  `pressure`, `flow_rate`, `load_kw`.
* `data.features[].value` → human-readable string with engineering
  unit (`9.5mm/s`, `82°C`, `1480RPM`, `6.4bar`). The adapter applies
  the unit lookup automatically.
* `data.features[].shapValue` → signed contribution. Positive values
  push risk up (red), negative values push risk down (green).
* `data.features[].desc` → tooltip / accessibility text.
* `data.baseValue` / `data.predictionValue` → anchors for the SHAP
  force-plot (`baseValue` on the left, `predictionValue` on the
  right, features stacked between).
* `data.waterfall` → ready-to-render Recharts floating-bar series.
  The bars are pre-sorted and the cumulative math is done server-side
  so the panel can simply `<Bar dataKey="start" /> <Bar dataKey="end" />`
  with `delta`-aware colour.
* `data.forcePlot` → ready-to-render d3 / SVG stacked-arrow series.
  `positive[]` and `negative[]` are pre-partitioned.
* `data.rootCause.headline` / `data.rootCause.narrative` → displayed
  above the bar chart.
* `data.confidenceMatrix[]` → optional diagnostic strip; the panel
  can render each entry as a small chip.

### Confidences map to UI warning lights

| Confidence 0..1 | Badge        | `warningLevel`              | `color[0]` (hex) |
| --------------- | ------------ | --------------------------- | ---------------- |
| ≥ 0.95          | `very_high`  | `industrial-status-ok`      | `#16a34a`        |
| ≥ 0.80          | `high`       | `industrial-status-ok`      | `#22c55e`        |
| ≥ 0.60          | `medium`     | `industrial-status-warning` | `#f59e0b`        |
| ≥ 0.30          | `low`        | `industrial-status-warning` | `#f97316`        |
| < 0.30          | `very_low`   | `industrial-status-critical`| `#ef4444`        |

The mapping lives in
[`app/ai_service/integration/formatters/confidence_badge.py`](../../app/ai_service/integration/formatters/confidence_badge.py)
and is exposed as a typed enum on the backend. The frontend can
import the same logic from the manifest endpoint.

---

## 7. Recommendations (prescriptive-action card panel)

### Request

```http
POST /api/v1/ai/ui/recommendations
Content-Type: application/json

{
  "asset_id": "P-101A",
  "component_id": "bearing-de",
  "risk_horizon_days": 30,
  "max_recommendations": 5
}
```

### Response

```json
{
  "success": true,
  "data": [
    {
      "actionId": "act-1",
      "actionType": "INSPECT",
      "description": "Inspect and lubricate P-101A drive-end bearing.",
      "priority": "HIGH",
      "severityTier": "SCHEDULED",
      "riskScoreIfIgnored": 0.78,
      "estimatedCostAvoidanceUsd": 42000.0,
      "recommendedCompletionBy": "2026-07-09T07:15:00",
      "sop": {
        "sopId": "SOP-PUMP-BEARING",
        "title": "Pump bearing inspection",
        "revision": "v2.1",
        "effectiveness": 0.82
      },
      "rank": 1
    }
  ],
  "error": null,
  "requestId": "req-rec-1",
  "generatedAt": "2026-07-07T07:15:00.123456"
}
```

`actionType` vocabulary: `LUBRICATE | REPLACE | INSPECT | ISOLATE |
CALIBRATE | ALIGN | BALANCE | MONITOR | SHUTDOWN | SCHEDULE_INSPECTION`.

`priority` vocabulary: `LOW | MEDIUM | HIGH | CRITICAL`.

`severityTier` vocabulary: `IMMINENT | SCHEDULED | MONITOR`.

The cards arrive in `rank` ascending order (1 = top card).

---

## 8. Multi-agent chat (non-streaming)

### Request

```http
POST /api/v1/ai/ui/agent/chat
Content-Type: application/json

{
  "session_id": "sess-maint-001",
  "asset_id": "P-101A",
  "messages": [
    { "role": "user", "content": "Diagnose elevated bearing temperature on P-101A." }
  ]
}
```

### Response

```json
{
  "success": true,
  "data": {
    "messageId": "msg-sess-maint-001",
    "sender": "AI_ENGINE",
    "payload": "P-101A shows a likely bearing lubrication issue. Recommend executing SOP-MECH-042 within 48 hours.",
    "timestamp": "2026-07-07T07:15:00.000000",
    "states": [
      { "state": "received", "message": "Accepted diagnostic chat turn.", "payload": { "messages": 1 }, "generated_at": "2026-07-07T07:15:00Z" },
      { "state": "triaged", "message": "Identified asset and selected GraphRAG/decision tools.", "payload": { "asset_id": "P-101A" }, "generated_at": "2026-07-07T07:15:00Z" },
      { "state": "graphrag_retrieved", "message": "Retrieved fused vector/graph context.", "payload": { "vector_hits": 4, "graph_nodes": 5, "citations": 1 }, "generated_at": "2026-07-07T07:15:00Z" },
      { "state": "decision_evaluated", "message": "Evaluated risk-ranked maintenance actions.", "payload": { "recommendations": 1, "overall_risk_score": 0.78 }, "generated_at": "2026-07-07T07:15:00Z" },
      { "state": "final", "message": "Diagnostic turn completed.", "payload": { "response_length": 240 }, "generated_at": "2026-07-07T07:15:00Z" }
    ]
  },
  "error": null,
  "requestId": "req-chat-1",
  "generatedAt": "2026-07-07T07:15:00.123456"
}
```

`data.messageId` is **deterministic** (derived from `session_id`) so
the front-end can dedupe / replace optimistic messages on retry.

`data.states[]` is the **full trace** of the LangGraph-style state
machine for the turn. The component can render this as a
collapsible timeline. Each state is a strict Pydantic
`AgentState` (Phase 10) with the `payload` carrying the
tool-specific metrics.

---

## 9. Multi-agent chat (NDJSON stream)

### Request

```http
POST /api/v1/ai/ui/agent/chat/stream
Content-Type: application/json
Accept: application/x-ndjson

{ "session_id": "sess-1", "asset_id": "P-101A",
  "messages": [{ "role": "user", "content": "Diagnose P-101A" }] }
```

### Response stream (one JSON object per line)

```jsonl
{"eventId":"evt-1a2b3c4d5e","sequence":0,"sessionId":"sess-1","assetId":"P-101A","eventType":"heartbeat","state":null,"message":"Agent runtime connected.","payload":{},"tools":[],"citations":[],"subgraph":null,"logs":[],"generatedAt":"2026-07-07T07:15:00Z","isFinal":false,"isError":false}
{"eventId":"evt-2b3c4d5e6f","sequence":1,"sessionId":"sess-1","assetId":"P-101A","eventType":"state","state":"received","message":"Accepted diagnostic chat turn.","payload":{"messages":1},"tools":[],"citations":[],"subgraph":null,"logs":[{"logId":"log-1","timestamp":"2026-07-07T07:15:00Z","level":"info","message":"Accepted diagnostic chat turn.","context":{"state":"received"}}],"generatedAt":"2026-07-07T07:15:00Z","isFinal":false,"isError":false}
{"eventId":"evt-3c4d5e6f7g","sequence":2,"sessionId":"sess-1","assetId":"P-101A","eventType":"state","state":"triaged","message":"Identified asset and selected GraphRAG/decision tools.","payload":{"asset_id":"P-101A"},"tools":[],"citations":[],"subgraph":null,"logs":[…],"generatedAt":"2026-07-07T07:15:00Z","isFinal":false,"isError":false}
{"eventId":"evt-4d5e6f7g8h","sequence":3,"sessionId":"sess-1","assetId":"P-101A","eventType":"state","state":"graphrag_retrieved","message":"Retrieved fused vector/graph context.","payload":{"vector_hits":4,"graph_nodes":5,"citations":[…]},
 "tools":[{"toolId":"tool-1","toolName":"vector_search","startedAt":"2026-07-07T07:15:00Z","durationMs":12.3,"status":"succeeded","summary":"vector_search completed in 12.3 ms","resultCount":4}],
 "citations":[{"citationId":"c1","claimSpan":"vibration 5.2 mm/s","sourceDocument":"sop.pdf","sourceType":"SOP","confidenceScore":0.91}],
 "subgraph":{"packetId":"sg-1","operation":"add_node","nodes":[{"id":"asset:P-101A"}],"edges":[],"highlightNodeIds":["asset:P-101A"],"highlightEdgeIds":[],"narrative":"Sub-graph context for the current diagnostic turn.","generatedAt":"2026-07-07T07:15:00Z"},
 "logs":[…],"generatedAt":"2026-07-07T07:15:00Z","isFinal":false,"isError":false}
{"eventId":"evt-5e6f7g8h9i","sequence":4,"sessionId":"sess-1","assetId":"P-101A","eventType":"state","state":"decision_evaluated","message":"Evaluated risk-ranked maintenance actions.","payload":{…},"tools":[{"toolName":"decision_eval","status":"succeeded","resultCount":1,…}],"citations":[],"subgraph":null,"logs":[…],"generatedAt":"2026-07-07T07:15:00Z","isFinal":false,"isError":false}
{"eventId":"evt-6f7g8h9i0j","sequence":5,"sessionId":"sess-1","assetId":"P-101A","eventType":"final","state":"final","message":"Diagnostic turn completed.","payload":{…},"tools":[],"citations":[],"subgraph":null,"logs":[…],"generatedAt":"2026-07-07T07:15:00Z","isFinal":true,"isError":false}
```

### Stream contract invariants

* Content-Type is `application/x-ndjson`. Each line is a complete
  JSON object terminated by `\n`. The client iterates with
  `response.body.getReader()` (fetch) or `iter_lines` (axios) and
  `JSON.parse`s each line.
* **First line is always a `heartbeat`** with `sequence === 0`. The
  front-end should render the "Agent thinking…" indicator on
  receipt of this line.
* `sequence` is **monotonic and unique** within one session — the
  client can use it as a stable key for `React.memo` / virtualised
  list keys.
* `eventType` is one of: `state | tool | citation | subgraph | final
  | error | heartbeat`.
* `isFinal === true` marks the last event of the turn. The
  client should collapse the timeline strip on this signal.
* `isError === true` marks a failed event. The `message` field
  carries the sanitised error copy.
* `subgraph` is present on `graphrag_retrieved` events; the client
  appends the contained nodes/edges to the side-panel sub-graph.
* `citations[]` is a flat list the client can render as source
  chips. Each entry has `citationId`, `claimSpan`,
  `sourceDocument`, `sourceType`, `confidenceScore`, and optional
  `pageNumber` / `url`.
* `tools[]` is a flat list the client can render as a tool-
  execution log. Each entry has `toolName`, `durationMs`, `status`,
  `summary`, `resultCount`.

---

## 10. CORS / preflight verification

See [`AI_CORS_INTEGRATION.md`](./AI_CORS_INTEGRATION.md) for the
full network-integration guide. Summary:

* `GET /api/v1/ai/ui/cors-check` returns 200 + allowed origin list
  when the gateway is configured correctly; 503 + remediation
  message otherwise. **Use from CI** to catch misconfiguration
  before the front-end tries to fetch.
* `OPTIONS /api/v1/ai/ui/options` returns the deterministic CORS
  header set the front-end can probe from the browser console.

---

## 11. End-to-end integration checklist (Member 4)

* [ ] `NEXT_PUBLIC_API_URL` env var points at the gateway that
      mounts `app.ai_service.integration.ui_router` (default
      `https://api.iob.enterprise.internal/v1`).
* [ ] `apiClient` interceptor in `src/api/interceptors.ts` sends
      `Content-Type: application/json` and an `x-request-id` per
      request (use `crypto.randomUUID()` if available).
* [ ] The CORS preflight endpoint
      (`/api/v1/ai/ui/options`) is callable from the dev origin
      (`http://localhost:3000`) and the prod origin
      (`https://app.iob.enterprise.internal`).
* [ ] `DigitalTwinView.tsx` binds directly to
      `data.telemetry.{speed,vibration,pressure,temperature,flowRate,load,riskScore,status}`
      and walks `data.history` for the mini charts.
* [ ] `GraphRagPanel.tsx` substitutes its `MOCK_GRAPH_NODES` /
      `MOCK_GRAPH_EDGES` constants with the response of
      `POST /api/v1/ai/ui/graphrag/query` and feeds
      `data.logs` into `setLoadingLogs`.
* [ ] `ShapExplainability.tsx` drops its inline `getShapFeatures()`
      mock in favour of `data.features` (already sorted).
* [ ] `prediction.service.ts` `getPredictions()` proxy
      `POST /api/v1/ai/ui/digital-twin/{asset}` (or read from
      the telemetry context) — the response includes
      `remainingUsefulLifeDays`, `failureProbability`, and
      `inferredFaultMechanism` at the top level when
      `include_inference=true`.
* [ ] `chat.service.ts` `sendMessage()` proxy
      `POST /api/v1/ai/ui/agent/chat` and use `data.messageId`
      for optimistic-update deduplication.
* [ ] The chat panel's WebSocket / streaming connection uses
      `POST /api/v1/ai/ui/agent/chat/stream` and parses the
      `application/x-ndjson` body line-by-line.

---

## 12. Versioning & breaking changes

* All Phase 11 endpoints accept and return **only** the Section 11
  shapes documented above. Any future change must bump the URL
  (e.g. `/api/v1/ai/ui/v2/...`) or version the manifest
  (`GET /api/v1/ai/ui/contracts` → `data.version`).
* The non-`/ui/` family (`/api/v1/ai/query`, `/predict`, etc.)
  is the **raw** Phase 10 contract — frozen, do not bind to it
  from the UI.
* The contract manifest at `GET /api/v1/ai/ui/contracts` is the
  source of truth for "which endpoint feeds which component". The
  TypeScript types in `src/types/index.ts` are the source of truth
  for "what shape is acceptable".

---

**Maintained by:** Member 3 (AI & Knowledge Engineer)
**Last updated:** 2026-07-07
**Backend package:** `app/ai_service/integration/`
**Test suite:** `tests/test_phase11_*.py`
