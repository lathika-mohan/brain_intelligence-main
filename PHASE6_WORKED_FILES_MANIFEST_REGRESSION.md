# PHASE 6 — Regression Testing — Worked Files Manifest

**Goal:** Confirm the UI-layer fixes (Phase 4) and relay fix (Phase 5) didn't
break anything else, with an auditable, repeatable gate.

## Files in this delivery

| File | Type | Purpose |
|------|------|---------|
| `phase6_regression_runner.py` | **new** | Runs the three Phase 6 command groups in order, parses real pytest output, enforces the acceptance gates, writes `phase6_regression_report.{json,md}`. |
| `docs/phase6_regression.md` | **new** | How to run, how the baseline works, how to read the report. |

## Honest status of "execution"

I could **not** run your suite here: no network in my sandbox to install
pytest/fastapi/torch/xgboost/shap, and your nested source isn't retrievable
through GitHub's automated-access restrictions. So this phase ships the tool that
runs it *properly on your machine* — not fabricated pass counts. The tool's own
parsing and gate logic ARE verified (all parser/gate cases pass).

## Task-by-task mapping

- Run `pytest tests/test_phase11_ui_router_contract.py -v` → group 1, gate:
  0 failures/errors.
- Run `pytest tests/test_phase3_byte_identical_relay.py -v` → group 2, gate:
  0 failures/errors. (Should pass once Phase 5's `compare_payloads` is wired in.)
- Run the 6-file core suite `-q` → group 3, gate: no NEW regressions vs baseline.
- Verify → the runner prints a gate summary and exits non-zero if any gate fails.

## How to run

```bash
# from repo root, in your venv
python phase6_regression_runner.py --update-baseline   # first time: record expected core level
python phase6_regression_runner.py                     # thereafter: enforce no regressions
cat phase6_regression_report.md
```

## Note on continuity with Phases 4–5

- Phase 6's UI-contract check targets your existing
  `tests/test_phase11_ui_router_contract.py`. The Phase 4 delivery added
  `tests/test_phase4_contract_sync.py` — include it in your run if you want the
  new drift gate covered too.
- Phase 6's relay check targets `tests/test_phase3_byte_identical_relay.py`. If
  you took Phase 5's "restore" path, that test should now pass; if you took the
  "delete as superseded" path, remove it from group 2 or the runner will report
  "no tests collected" for that file.
