# Phase 6 — Regression Testing

## What the runner does

Executes the exact Phase 6 commands, in order, and turns their output into a
pass/fail decision:

1. `pytest tests/test_phase11_ui_router_contract.py -v`  → **UI contract gate** (0 failures)
2. `pytest tests/test_phase3_byte_identical_relay.py -v` → **Relay gate** (0 failures)
3. `pytest <phase6,7,8,9,10,12> -q`                      → **Core AI suite gate** (no new regressions)

It parses pytest's terminal summary (reading the last summary line so test names
containing "passed"/"failed" don't skew the count), applies the gates, and writes
`phase6_regression_report.json` and `phase6_regression_report.md`. Exit code is 0
only when all gates pass — drop it into CI as-is.

## The baseline (core suite)

"Expected passing level" needs a reference point. On the first clean run:

```bash
python phase6_regression_runner.py --update-baseline
```

This writes `phase6_regression_baseline.json` with the current core-suite counts.
Later runs compare against it: the gate fails if failures increase **or** passes
drop below baseline. Without a baseline, the core gate passes only at 0 failures.

## Reading the report

`phase6_regression_report.md` lists each gate with ✅/❌ and the underlying counts
(`returncode`, `passed`, `failed`, `error`, `skipped`). `returncode` semantics:
`0` = all passed, `1` = failures present, `5` = no tests collected (treated as a
gate failure for a named file — usually a bad path or a deleted test).

## If a gate fails

- **UI contract ❌** — a Phase 4 wiring issue (prefix/response shape). Re-check the
  `/contracts` handler and mount prefix.
- **Relay ❌** — Phase 5 `compare_payloads` not importable where the test expects,
  or the test was deleted without updating group 2.
- **Core suite ❌** — inspect which of the six files regressed; the report shows
  current vs baseline counts.
