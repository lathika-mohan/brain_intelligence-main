# PHASE 4 — Contracts Manifest & API Synchronization — Worked Files Manifest

**Goal:** Ensure the application describes itself correctly, and keep the
documented contract permanently in sync with the mounted implementation.

## Core design decision

The contract manifest is **derived at runtime from `app.routes`**, not
maintained by hand. This eliminates drift *by construction*: the thing that
documents the API and the thing that serves the API are the same object.

## Files in this delivery

| File | Type | Purpose |
|------|------|---------|
| `app/ai_service/integration/contracts_manifest.py` | **new** | Introspection engine: builds the manifest, resolves full mounted paths, validates against OpenAPI. |
| `app/ai_service/integration/contracts_router.py` | **new** | Additive `APIRouter` exposing `/contracts`, `/contracts/routes`, `/contracts/validate`. |
| `app/ai_service/integration/_contracts_handler_snippet.py` | **reference** | Copy-paste replacement for the stale `/contracts` handler already in `ui_router.py`. |
| `tests/test_phase4_contract_sync.py` | **new** | Pytest gate — fails CI on any manifest/OpenAPI drift. |
| `phase4_contract_sync_verify.py` | **new** | Standalone verifier (repo root); exit 1 on drift. |
| `docs/phase4_contract_sync.md` | **new** | Integration + usage notes. |

## Task-by-task mapping

- **Fix `/api/v1/ai/ui/contracts`** → replace the hand-maintained handler with
  `build_contract_manifest(request.app)` (snippet), or include `contracts_router`.
- **Report full mounted paths** → `list_mounted_paths()` resolves every
  `include_router` prefix and `Mount`; `route.path` is already fully qualified.
- **Add new endpoints** → `/contracts/routes` and `/contracts/validate`.
- **Validate against FastAPI OpenAPI** → `validate_manifest_against_openapi()`
  diffs served routes vs `app.openapi()["paths"]`.
- **Ensure every manifest route exists** → guaranteed; the manifest *is* the
  route table. Test `test_every_manifest_route_actually_exists` asserts it.
- **Remove path mismatches** → drift report surfaces `missing_in_openapi`,
  `missing_in_manifest`, and `method_mismatches`; there is no hand-list to mismatch.
- **Verify router mounting** → the verifier imports `app.main:app`; a bad mount
  fails import, and unmounted routers show as missing routes.

## How to run

```bash
# from repo root, in your normal venv (fastapi installed)
python phase4_contract_sync_verify.py     # -> exit 0 = in sync
pytest tests/test_phase4_contract_sync.py -q
```

## Two things you must confirm (I could not see them from outside)

1. **Mount prefix.** I assumed the UI router resolves to `/ui` under
   `/api/v1/ai`, giving `/api/v1/ai/ui/contracts`. If your prefix differs, the
   code still works — it derives paths — but adjust the wiring line accordingly.
2. **Response shape.** If your frontend expects a specific `/contracts` JSON
   schema (see `ui_schemas.py` / `phase2_ui_contract_manifest_snapshot.json`),
   map `build_contract_manifest()` output into that model, or set it as the
   handler's `response_model`. The generated payload is a superset of typical
   manifest fields.
