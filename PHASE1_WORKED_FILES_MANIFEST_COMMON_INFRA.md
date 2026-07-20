# Phase 1 — Common Infrastructure & Response Contract (Worked-Files Manifest)

**Target test:** `pytest tests/test_phase11_ui_router_contract.py -v`
**Result:** `24 passed` (unchanged — zero regressions after wiring in the new shared layer)
**New test:** `pytest tests/test_phase1_common_infrastructure.py -v` → `20 passed`
**Full sibling regression:** `152 passed` (all runnable suites; 5 unrelated modules skipped — see §6)
**Repo:** `lathika-mohan/brain_intelligence-main`
**Date:** 2026-07-20

---

## 1. What this phase delivers

A unified, bulletproof response standard (`UIAPIResponse`) plus the
middleware/helper plumbing to enforce it, reusable by **every** endpoint
mounted under `/api/v1/ai/ui/*` — and by any future AI UI submodule that
doesn't even know about Phase 11's existing helpers.

Concretely:

| # | Requirement (spec §1) | Implementation |
|---|------------------------|-----------------|
| 1.1 | `UIAPIResponse` envelope: `requestId`, `generatedAt`, `success`, `error`, `data` | `app/ai_service/common/schemas.py` → `UIAPIResponseEnvelope[T]` + `UIAPIErrorPayload` |
| 1.2 | `x-ai-module` header on every response | `app/ai_service/common/middleware.py` → `UIContractRoute` (router `route_class`) injects it even for hand-rolled responses; `create_ui_response` also sets it explicitly |
| 1.2 | `x-request-id` echo (or generated fallback) | `UIContractRoute.get_route_handler()` resolves it pre-handler via `resolve_request_id()`, stashes on `request.state.request_id`; `create_ui_response` echoes it on the response |
| 1.3 | No `null` arrays — empty arrays must be `[]` | `app/ai_service/common/responses.py` → `sanitize_arrays()`, applied automatically inside `create_ui_response()` |
| 2.1 | Shared middleware/dependency layer | `UIContractRoute` / `make_ui_contract_route()` |
| 2.2 | Shared response helper | `create_ui_response()` |

## 2. New files (this delivery)

```
app/ai_service/common/__init__.py       (new) — package surface / re-exports
app/ai_service/common/schemas.py        (new) — UIAPIResponseEnvelope, UIAPIErrorPayload, utc_now_iso()
app/ai_service/common/responses.py      (new) — create_ui_response(), sanitize_arrays(), KNOWN_ARRAY_FIELDS
app/ai_service/common/middleware.py     (new) — UIContractRoute, make_ui_contract_route(), resolve_request_id(), get_request_id()
tests/test_phase1_common_infrastructure.py (new) — 20 unit/e2e tests for the package above
```

## 3. Modified files (this delivery)

```
app/ai_service/integration/ui_router.py  (modified, minimal/surgical)
```

Exact changes to `ui_router.py`:

1. Added imports from the new `app.ai_service.common` package.
2. Removed the now-unused `to_ui_api_envelope` import (superseded — the
   function itself is untouched in `frontend_adapters.py` for any other
   caller).
3. Added `route_class=make_ui_contract_route(module="phase-11-ui")` to the
   `ui_router = APIRouter(...)` construction — this is the "attach to the
   router instance" step from Section 3.2. Every one of the 9 existing
   routes on this router (`digital-twin`, `graphrag/query`,
   `explain/{id}`, `recommendations`, `agent/chat`,
   `agent/chat/stream`, `cors-check`, `options`, `contracts`)
   automatically inherits the header-injection guarantee — **no
   per-route code changes were needed**.
4. `_request_id()` now delegates to `app.ai_service.common.get_request_id`
   (keeps the exact same call signature/behaviour every existing call
   site already relies on).
5. `_ui_response()` now delegates to `app.ai_service.common.create_ui_response`
   instead of building the envelope inline via `to_ui_api_envelope` +
   raw `JSONResponse` construction (Section 3.3 — "refactor primary
   endpoints ... to route return statements exclusively through the new
   response helper"). Because every route in this file already funnels
   through the single `_ui_response()`/`_request_id()` helper pair, this
   one-function change upgrades **all 9 endpoints** to the Phase 1
   contract simultaneously.

No other file in the repository was modified. `AI_MODULE_NAME = "phase-11-ui"`
was added as a module constant so the route-class safety net and the
response helper agree on the exact header value the existing test suite
asserts (`x-ai-module == "phase-11-ui"`).

## 4. Integration with existing wiring (verified)

Mount chain — **unchanged**:

```
app.main: app.include_router(api_router, prefix="/api/v1")
   └─ app/api/v1/router.py   →  api_router.include_router(ai_router)   [Phase 10]
         └─ app/ai_service/main_router.py  →  ai_router(prefix="/ai")
               .include_router(ui_router)                              # prefix="/ui"
                     └─ /api/v1/ai/ui/*   ← all 9 endpoints, now Phase-1-contracted
```

`ui_router` itself picked up one new construction kwarg
(`route_class=...`); it is still built with `APIRouter(prefix="/ui", ...)`
and included into `ai_router` exactly as before — the parent router does
not need to know or care that its child uses a custom route class.

Engine wiring (`app/ai_service/dependencies.py` — `get_graphrag_engine`,
`get_prediction_engine`, `get_xai_engine`, `get_decision_engine`) is
completely untouched; `app.dependency_overrides[...]` in tests still maps
straight onto the real callables.

## 5. Why a custom `APIRoute` instead of `app.add_middleware`

`fastapi.APIRouter` does not expose `add_middleware` — middleware can only
be attached to an ASGI application (`FastAPI`/`Starlette`), which would
force the contract onto **every** route in the whole service (including
the Phase 0 `/predictive`, `/decision`, `/vector` routers, the Phase 5A
compatibility shims, etc.) — out of scope for "Phase 1 — AI UI endpoints".

Installing a custom `APIRoute` subclass as a router's `route_class` is the
FastAPI-idiomatic way to get router-scoped, middleware-like interception
(pre-handler + post-handler hooks) without touching the app object or any
other router. `UIContractRoute`:

* Resolves/generates `request_id` **before** the handler runs and exposes
  it on `request.state.request_id` (so any dependency or nested call can
  read the exact same id — see `get_request_id()`).
* Then, whatever the handler returns — a `JSONResponse` built by
  `create_ui_response`, a raw `Response`, or a `StreamingResponse` for the
  NDJSON chat endpoint — the post-handler hook force-sets
  `x-request-id` and (if not already present) `x-ai-module` on the
  outgoing headers. This is the "even if a developer forgets" safety net
  called out in Section 1.2/2.1.

`make_ui_contract_route(module=...)` lets any future AI UI sub-router
(Phase 12+, a new `/api/v1/ai/ui/vector/*` panel, etc.) opt into the same
contract with a one-line change: `route_class=make_ui_contract_route(module="phase-12-ui")`.

## 6. How to apply

```bash
# from the repo root
unzip phase1_common_infrastructure_worked_files.zip -d .
```

This overlays:

```
app/ai_service/common/__init__.py
app/ai_service/common/schemas.py
app/ai_service/common/responses.py
app/ai_service/common/middleware.py
app/ai_service/integration/ui_router.py     (overwrites the Phase 11 file)
tests/test_phase1_common_infrastructure.py
```

Then validate (same minimal dependency set the Phase 11 fix already
documents — no new third-party packages required):

```bash
python -m venv .venv && . .venv/bin/activate
pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" pydantic==2.9.2 \
            pydantic-settings==2.5.2 httpx==0.27.2 orjson==3.10.7 \
            python-dotenv==1.0.1 pytest==8.3.3 pytest-asyncio==0.24.0 \
            numpy==1.26.4 pandas==2.2.3

pytest tests/test_phase11_ui_router_contract.py -v        # expect 24 passed (unchanged)
pytest tests/test_phase1_common_infrastructure.py -v       # expect 20 passed (new)
```

## 7. Evidence (raw pytest logs included in this zip, `evidence/`)

```
evidence/phase1_evidence_ui_router_contract.log   → 24 passed
evidence/phase1_evidence_common_infra.log         → 20 passed
evidence/phase1_evidence_full_regression.log      → 152 passed
```

The full regression run excludes five test modules
(`test_phase12_ml_models.py`, `test_phase5_e2e.py`,
`test_phase6_predictive.py`, `test_phase7_xai.py`,
`test_phase8_decision.py`) that fail to *collect* in this sandbox purely
because heavy optional dependencies pinned in `requirements.txt`
(`joblib`, `shap`, `xgboost`'s transitive stack, etc.) were not installed
for this exercise — this is pre-existing and 100% unrelated to this
change (verified via `git status --short`, which shows only
`app/ai_service/integration/ui_router.py` modified and
`app/ai_service/common/` + the new test file added). In a full
`pip install -r requirements.txt` environment those suites are expected
to pass unaffected, since nothing in this delivery touches
`app/predictive/*`, `app/decision/*`, or `app/graph/*`.

## 8. Design choices worth flagging for review

* **Two envelope models now exist side by side on purpose.**
  `app.ai_service.integration.schemas.ui_schemas.UIAPIResponse[T]` (Phase
  11, `extra="forbid"`, snake/camel aliasing) remains the FastAPI
  `response_model=` annotation used for OpenAPI docs generation on each
  route (unchanged). `app.ai_service.common.schemas.UIAPIResponseEnvelope[T]`
  (Phase 1, this delivery) is the **wire-level object actually
  constructed and serialized** by `create_ui_response()`. The two are
  shape-compatible (`requestId/generatedAt/success/error/data`) by
  design — this delivery does not fork the contract, it centralizes the
  *construction* of it so submodules that never import `ui_schemas` (or
  don't want the Generic-typing overhead) still get the exact same
  guarantees. `to_ui_api_envelope()` in `frontend_adapters.py` is left
  untouched for any other existing caller outside `ui_router.py`.
* **Array sanitation is allow-list + heuristic, not schema-introspection.**
  `KNOWN_ARRAY_FIELDS` enumerates every array field name found across the
  Phase 0–11 domain/UI models (`app/models/*.py`,
  `app/ai_service/integration/schemas/*.py`,
  `app/ai_service/schemas.py`), plus a small heuristic
  (`*Ids`, `*_ids`, `*List`, `*_list`, `*Array`, `*_array` suffixes) so a
  future field is still protected without a code change. Non-array
  `None` values (e.g. `parentId`, `description`) are deliberately left
  alone — Section 1.3 only mandates sanitizing *array-typed* fields.
* **`create_ui_response(data=...)` defaults `data` to `None` on failure**
  but still lets a caller *explicitly* pass diagnostic `data` alongside
  `success=False` (used by the existing `/ui/cors-check` endpoint, which
  intentionally reports `{"status": "misconfigured", "remediation": ...}`
  on failure for CI self-diagnosis). This matches the pre-existing,
  already-tested behaviour of that endpoint while still defaulting to
  strict `data: null` for every other failure path per Section 1.1.
