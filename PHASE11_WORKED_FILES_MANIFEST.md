# Phase 11 Worked Files Manifest — Frontend Integration Support

## Summary

Phase 11 closes the integration gap between the Phase 0–10 FastAPI
backend (`app/ai_service/*`) and the pre-built Next.js / TypeScript
components in `src/components/*`. It introduces an isolated
**UI-contract projection layer** under
`app/ai_service/integration/` that exposes the same engines
through `/api/v1/ai/ui/*` endpoints with byte-for-byte Pydantic
validation against the Section 11 TypeScript layouts, plus a
chart-ready formatter module, a CORS verification helper, and a
handful of contract tests.

**Zero React / TypeScript / Next.js code is shipped.** Member 4
binds directly to the documented JSON contracts; no client-side
parser code is required.

## Added Files (21)

### Adapter layer — `app/ai_service/integration/`

| File                                                | Purpose                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------- |
| `app/ai_service/integration/__init__.py`            | Module entry point + public re-exports                                           |
| `app/ai_service/integration/adapters/__init__.py`   | Adapter sub-package exports                                                      |
| `app/ai_service/integration/adapters/frontend_adapters.py` | Backend Pydantic → Section 11 + component shapes (digital twin, GraphRAG, SHAP, recommendations, envelope) |
| `app/ai_service/integration/adapters/chat_event_adapter.py` | Phase 9 LangGraph states → NDJSON event stream (heartbeat, tools, citations, sub-graph) |
| `app/ai_service/integration/formatters/__init__.py` | Formatter sub-package exports                                                    |
| `app/ai_service/integration/formatters/payload_formatters.py` | Recharts / Chart.js / d3 / vis-network payload formatters + SHAP waterfall & force-plot |
| `app/ai_service/integration/formatters/confidence_badge.py`  | 0..1 confidence → UI badge / colour / warning-level mappers              |
| `app/ai_service/integration/schemas/__init__.py`    | Schemas sub-package exports                                                      |
| `app/ai_service/integration/schemas/ui_schemas.py`  | Pydantic v2 strict mirror of Section 11 + component-level contracts               |
| `app/ai_service/integration/schemas/chat_event_schemas.py` | NDJSON stream event schemas (heartbeat, tool, citation, subgraph, final)    |
| `app/ai_service/integration/cors_headers.py`        | CORS / preflight verification helpers + explicit header echo                     |
| `app/ai_service/integration/ui_router.py`           | FastAPI sub-router mounted at `/api/v1/ai/ui/*` exposing the UI-shaped projections |

### Test layer — `tests/`

| File                                                       | Purpose                                                                |
| ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| `tests/fixtures/ui_payload_samples.py`                     | Golden sample payloads used by the contract tests                      |
| `tests/test_phase11_frontend_adapters.py`                  | Unit tests for the 6 adapter functions + envelope helpers             |
| `tests/test_phase11_payload_formatters.py`                 | Unit tests for the chart-ready formatters + confidence badge           |
| `tests/test_phase11_cors_headers.py`                       | Unit tests for the CORS helpers + preflight header echo                |
| `tests/test_phase11_chat_event_adapter.py`                 | Unit tests for the chat event adapter (heartbeat / stream / final)     |
| `tests/test_phase11_ui_router_contract.py`                 | End-to-end contract tests via FastAPI `TestClient` (9 endpoints)       |

### Documentation — `docs/` + repo root

| File                                                       | Purpose                                                                |
| ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| `docs/AI_PAYLOAD_SPEC.md`                                  | The frontend handoff playbook — copy-pasteable JSON for every endpoint |
| `docs/AI_CORS_INTEGRATION.md`                              | CORS / network integration guide for Member 1 + Member 4               |
| `PHASE11_WORKED_FILES_MANIFEST.md` (this file)              | Manifest of every file added / modified in Phase 11                    |
| `PHASE11_INSTALL.md`                                       | Quick install guide — where to drop each file                          |
| `README_PHASE11_INTEGRATION.md`                            | Top-level integration README (mirrors `README_INTEGRATION.md` style)   |

## Modified Files (0)

Phase 11 adds an **isolated, additive** layer. No existing file in
the repo is modified. To activate the new endpoints the operator
adds **one line** to `app/api/v1/router.py`:

```python
try:
    from app.ai_service.integration.ui_router import ui_router
    api_router.include_router(ui_router)
    logger.info("Phase 11 UI contract router mounted at /ai/ui")
except Exception as e:  # pragma: no cover
    logger.warning("Phase 11 UI router not mounted: %s", e)
```

This is documented in `PHASE11_INSTALL.md` and is fully
backward-compatible (the router import is wrapped in the same
try/except pattern used for the Phase 10 `ai_router`).

## Endpoints Added (9)

| Method   | Path                                              | Schema / Response model      |
| -------- | ------------------------------------------------- | ---------------------------- |
| `GET`    | `/api/v1/ai/ui/digital-twin/{asset_id}`           | `UIDigitalTwinPayload`       |
| `POST`   | `/api/v1/ai/ui/graphrag/query`                    | `UIGraphRAGPayload`          |
| `GET`    | `/api/v1/ai/ui/explain/{prediction_id}`           | `UIShapExplanation`          |
| `POST`   | `/api/v1/ai/ui/recommendations`                   | `List[UIRecommendationAction]` |
| `POST`   | `/api/v1/ai/ui/agent/chat`                        | `UIAPIResponse[UIChat]`      |
| `POST`   | `/api/v1/ai/ui/agent/chat/stream`                 | `AgentStreamEvent[]` NDJSON  |
| `GET`    | `/api/v1/ai/ui/cors-check`                        | `CORSStatus`                 |
| `OPTIONS`| `/api/v1/ai/ui/options`                           | (empty body, CORS headers)   |
| `GET`    | `/api/v1/ai/ui/contracts`                         | `ContractManifest`           |

## Verification

```bash
# Run all Phase 11 tests
pytest tests/test_phase11_frontend_adapters.py \
       tests/test_phase11_payload_formatters.py \
       tests/test_phase11_cors_headers.py \
       tests/test_phase11_chat_event_adapter.py \
       tests/test_phase11_ui_router_contract.py -v
```

Expected result: **all tests pass.** The contract suite asserts
every endpoint's envelope, every required key, every data type,
the NDJSON stream order, the CORS header echo, and the
deterministic graph layout.

The existing Phase 10 contract suite still passes (Phase 11 is
fully additive):

```bash
pytest tests/test_phase10_ai_service.py -v
```
