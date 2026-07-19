# Phase 11 — UI Router Contract Fix (Worked-Files Manifest)

**Target test:** `pytest tests/test_phase11_ui_router_contract.py -v`
**Result:** `24 passed` (was `22 failed / 2 passed` on the shipped baseline)
**Date:** 2026-07-18

---

## 1. What was broken

The router module **`app/ai_service/integration/ui_router.py`** shipped as a
**174-line stub**. The stub was correctly *mounted* (so the routes existed and
returned HTTP 200) but its response shapes did **not** satisfy the Section 11 UI
contract that `tests/test_phase11_ui_router_contract.py` enforces.

Concrete gaps in the stub:

| # | Contract requirement (from the test) | Stub behaviour | Fixed behaviour |
|---|--------------------------------------|----------------|-----------------|
| 1 | `x-ai-module: phase-11-ui` header on every UI response | Not emitted | Emitted on all 9 endpoints |
| 2 | Echo inbound `x-request-id` verbatim | Not echoed | Echoed (falls back to `x-correlation-id` / new UUID) |
| 3 | Digital Twin: `data.history` must be a **non-empty** list | Returned `[]` | Real telemetry history frames |
| 4 | GraphRAG: keys `answer, logs, nodes, edges, highlightedNodes, highlightedEdges, citations, vectorHits, confidence` + `badge / warningLevel / color`; node `type` ∈ panel vocabulary | Wrong keys, no badges | Full adapter projection + confidence formatter |
| 5 | Explain: `features` (`name`,`shapValue`) sorted by \|shapValue\| desc, plus `waterfall` + `forcePlot` | `{feature, shap_value}`, no plots | Sorted features + waterfall/force formatters |
| 6 | Recommendations: **endpoint missing** | 404 (no route) | `POST /ui/recommendations` → list of action cards |
| 7 | Agent chat (non-stream) | 404 | `POST /ui/agent/chat` → `UIChat` envelope |
| 8 | Agent chat NDJSON stream; first event `heartbeat` seq 0 | 404 | `POST /ui/agent/chat/stream` → `application/x-ndjson` |
| 9 | `GET /ui/cors-check` (200 ok / 503 misconfigured) | 404 | Implemented (verifies CORS allow-list) |
| 10 | `OPTIONS /ui/options` → 204 + CORS headers | 404 | Implemented |
| 11 | `GET /ui/contracts`: `phase == "11-frontend-integration-support"`, full `/api/v1/ai/ui/...` paths, all 9 endpoints | `phase` had `-enhanced-phase5` suffix, relative `/ui/...` paths, 5 endpoints | Exact contract phase + all 9 full paths |

## 2. The worked file (exactly one)

```
app/ai_service/integration/ui_router.py      (174 → 714 lines, +679 / −138)
```

The full, contract-compliant implementation already existed in the repository
as the reference copy `package/app/ai_service/integration/ui_router.py`. It was
authored against the **existing** integration package and imports cleanly from
the modules that were already present:

```
app/ai_service/integration/adapters/chat_event_adapter.py     (existing)
app/ai_service/integration/adapters/frontend_adapters.py      (existing)
app/ai_service/integration/formatters/confidence_badge.py     (existing)
app/ai_service/integration/formatters/payload_formatters.py   (existing)
app/ai_service/integration/schemas/ui_schemas.py              (existing)
app/ai_service/integration/cors_headers.py                    (existing)
```

This change therefore **re-uses 100% of the existing wiring** — no new modules,
no signature changes, no edits to adapters/formatters/schemas/models. Only the
stub router was promoted to the complete implementation.

## 3. Integration with existing wiring (verified)

The mount chain is unchanged and already correct:

```
app.main: app.include_router(api_router, prefix="/api/v1")
   └─ app/api/v1/router.py   →  api_router.include_router(ai_router)   [Phase 10]
         └─ app/ai_service/main_router.py  →  ai_router(prefix="/ai")
               .include_router(ui_router)                              # prefix="/ui"
                     └─ /api/v1/ai/ui/*   ← all 9 contract endpoints
```

Engine wiring uses FastAPI dependency providers from
`app/ai_service/dependencies.py` (`get_graphrag_engine`,
`get_prediction_engine`, `get_xai_engine`, `get_decision_engine`). The router
resolves them lazily so `app.dependency_overrides[...]` in tests maps straight
onto the real callables — confirmed by the green run with stub engines and by
graceful degradation when real engines/infra are absent.

## 4. How to apply

Copy the file over the stub in your local clone (paths preserved):

```bash
# from the repo root
cp app/ai_service/integration/ui_router.py app/ai_service/integration/ui_router.py.bak   # optional backup
unzip phase11_ui_router_worked_files.zip   # contains app/ai_service/integration/ui_router.py
```

Then validate:

```bash
python -m venv .venv && . .venv/bin/activate
pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" pydantic==2.9.2 \
            pydantic-settings==2.5.2 httpx==0.27.2 orjson==3.10.7 \
            python-dotenv==1.0.1 pytest==8.3.3 pytest-asyncio==0.24.0 \
            numpy==1.26.4 pandas==2.2.3
pytest tests/test_phase11_ui_router_contract.py -v          # expect 24 passed
```

Heavy runtime deps (torch, xgboost, shap, neo4j, qdrant-client, langgraph,
sentence-transformers) are **not required for this test** — every handler
imports them lazily and degrades to a sanitized 503/envelope if the real engine
is unavailable. The test stubs the four engines, so it is zero-infrastructure.

## 5. Live boot smoke (over real HTTP, not just TestClient)

`uvicorn app.main:app --port 8011` (APP_ENV=development):

| Route | Result |
|-------|--------|
| `GET  /health` | `200` |
| `GET  /api/v1/ai/ui/contracts` | `200`, envelope ok, `x-ai-module=phase-11-ui`, `x-request-id` echoed |
| `OPTIONS /api/v1/ai/ui/options` | `204`, `allow-origin=http://localhost:3000`, `allow-methods=GET, POST, OPTIONS`, `vary=Origin` |
| `GET  /api/v1/ai/ui/cors-check` | `503 misconfigured` *(correct — surfaces that `.env` only lists `localhost:3000`; test accepts 200 or 503)* |

## 6. Contents of this zip

```
app/ai_service/integration/ui_router.py   ← THE worked file (drop into your repo)
PHASE11_UI_ROUTER_CONTRACT_FIX.md         ← this manifest / integration notes
evidence/baseline_stub_pytest.txt         ← raw pytest log: 2 passed / 22 failed
evidence/fixed_pytest.txt                 ← raw pytest log: 24 passed
```

## 7. Notes

- Only **one** application file changed. `git diff --stat`:
  `app/ai_service/integration/ui_router.py | 817 ++++++++++++++++++++++++++------`
  (1 file changed, 679 insertions(+), 138 deletions(-)).
- The reference copy `package/app/ai_service/integration/ui_router.py` is now
  identical to the live `app/...` copy; it may be kept as a reference or removed.
- Sibling suites still green: `test_phase10_ai_service.py`,
  `test_phase11_cors_headers.py`, `test_phase11_chat_event_adapter.py`,
  `test_phase11_frontend_adapters.py`, `test_phase11_payload_formatters.py`
  → **113 passed**, no regressions.
