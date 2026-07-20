# Phase 7 — Final Verification & Cleanup

## Purpose

Confirm the Phase 4–6 work is complete **and within scope**, without producing a
sign-off document. Acceptance is decided by pytest; this script only surfaces
problems and hard-fails on scope violations.

## The scope guard (strict)

Proves none of the protected modules changed relative to a base ref:

- `app/predictive/*`
- `app/graph_rag/*` and `app/graphrag/*` (both spellings)
- `app/decision/*`
- `app/orchestration/service.py` (only this file; `routing.py`, `state.py`, etc. are allowed)
- `app/models/*`

```bash
python phase7_final_verification.py --base <ref-before-your-changes>
```

`<ref>` is whatever commit/branch/tag predates your Phase 4–6 work (e.g.
`origin/main`, a sha, or a tag). The run exits non-zero and lists offenders if any
protected path was touched. It also prints the allowed files that changed, for
transparency.

## The live checks (report-only)

Run inside the app venv so `app.main:app` imports:

```bash
python phase7_final_verification.py --base origin/main --live
```

- **Required endpoints exist** — route count + the `/api/v1/ai/ui/contracts`
  endpoint returns 200.
- **Headers correct** — response `content-type` is `application/json`.
- **Envelope consistent** — response bodies contain the required `APIResponse`
  fields (read from `app/models/common.py` when importable; otherwise a default
  `{success, data}` shape — adjust if your envelope differs).
- **Manifest accurate** — reuses Phase 4's `validate_manifest_against_openapi`.

These never fail the run on their own; they point you at what to fix, and the
pytest suite is the gate.

## Why no certificate

The Phase 7 checklist states the pytest results are the only acceptance criteria.
So there is intentionally no generated "ACCEPTED"/sign-off artifact — trusting a
document over the actual test run is exactly the drift this whole effort avoids.
```bash
python phase6_regression_runner.py    # the actual acceptance gate
```
