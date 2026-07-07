# Phase 10 — AI Service Integration Notes

This package adds an isolated FastAPI AI module under:

```text
/api/v1/ai
```

It exposes the Phase 5–9 AI capabilities without creating any Next.js pages,
React components, or platform authentication logic.

## Files Added / Modified

### Added

- `app/ai_service/__init__.py`
- `app/ai_service/main_router.py`
- `app/ai_service/dependencies.py`
- `app/ai_service/exceptions.py`
- `app/ai_service/schemas.py`
- `app/ai_service/agent_runtime.py`
- `tests/test_phase10_ai_service.py`
- `README_INTEGRATION.md`

### Modified

- `app/api/v1/router.py` mounts the Phase 10 router under `/api/v1/ai/*`.
- `app/main.py` installs sanitized AI exception/validation handlers.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/ai/health` | AI module dependency/readiness summary |
| `POST` | `/api/v1/ai/query` | GraphRAG answer, citations, chunks, graph nodes/edges |
| `POST` | `/api/v1/ai/predict` | Predictive maintenance RUL, failure probability, anomaly flags |
| `GET` | `/api/v1/ai/explain/{prediction_id}` | SHAP/LIME explainability payload for a prediction |
| `POST` | `/api/v1/ai/recommend` | SOP-backed risk-ranked recommendations |
| `POST` | `/api/v1/ai/agent/chat` | Structured diagnostic agent states; supports `stream=true` NDJSON |

## Mounting in Member 1 Gateway

If Member 1 uses the existing application in `app/main.py`, no extra work is
needed; `app/api/v1/router.py` already includes `ai_router`.

For a separate enterprise gateway application:

```python
from fastapi import FastAPI
from app.ai_service.main_router import ai_router, ai_lifespan
from app.ai_service.exceptions import install_ai_exception_handlers

app = FastAPI(lifespan=ai_lifespan)
install_ai_exception_handlers(app)
app.include_router(ai_router, prefix="/api/v1")
```

A standalone app is also available:

```bash
uvicorn app.ai_service.main_router:create_ai_service_app --factory --reload --port 8000
```

## Dependency Injection

Routes use FastAPI `Depends` providers from `app/ai_service/dependencies.py`:

- `get_graphrag_engine()`
- `get_prediction_engine()`
- `get_xai_engine()`
- `get_decision_engine()`
- `get_ai_runtime()`

These providers can be overridden in tests or by Member 1 if the gateway needs
to supply pre-initialized service objects.

## Error Handling

`app/ai_service/exceptions.py` standardizes AI errors into sanitized JSON:

```json
{
  "success": false,
  "error_code": "AI_DEPENDENCY_UNAVAILABLE",
  "message": "A required AI dependency is temporarily unavailable.",
  "request_id": "...",
  "details": {"engine": "graphrag"}
}
```

Pydantic request errors are intercepted before ML/GraphRAG engines are called
and returned as `422 VALIDATION_ERROR`.

## Verification

Run the Phase 10 contract suite:

```bash
pytest tests/test_phase10_ai_service.py -q
```

The tests assert every endpoint response envelope, status code, OpenAPI path,
and validation error contract using FastAPI `TestClient` and dependency
overrides, so no live Neo4j/Qdrant/model artifacts are required.
