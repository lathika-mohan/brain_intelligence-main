#!/usr/bin/env python3
"""
Phase 3 — Task 8: AI Contract Regression Execution.

Runs the full backend test suite and produces the **Test Suite Progression
Matrix** comparing Total / Passed / Failed / Errors / Skipped BEFORE and AFTER
the Phase 1 & 2 system corrections.

  AFTER  : runs `pytest` live in the project root (the mounted, debugged framework)
  BEFORE : parsed from a saved baseline log if present (default phase2_regression.log)

Exits non-zero if any test FAILED or ERRORED in the AFTER run (skips are
acceptable when honestly documented — see Task 9 for the Neo4j audit). This is
the binary gate for Task 8.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

SUMMARY_RE = re.compile(
    r"(?:(?P<deselected>\d+)\s+deselected,?\s+)?"
    r"(?P<n>\d+)\s+(passed|error|failed|skipped|warning)"
)


def parse_summary(text: str) -> dict[str, int]:
    """Parse pytest's trailing summary line(s) into counts."""
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "warnings": 0, "deselected": 0}
    if not text:
        return counts
    last = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("=") and ("passed" in s or "failed" in s or "error" in s or "skipped" in s or "deselected" in s or "no tests ran" in s):
            last = s
    if "no tests ran" in last:
        return counts
    for m in re.finditer(r"(\d+)\s+(passed|failed|error|skipped|warning|deselected)", last):
        n = int(m.group(1)); kind = m.group(2)
        key = "errors" if kind == "error" else kind + "s" if not kind.endswith("s") else kind
        counts[key] = counts.get(key, 0) + n
    counts["errors"] = counts.get("errors", 0)
    return counts


def parse_baseline(path: str) -> dict[str, int]:
    try:
        with open(path) as f:
            return parse_summary(f.read())
    except FileNotFoundError:
        return {}


def run_tests(root: str) -> tuple[dict[str, int], str]:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", "tests/"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=root, check=False, timeout=900)
    text = r.stdout + "\n" + r.stderr
    counts = parse_summary(text)
    counts["_exit_code"] = r.returncode
    return counts, text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--baseline", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()

    before = parse_baseline(args.baseline)
    after, raw = run_tests(args.project_root)

    total_before = before.get("passed", 0) + before.get("failed", 0) + before.get("errors", 0) + before.get("skipped", 0)
    total_after = after.get("passed", 0) + after.get("failed", 0) + after.get("errors", 0) + after.get("skipped", 0)

    lines = [
        "# Test Suite Progression Matrix (Phase 3 — Task 8)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Baseline log: `{args.baseline or '(none)'}`",
        "",
        "| Metric | Before (Phase 1 & 2 baseline) | After (Phase 3, live) | Delta |",
        "|---|---|---|---|",
        f"| Total collected | {total_before} | {total_after} | {total_after - total_before:+d} |",
        f"| Passed | {before.get('passed',0)} | {after.get('passed',0)} | {after.get('passed',0)-before.get('passed',0):+d} |",
        f"| Failed | {before.get('failed',0)} | {after.get('failed',0)} | {after.get('failed',0)-before.get('failed',0):+d} |",
        f"| Errors | {before.get('errors',0)} | {after.get('errors',0)} | {after.get('errors',0)-before.get('errors',0):+d} |",
        f"| Skipped | {before.get('skipped',0)} | {after.get('skipped',0)} | {after.get('skipped',0)-before.get('skipped',0):+d} |",
        "",
        f"**AFTER run exit code:** {after.get('_exit_code')}",
        f"**Gate verdict:** {'✅ PASS — no failures, no errors' if after.get('failed',0)==0 and after.get('errors',0)==0 else '❌ FAIL — failing tests or errors present'}",
        "",
        "> Skipped tests are acceptable ONLY when the skip reason is an honestly documented",
        "> missing infrastructure dependency (e.g. no live Neo4j). See Task 9 audit. Skips",
        "> must never be masked as passes.",
    ]

    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(args.json, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "before": before, "after": {k: v for k, v in after.items()},
                   "raw_tail": raw[-4000:]}, f, indent=2)

    print("\n".join(lines))
    # also dump the live log
    try:
        with open(os.path.join(args.project_root, "phase3_regression.log"), "w") as f:  # noqa: F821
            f.write(raw)
    except Exception:
        pass

    return 0 if after.get("failed", 0) == 0 and after.get("errors", 0) == 0 else 5


if __name__ == "__main__":
    import os  # noqa: E402
    sys.exit(main())
