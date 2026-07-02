# Team Coordination Boundaries & Data Interchanges (Phase 0)

## Roles
- **Member 1 — Platform Backend**: owns the enterprise API gateway that will
  eventually proxy/aggregate this AI platform's endpoints alongside other
  backend services.
- **Member 2 — PLC/SCADA (Telemetry)**: owns the ingestion pipeline that
  produces live sensor data.
- **Member 3 — AI & Knowledge Engineer (this repo, `ai-platform/`)**: owns
  GraphRAG, Predictive Maintenance, XAI, and the Decision Engine.
- **Member 4 — Frontend**: owns `brain_intelligence` (Next.js), including
  `DigitalTwinView.tsx`, `GraphRagPanel.tsx`, `ShapExplainability.tsx`, and
  the `src/services/*.service.ts` API client layer.

## Upstream — Consumed From Member 2

`app/models/telemetry.py::TelemetryBatch` / `TelemetryReading` is the
FROZEN shape the AI platform expects. Key points:

- `schema_version` is pinned (`"1.0.0"`) — any breaking change to sensor
  field names/units MUST bump this and be renegotiated before Member 3's
  inference pipeline consumes it.
- Units are constrained to the `SensorUnit` enum — if Member 2's SCADA
  historian emits a new unit type, it must be added to the enum, not
  passed as a free string.
- Endpoint: `POST /api/v1/ingestion/telemetry` validates and acknowledges
  batches (Phase 0 stub — no persistence yet).

## Downstream — Provided To Member 4 (Frontend)

The following endpoints + Pydantic response shapes are frozen contracts
Member 4 can bind to immediately, even while responses are Phase 0 stub
data:

| Endpoint                          | Frontend component        | Response schema         |
|-------------------------------------|------------------------------|---------------------------|
| `POST /api/v1/graphrag/query`      | `GraphRagPanel.tsx`          | `GraphRagQueryResponse`  |
| `POST /api/v1/predictive/infer`    | `DigitalTwinView.tsx`        | `InferenceResponse`      |
| `POST /api/v1/xai/explain`         | `ShapExplainability.tsx`     | `ExplanationResponse`    |
| `POST /api/v1/decision/recommend`  | (new prescriptive panel)     | `RecommendationResponse` |

All are wrapped in `APIResponse<T>` — identical envelope shape to the
frontend's own `src/types/index.ts` `APIResponse<T>` (see
`INTEGRATION_NOTES_SECTION11.md` in the repo root), so
`src/services/*.service.ts` can point `apiClient.post<...>()` calls
directly at these paths once `NEXT_PUBLIC_API_URL` is updated to this
service's base URL — no shape translation required on the frontend side.

Suggested frontend wiring (no frontend files were modified in Phase 0,
per mandate — this is guidance for Member 4):

```ts
// src/services/knowledge.service.ts
const res = await apiClient.post<APIResponse<GraphRagQueryResponse>>(
  '/graphrag/query',
  { query, asset_ids: [...] }
);
```

## Downstream — Provided To Member 1 (Platform Backend)

- OpenAPI schema auto-generated at `GET /openapi.json` (and human-readable
  at `/docs`) is the integration artifact for the enterprise gateway.
- `GET /api/v1/health` / `GET /api/v1/health/ready` are provided for
  gateway liveness/readiness routing.
- `SERVICE_API_KEY` (see `.env.example`) is reserved for
  service-to-service auth once the gateway proxies these routes —
  enforcement middleware is out of scope for Phase 0.

## Change control

Any modification to a Pydantic schema in `app/models/*.py` that changes
field names, types, or removes a field is a **breaking change** and
requires:
1. A version bump note in this document.
2. Notification to Member 4 (frontend contract) and/or Member 2
   (telemetry contract), whichever is affected.
