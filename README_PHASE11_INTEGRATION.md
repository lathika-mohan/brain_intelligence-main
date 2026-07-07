# Phase 11 — Frontend Integration Support

Phase 11 binds the FastAPI AI Intelligence platform to the
pre-built Next.js / React components in `src/components/`. It adds
an isolated, **strictly contract-driven** layer under
`app/ai_service/integration/` that:

1. **Projects** the same engines (GraphRAG, Predictive, XAI,
   Decision, Agent) through UI-shaped endpoints at
   `/api/v1/ai/ui/*` so the React components can `fetch` and bind
   directly.
2. **Validates** every response through a Pydantic v2 model that
   is a 1-to-1 mirror of the Section 11 TypeScript layouts
   (`src/types/index.ts`) and the component-level interfaces
   declared inline in `src/components/*.tsx`.
3. **Streams** multi-agent diagnostic turns as deterministic
   `application/x-ndjson` event blocks the chat panel can render
   line-by-line.
4. **Verifies** CORS configuration from CI with a dedicated
   `/api/v1/ai/ui/cors-check` endpoint, and provides a manual
   `/api/v1/ai/ui/options` preflight probe for the browser
   console.
5. **Documents** the entire contract surface in
   [`docs/AI_PAYLOAD_SPEC.md`](docs/AI_PAYLOAD_SPEC.md) with
   copy-pasteable JSON examples for every endpoint and a
   field-by-field binding map for every component.

> **No React, TypeScript, or Next.js code is shipped from this
> phase.** The contract flows strictly *backend → JSON → frontend*
> without any UI rewrite.

---

## Endpoints Added

| Method   | Path                                              | Feeds                                  |
| -------- | ------------------------------------------------- | -------------------------------------- |
| `GET`    | `/api/v1/ai/ui/digital-twin/{asset_id}`           | `DigitalTwinView.tsx`                  |
| `POST`   | `/api/v1/ai/ui/graphrag/query`                    | `GraphRagPanel.tsx`                    |
| `GET`    | `/api/v1/ai/ui/explain/{prediction_id}`           | `ShapExplainability.tsx`               |
| `POST`   | `/api/v1/ai/ui/recommendations`                   | Prescriptive-action card panel         |
| `POST`   | `/api/v1/ai/ui/agent/chat`                        | Multi-agent chat (non-streaming)       |
| `POST`   | `/api/v1/ai/ui/agent/chat/stream`                 | Multi-agent chat (NDJSON stream)       |
| `GET`    | `/api/v1/ai/ui/cors-check`                        | CORS verification (CI / smoke)         |
| `OPTIONS`| `/api/v1/ai/ui/options`                           | Browser preflight probe                |
| `GET`    | `/api/v1/ai/ui/contracts`                         | Contract manifest for type generation  |

Every response is wrapped in the Section 11 `APIResponse<T>`
envelope: `{ success, data, error, requestId, generatedAt }`.

---

## Files Added (21)

```
app/ai_service/integration/
├── __init__.py
├── adapters/
│   ├── __init__.py
│   ├── frontend_adapters.py          (data transformers)
│   └── chat_event_adapter.py         (NDJSON event stream)
├── formatters/
│   ├── __init__.py
│   ├── payload_formatters.py         (chart-ready formatters)
│   └── confidence_badge.py           (badge/colour mappers)
├── schemas/
│   ├── __init__.py
│   ├── ui_schemas.py                 (Pydantic v2 strict mirrors)
│   └── chat_event_schemas.py         (NDJSON event schemas)
├── cors_headers.py                   (CORS verification helpers)
└── ui_router.py                      (FastAPI sub-router)

tests/
├── fixtures/
│   └── ui_payload_samples.py
├── test_phase11_frontend_adapters.py
├── test_phase11_payload_formatters.py
├── test_phase11_cors_headers.py
├── test_phase11_chat_event_adapter.py
└── test_phase11_ui_router_contract.py

docs/
├── AI_PAYLOAD_SPEC.md
└── AI_CORS_INTEGRATION.md
```

Plus the top-level: `PHASE11_WORKED_FILES_MANIFEST.md`,
`PHASE11_INSTALL.md`, `README_PHASE11_INTEGRATION.md`.

---

## Files Modified (0)

Phase 11 is fully additive. To activate the new endpoints, the
operator adds **one try/except block** to
`app/api/v1/router.py`:

```python
try:
    from app.ai_service.integration.ui_router import ui_router
    api_router.include_router(ui_router)
    logger.info("Phase 11 UI contract router mounted at /ai/ui")
except Exception as e:  # pragma: no cover
    logger.warning("Phase 11 UI router not mounted: %s", e)
```

See [`PHASE11_INSTALL.md`](PHASE11_INSTALL.md) for the full
install guide.

---

## Verification

```bash
# All Phase 11 tests
pytest tests/test_phase11_frontend_adapters.py \
       tests/test_phase11_payload_formatters.py \
       tests/test_phase11_cors_headers.py \
       tests/test_phase11_chat_event_adapter.py \
       tests/test_phase11_ui_router_contract.py -v

# Phase 10 contract suite still passes
pytest tests/test_phase10_ai_service.py -v
```

The contract suite asserts every endpoint's envelope, every
required key, every data type, the NDJSON stream order, the
CORS header echo, the deterministic graph layout, and the
pre-sorted SHAP feature order.

---

## Documentation

* [`docs/AI_PAYLOAD_SPEC.md`](docs/AI_PAYLOAD_SPEC.md) — the
  full playbook Member 4 will use to bind the React components
  to the AI service.
* [`docs/AI_CORS_INTEGRATION.md`](docs/AI_CORS_INTEGRATION.md) —
  CORS / network guide for Member 1 (gateway) and Member 4
  (frontend).
* [`PHASE11_WORKED_FILES_MANIFEST.md`](PHASE11_WORKED_FILES_MANIFEST.md) —
  complete file manifest.
* [`PHASE11_INSTALL.md`](PHASE11_INSTALL.md) — quick install
  guide.

---

## What changed for existing endpoints

**Nothing.** The Phase 10 `/api/v1/ai/*` endpoints remain
unchanged, fully tested, and continue to power Member 1's
gateway. The Phase 11 `/api/v1/ai/ui/*` family is a **strict
additive projection** of the same engines, tuned for
direct-to-frontend binding.
