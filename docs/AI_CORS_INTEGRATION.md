# AI CORS / Network Integration Guide — Phase 11

**Audience:** Member 1 (Platform Backend) — for CORS configuration
on the FastAPI gateway, and Member 4 (Frontend) — for the browser
fetch wiring.

---

## 1. CORS allow-list (must include)

The Phase 11 UI endpoints require the following origins on the
gateway's CORS allow-list:

| Origin                            | Why                          |
| --------------------------------- | ---------------------------- |
| `http://localhost:3000`           | Next.js dev server           |
| `http://127.0.0.1:3000`           | Next.js dev server (alias)   |
| `https://app.iob.enterprise.internal` | Production front-end       |

Set them in the gateway's `CORS_ALLOW_ORIGINS` env var as a
comma-separated list:

```bash
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://app.iob.enterprise.internal
```

> **Don't use a wildcard `*`.** Credentialed requests
> (`withCredentials: true`) and custom headers (`x-request-id`,
> `authorization`) are blocked when the gateway uses a wildcard.

---

## 2. Allowed methods

* `GET` — read endpoints (digital-twin, explain, cors-check, options, contracts)
* `POST` — write endpoints (graphrag/query, recommendations, agent/chat, agent/chat/stream)
* `OPTIONS` — preflight

---

## 3. Allowed request headers

The browser will send the following request headers from
`src/api/interceptors.ts`. Make sure they're on the allow-list:

| Header              | Why                                  |
| ------------------- | ------------------------------------ |
| `accept`            | Standard content negotiation         |
| `accept-language`   | i18n                                 |
| `authorization`     | Bearer token (when auth is enabled)  |
| `content-type`      | Required for `application/json` POST |
| `x-request-id`      | End-to-end tracing correlation       |
| `x-correlation-id`  | Alternative tracing id               |
| `x-feature-flags`   | Per-tenant feature flag toggles      |

---

## 4. Exposed response headers

The browser blocks `fetch` from reading custom response headers
unless they're in `Access-Control-Expose-Headers`. The Phase 11
endpoints emit:

| Header           | Why                                              |
| ---------------- | ------------------------------------------------ |
| `content-type`   | Always                                           |
| `x-request-id`   | Echoed from the request (or generated)           |
| `x-correlation-id` | Echoed (alias of x-request-id)                  |
| `x-ai-module`    | Set to `phase-11-ui` — drives the footer credit  |
| `x-ai-version`   | Set to `0.11.0` — drives the version tooltip     |

---

## 5. CORS preflight verification (CI / smoke)

Run this in CI to catch CORS misconfiguration **before** the
front-end's first fetch:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://api.iob.enterprise.internal/v1/ai/ui/cors-check
```

Expected output: `200`. If the response is `503`, the body
contains a `remediation` field with the exact `CORS_ALLOW_ORIGINS`
value to set.

You can also probe from the browser console:

```js
fetch('https://api.iob.enterprise.internal/v1/ai/ui/options', { method: 'OPTIONS' })
  .then(r => {
    console.log('allow-origin:', r.headers.get('access-control-allow-origin'));
    console.log('allow-methods:', r.headers.get('access-control-allow-methods'));
    console.log('allow-headers:', r.headers.get('access-control-allow-headers'));
  });
```

Expected:
* `allow-origin`: `https://app.iob.enterprise.internal`
* `allow-methods`: `GET, POST, OPTIONS`
* `allow-headers`: `accept, accept-language, authorization, content-type, x-request-id, x-correlation-id, x-feature-flags`

---

## 6. Streaming endpoints (NDJSON)

The `/api/v1/ai/ui/agent/chat/stream` endpoint returns
`Content-Type: application/x-ndjson`. The browser's `fetch` will
buffer the response unless the gateway emits:

* `Cache-Control: no-cache` — prevents caching of the stream
* `X-Accel-Buffering: no` — tells nginx (and similar) to disable
  proxy buffering so chunks reach the browser in real time

These headers are already set in
`app/ai_service/integration/ui_router.py`. If you front the API
with nginx / envoy / a CDN, **double-check that the proxy doesn't
override them.**

### Browser fetch snippet

```ts
const res = await fetch('/api/v1/ai/ui/agent/chat/stream', {
  method: 'POST',
  headers: { 'content-type': 'application/json', 'x-request-id': crypto.randomUUID() },
  body: JSON.stringify({ session_id, asset_id, messages }),
});
const reader = res.body!.getReader();
const decoder = new TextDecoder();
let buffer = '';
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  let newline;
  while ((newline = buffer.indexOf('\n')) !== -1) {
    const line = buffer.slice(0, newline);
    buffer = buffer.slice(newline + 1);
    if (line.trim()) {
      const event = JSON.parse(line);
      // dispatch event to the timeline / tool-execution / source-chip panels
    }
  }
}
```

---

## 7. Error envelope (sanitised)

The Phase 11 endpoints always return errors in the Section 11
object form:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "AI_DEPENDENCY_UNAVAILABLE",
    "message": "A required AI dependency is temporarily unavailable.",
    "details": { "engine": "graphrag" }
  },
  "requestId": "req-1",
  "generatedAt": "2026-07-07T07:15:00.000000"
}
```

| Code                         | HTTP | When                                          |
| ---------------------------- | ---- | --------------------------------------------- |
| `AI_SERVICE_ERROR`           | 503  | Catch-all for unclassified errors             |
| `AI_DEPENDENCY_UNAVAILABLE`  | 503  | Neo4j / Qdrant / model artifacts unreachable  |
| `AI_INVALID_REQUEST`         | 422  | Semantic validation failed post-Pydantic      |
| `AI_ENGINE_TIMEOUT`          | 504  | Engine exceeded its deadline                  |
| `VALIDATION_ERROR`           | 422  | Pydantic request validation failed            |
| `DIGITAL_TWIN_FAILED`        | 503  | Phase 11 `digital-twin` exception             |
| `GRAPHRAG_FAILED`            | 503  | Phase 11 `graphrag/query` exception           |
| `XAI_FAILED`                 | 503  | Phase 11 `explain` exception                  |
| `DECISION_FAILED`            | 503  | Phase 11 `recommendations` exception          |
| `AGENT_FAILED`               | 503  | Phase 11 `agent/chat` exception               |
| `CORS_MISCONFIGURED`         | 503  | CORS allow-list missing required origins      |

The `details` field is opaque — never present it directly to the
end user; treat it as a debugging breadcrumb.

---

## 8. Mounting the Phase 11 router in the Member 1 gateway

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai_service.integration.ui_router import ui_router
from app.ai_service.integration.cors_headers import (
    UI_ALLOWED_METHODS,
    UI_ALLOWED_HEADERS,
    UI_EXPOSED_HEADERS,
    DEFAULT_FRONTEND_ORIGINS,
)

app = FastAPI()

# Merge the configured env-driven origins with the documented defaults
origins = sorted(set(DEFAULT_FRONTEND_ORIGINS) | set([o.strip() for o in settings.cors_origins_list]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=UI_ALLOWED_METHODS,
    allow_headers=UI_ALLOWED_HEADERS,
    expose_headers=UI_EXPOSED_HEADERS,
    max_age=600,
)

app.include_router(ui_router, prefix="/api/v1/ai")
```

---

## 9. Smoke-test script

```bash
#!/usr/bin/env bash
# Run from CI after the gateway deploy. Exits non-zero on any failure.
set -euo pipefail

BASE="${BASE_URL:-https://api.iob.enterprise.internal}"

echo "→ CORS allow-list check"
status=$(curl -sS -o /tmp/cors.json -w "%{http_code}" "$BASE/v1/ai/ui/cors-check")
if [[ "$status" != "200" ]]; then
  echo "CORS misconfigured:"
  cat /tmp/cors.json
  exit 1
fi

echo "→ DigitalTwin contract"
curl -sS "$BASE/v1/ai/ui/digital-twin/P-101A" \
  | python -c "import json,sys; d=json.load(sys.stdin); assert d['success'] and 'telemetry' in d['data'] and 'history' in d['data']; print('ok')"

echo "→ GraphRAG contract"
curl -sS -X POST "$BASE/v1/ai/ui/graphrag/query" \
  -H 'content-type: application/json' \
  -d '{"query":"vibration?","asset_id":"P-101A"}' \
  | python -c "import json,sys; d=json.load(sys.stdin); assert d['success'] and 'nodes' in d['data'] and 'edges' in d['data']; print('ok')"

echo "→ Explainability contract"
curl -sS "$BASE/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A" \
  | python -c "import json,sys; d=json.load(sys.stdin); assert d['success'] and 'features' in d['data'] and 'waterfall' in d['data']; print('ok')"

echo "→ All contracts green."
```
