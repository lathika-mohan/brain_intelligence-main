# PHASE 7 — Final Verification & Cleanup — Worked Files

> This is a file list for the verification tooling. It is **not** a completion
> certificate or sign-off. Per the Phase 7 checklist, pytest results are the only
> acceptance criterion — see `phase6_regression_runner.py`.

## Files in this delivery

| File | Type | Purpose |
|------|------|---------|
| `phase7_final_verification.py` | **new** | Scope guard (protected modules untouched) + live endpoint/header/envelope/manifest checks. Prints findings; writes no certificate. |
| `docs/phase7_final_verification.md` | **new** | How to run and interpret. |

## Checklist coverage

| Checklist item | Where it's checked |
|----------------|--------------------|
| All UI contract tests pass | pytest (`phase6_regression_runner.py`) — acceptance authority |
| All required endpoints exist | `--live`: manifest route count + contracts endpoint responds |
| Headers are correct | `--live`: content-type check on responses |
| Response envelopes consistent | `--live`: `envelope_is_consistent` vs `APIResponse` fields |
| Contracts manifest accurate | `--live`: `validate_manifest_against_openapi` in-sync check |
| Core AI modules untouched | `--base <ref>`: **hard** scope guard (fails run on violation) |
| No mods to predictive/graphrag/decision/orchestration.service/models | scope guard patterns (both `graph_rag` and `graphrag` covered) |
| No completion certificate created | by design — this script writes none |

## Run

```bash
# scope guard — the strict, must-pass check
python phase7_final_verification.py --base origin/main      # or the sha/tag before your work

# live contract checks (inside the app venv)
python phase7_final_verification.py --base origin/main --live
```

Exit code is non-zero only on a scope violation. Everything else is report-only,
because acceptance belongs to pytest.

## Verified offline (in this delivery)

Scope-path matching (protected vs allowed, incl. `orchestration/service.py`
protected but `orchestration/routing.py` allowed) and envelope conformance logic
were unit-checked and pass. The live checks run against your app on your machine.
