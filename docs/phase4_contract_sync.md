# Phase 4 — Contract Synchronization

## What changed

`/api/v1/ai/ui/contracts` now returns a manifest **generated from the live
FastAPI route table** instead of a hand-maintained list. Two diagnostic
endpoints were added alongside it.

## Endpoints

| Method & Path | Returns |
|---------------|---------|
| `GET /api/v1/ai/ui/contracts` | Full manifest: service, version, route count, routes (with full mounted paths, methods, tags), routes grouped by tag, and an embedded OpenAPI sync flag. |
| `GET /api/v1/ai/ui/contracts/routes` | Flat list of every mounted path + methods. |
| `GET /api/v1/ai/ui/contracts/validate` | Structured drift report vs OpenAPI. |

## Wiring (choose one)

**A. Fix the existing handler** in `app/ai_service/integration/ui_router.py`
(see `_contracts_handler_snippet.py`): delete the old manifest-building body and
call `build_contract_manifest(request.app)`.

**B. Include the additive router.** In `ui_router.py`:

```python
from .contracts_router import router as contracts_router
router.include_router(contracts_router)   # inherits the /ui prefix
```

Only do one of these — if you both keep an old `/contracts` handler and include
the router, remove the old handler so exactly one owns the path.

## Guaranteeing no drift in CI

```bash
python phase4_contract_sync_verify.py       # exit 1 on drift
pytest tests/test_phase4_contract_sync.py -q
```

Optionally fail fast at startup by calling, in your app factory:

```python
from app.ai_service.integration.contracts_manifest import assert_in_sync
# ... after all routers are included ...
assert_in_sync(app)   # raises RuntimeError if manifest != OpenAPI
```

## Why this design

Any hand-written list of routes is a second source of truth and *will* drift.
By deriving the manifest from `app.routes`, "add an endpoint" and "update the
manifest" become one action, and the validator/test make any accidental
divergence a hard failure rather than a silent doc lie.
