# Phase 11 Install Guide

This is a short, command-line-first guide to wiring Phase 11 into
your existing `brain_intelligence-main` repository.

> **You only need to drop the files in and add one `try/except`
> block to `app/api/v1/router.py`.** Nothing else changes.

---

## 1. Copy the new files into your repo

The Phase 11 deliverable ships as a tree of *new* files. Drop them
into your existing repo at the matching relative paths:

```
brain_intelligence-main/
├── app/
│   └── ai_service/
│       └── integration/
│           ├── __init__.py                          ← new
│           ├── adapters/
│           │   ├── __init__.py                      ← new
│           │   ├── frontend_adapters.py             ← new
│           │   └── chat_event_adapter.py            ← new
│           ├── formatters/
│           │   ├── __init__.py                      ← new
│           │   ├── payload_formatters.py            ← new
│           │   └── confidence_badge.py              ← new
│           ├── schemas/
│           │   ├── __init__.py                      ← new
│           │   ├── ui_schemas.py                    ← new
│           │   └── chat_event_schemas.py            ← new
│           ├── cors_headers.py                      ← new
│           └── ui_router.py                         ← new
├── tests/
│   ├── fixtures/
│   │   └── ui_payload_samples.py                    ← new
│   ├── test_phase11_frontend_adapters.py            ← new
│   ├── test_phase11_payload_formatters.py           ← new
│   ├── test_phase11_cors_headers.py                 ← new
│   ├── test_phase11_chat_event_adapter.py           ← new
│   └── test_phase11_ui_router_contract.py           ← new
├── docs/
│   ├── AI_PAYLOAD_SPEC.md                           ← new
│   └── AI_CORS_INTEGRATION.md                       ← new
├── PHASE11_WORKED_FILES_MANIFEST.md                 ← new
├── PHASE11_INSTALL.md                               ← new (this file)
└── README_PHASE11_INTEGRATION.md                    ← new
```

**No existing file is modified.**

---

## 2. Mount the Phase 11 router (one line)

Add the following to the end of `app/api/v1/router.py`, inside the
`try/except` block style used for the Phase 10 `ai_router`:

```python
# Phase 11 — Frontend Integration Support (/api/v1/ai/ui/*)
try:
    from app.ai_service.integration.ui_router import ui_router
    api_router.include_router(ui_router)
    logger.info("Phase 11 UI contract router mounted at /ai/ui")
except Exception as e:  # pragma: no cover
    logger.warning("Phase 11 UI router not mounted: %s", e)
```

The router prefix is already `/ui` inside `ui_router.py` and
`/api/v1` is added by the parent `api_router`, so the final URL
is `/api/v1/ai/ui/...`.

---

## 3. CORS configuration

Set the `CORS_ALLOW_ORIGINS` env var on the FastAPI gateway to
include the Next.js dev + prod origins:

```bash
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://app.iob.enterprise.internal
```

These three are the **default** that the Phase 11 helpers
(`app/ai_service/integration/cors_headers.py`) check against, so
if you set them you don't need to touch any code. See
[`docs/AI_CORS_INTEGRATION.md`](docs/AI_CORS_INTEGRATION.md) for the
full CORS integration guide.

---

## 4. Verify

```bash
# Run all Phase 11 tests
pytest tests/test_phase11_frontend_adapters.py \
       tests/test_phase11_payload_formatters.py \
       tests/test_phase11_cors_headers.py \
       tests/test_phase11_chat_event_adapter.py \
       tests/test_phase11_ui_router_contract.py -v

# Verify the new endpoints show up in OpenAPI
curl -sS http://localhost:8000/openapi.json | \
  python -c "import json,sys; d=json.load(sys.stdin); print(*sorted(p for p in d['paths'] if '/ai/ui/' in p), sep='\n')"

# Smoke-test CORS configuration
curl -sS http://localhost:8000/api/v1/ai/ui/cors-check | python -m json.tool
```

Expected CORS check output (when origins are configured):

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "allowedOrigins": [
      "http://localhost:3000",
      "http://127.0.0.1:3000",
      "https://app.iob.enterprise.internal"
    ],
    "exposedHeaders": [
      "content-type",
      "x-request-id",
      "x-correlation-id",
      "x-ai-module",
      "x-ai-version"
    ]
  },
  "error": null,
  "requestId": "...",
  "generatedAt": "..."
}
```

If `success: false`, the `remediation` field tells you exactly
which env var to set.

---

## 5. Hand off to Member 4

Point them at [`docs/AI_PAYLOAD_SPEC.md`](docs/AI_PAYLOAD_SPEC.md).
It contains a copy-pasteable JSON example for every endpoint and
a field-by-field binding map for every component.

The end-to-end integration checklist is in
[`docs/AI_PAYLOAD_SPEC.md#11-end-to-end-integration-checklist-member-4`](docs/AI_PAYLOAD_SPEC.md#11-end-to-end-integration-checklist-member-4).
