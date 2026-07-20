#!/usr/bin/env python3
"""
Phase 6 — Regression Runner
===========================

Runs the Phase 6 regression commands in order, parses each result, enforces the
acceptance gates, and writes machine- and human-readable reports. Nothing is
faked: every number comes from a real pytest process on your machine.

Usage (from repo root, in your normal venv):

    python phase6_regression_runner.py                 # run + verify
    python phase6_regression_runner.py --update-baseline   # record current core
                                                            # suite as the baseline

Gates
-----
1. UI contract   : tests/test_phase11_ui_router_contract.py       -> 0 failures/errors
2. Relay         : tests/test_phase3_byte_identical_relay.py       -> 0 failures/errors
3. Core AI suite : phase6/7/8/9/10/12                              -> no NEW regressions
                   vs phase6_regression_baseline.json (created on first
                   --update-baseline). Without a baseline it reports absolute
                   numbers and passes only if failures == 0.

Exit code 0 => all gates satisfied. Non-zero => a gate failed (CI-friendly).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

BASELINE_FILE = "phase6_regression_baseline.json"
REPORT_JSON = "phase6_regression_report.json"
REPORT_MD = "phase6_regression_report.md"

UI_CONTRACT = "tests/test_phase11_ui_router_contract.py"
RELAY = "tests/test_phase3_byte_identical_relay.py"
CORE_SUITE = [
    "tests/test_phase6_predictive.py",
    "tests/test_phase7_xai.py",
    "tests/test_phase8_decision.py",
    "tests/test_phase9_orchestration.py",
    "tests/test_phase10_ai_service.py",
    "tests/test_phase12_ml_models.py",
]

# Matches pytest's terminal summary counts, e.g.
#   "===== 5 passed, 1 skipped, 2 warnings in 0.42s ====="
#   "=== 2 failed, 3 passed, 1 error in 1.1s ==="
_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed|deselected)")


def parse_pytest_summary(output: str) -> dict:
    """Extract a normalized counts dict from pytest terminal output.

    Reads the LAST summary line so earlier occurrences of these words in test
    names or tracebacks don't skew the numbers.
    """
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0,
              "xfailed": 0, "xpassed": 0, "deselected": 0}
    summary_line = ""
    for line in output.splitlines():
        s = line.strip()
        if s.startswith("=") and s.endswith("=") and ("passed" in s or "failed" in s
                                                       or "error" in s or "no tests ran" in s):
            summary_line = s
    target = summary_line or output
    for num, kind in _COUNT_RE.findall(target):
        key = "error" if kind in ("error", "errors") else kind
        counts[key] = counts.get(key, 0) + int(num)
    return counts


def run_pytest(args: list, label: str) -> dict:
    cmd = [sys.executable, "-m", "pytest", *args]
    print(f"\n$ {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return {"label": label, "ran": False, "error": f"pytest not runnable: {exc}",
                "returncode": None, "counts": {}}
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # Echo pytest's own tail so the operator sees the real output too.
    print("\n".join(out.splitlines()[-12:]))
    counts = parse_pytest_summary(out)
    return {
        "label": label,
        "ran": True,
        "returncode": proc.returncode,     # 0 all passed, 1 failures, 5 none collected
        "counts": counts,
        "no_tests_collected": proc.returncode == 5,
    }


def _fail_count(counts: dict) -> int:
    return counts.get("failed", 0) + counts.get("error", 0)


def evaluate(results: dict, baseline: dict | None) -> tuple[bool, list]:
    gates = []
    overall_ok = True

    for key, human in [("ui_contract", "UI contract"), ("relay", "Relay")]:
        r = results[key]
        fails = _fail_count(r["counts"])
        ok = r["ran"] and r["returncode"] == 0 and fails == 0 and not r.get("no_tests_collected")
        gates.append({
            "gate": f"{human}: 0 failures",
            "ok": ok,
            "detail": (f"returncode={r['returncode']} counts={r['counts']}"
                       if r["ran"] else r.get("error", "did not run")),
        })
        overall_ok &= ok

    core = results["core_suite"]
    core_fails = _fail_count(core["counts"])
    if baseline and "core_suite_counts" in baseline:
        base_fails = _fail_count(baseline["core_suite_counts"])
        base_passed = baseline["core_suite_counts"].get("passed", 0)
        regressed = core_fails > base_fails or core["counts"].get("passed", 0) < base_passed
        ok = core["ran"] and not regressed and not core.get("no_tests_collected")
        detail = (f"current failures={core_fails} vs baseline={base_fails}; "
                  f"current passed={core['counts'].get('passed',0)} vs baseline={base_passed}")
    else:
        ok = core["ran"] and core_fails == 0 and not core.get("no_tests_collected")
        detail = (f"no baseline recorded; counts={core['counts']} "
                  "(pass requires 0 failures; run --update-baseline to set expected level)")
    gates.append({"gate": "Core AI suite: no new regressions", "ok": ok, "detail": detail})
    overall_ok &= ok

    return overall_ok, gates


def write_reports(results: dict, gates: list, overall_ok: bool) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_ok": overall_ok,
        "gates": gates,
        "results": results,
    }
    with open(REPORT_JSON, "w") as fh:
        json.dump(payload, fh, indent=2)

    lines = ["# Phase 6 — Regression Report", "",
             f"Generated: {payload['timestamp']}", "",
             f"**Overall: {'PASS ✅' if overall_ok else 'FAIL ❌'}**", "",
             "## Gates", ""]
    for g in gates:
        lines.append(f"- {'✅' if g['ok'] else '❌'} {g['gate']} — {g['detail']}")
    lines += ["", "## Raw counts", ""]
    for key, r in results.items():
        lines.append(f"- `{r['label']}`: ran={r['ran']} rc={r.get('returncode')} "
                     f"counts={r.get('counts')}")
    with open(REPORT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nReports written: {REPORT_JSON}, {REPORT_MD}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true",
                    help="Record the current core-suite counts as the accepted baseline.")
    args = ap.parse_args()

    if not os.path.isdir("tests"):
        print("[FATAL] run this from the repo root (no ./tests directory found).")
        return 2

    results = {
        "ui_contract": run_pytest([UI_CONTRACT, "-v"], UI_CONTRACT),
        "relay": run_pytest([RELAY, "-v"], RELAY),
        "core_suite": run_pytest([*CORE_SUITE, "-q"], "core_ai_suite"),
    }

    if args.update_baseline:
        with open(BASELINE_FILE, "w") as fh:
            json.dump({"core_suite_counts": results["core_suite"]["counts"],
                       "recorded": datetime.now(timezone.utc).isoformat()}, fh, indent=2)
        print(f"\nBaseline updated -> {BASELINE_FILE}: {results['core_suite']['counts']}")

    baseline = None
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE) as fh:
            baseline = json.load(fh)

    overall_ok, gates = evaluate(results, baseline)
    write_reports(results, gates, overall_ok)

    print("\n=== GATE SUMMARY ===")
    for g in gates:
        print(f"  {'PASS' if g['ok'] else 'FAIL'}  {g['gate']}")
    print("\n" + ("ALL GATES PASSED ✅" if overall_ok else "REGRESSION GATE FAILED ❌"))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
