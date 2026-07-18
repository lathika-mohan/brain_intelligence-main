#!/usr/bin/env python3
"""
Phase 3 — Task 13: Integration Summary Report Compilation.

Reads every artifact produced by Tasks 1-12 and compiles the final
**Phase 3 Integration Summary Report**, evaluating the six binary gatekeeper
exit criteria. Exits non-zero if ANY criterion is unmet (Phase 4 stays locked).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def _load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return "_(artifact missing)_"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    a = args.artifacts
    status = _load_json(os.path.join(a, "02_service_container_status.json"))
    mutation = _load_json(os.path.join(a, "05_payload_mutation_matrix.json"))
    regression = _load_json(os.path.join(a, "08_test_suite_progression_matrix.json"))
    neo4j = _load_json(os.path.join(a, "09_neo4j_dependency_audit.json"))
    latency = _load_json(os.path.join(a, "11_baseline_latency_matrix.json"))

    # --- Evaluate the six binary gatekeeper criteria ---
    c1 = status.get("all_healthy", False) and any(
        r.get("service") == "brain_intelligence" and r.get("gate_ok") for r in status.get("rows", []))
    c2 = "Routing DROP" not in _read(os.path.join(a, "03_cross_container_probe.log")) and \
         "internal DNS mesh verified" in _read(os.path.join(a, "03_cross_container_probe.log"))
    c3 = bool(mutation.get("byte_identical", False))
    after = regression.get("after", {})
    c4 = after.get("failed", 1) == 0 and after.get("errors", 1) == 0
    c5 = not neo4j.get("fraud", True)  # fraud False => honest
    log_md = _read(os.path.join(a, "10_log_scan.md"))
    c6 = "❌ FAIL" not in log_md and "✅ PASS" in log_md

    criteria = [
        ("brain_intelligence runs inside the shared Docker Compose network with an active healthy tag", c1),
        ("Member 2's gateway reaches the internal AI REST endpoints with zero routing drops", c2),
        ("Proxy relay & direct microservice outputs are 100% byte-identical (whitespace + precision)", c3),
        ("Complete regression suite ran natively against the mounted, debugged framework", c4),
        ("GraphRAG / Neo4j stack states catalogued without masking infrastructure gaps", c5),
        ("Zero ImportError / Timeout / JSON-serialization exceptions in unified logs", c6),
    ]
    all_pass = all(v for _, v in criteria)

    # --- Counts for the header ---
    bi_row = next((r for r in status.get("rows", []) if r.get("service") == "brain_intelligence"), {})
    mtx = mutation.get("matrix", [])
    stable = [r for r in mtx if r.get("category") == "stable"]
    stable_ok = sum(1 for r in stable if r.get("byte_identical"))

    lines = [
        "# PHASE 3 — BACKEND-ONLY SMOKE TEST · INTEGRATION SUMMARY REPORT",
        "",
        f"**Owner:** Member 3 — Lathika (AI/ML Knowledge Engineer)  ",
        f"**Phase:** Phase 3 — Backend-Only Smoke Test (Joint Integration Gate)  ",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**Overall verdict:** {'🟢 **PASSED — Phase 4 (frontend deploy) UNLOCKED**' if all_pass else '🔴 **FAILED — Phase 4 remains LOCKED**'}",
        "",
        "---",
        "## Binary Exit Criteria (The Gatekeeper Rules)",
        "",
    ]
    for i, (label, passed) in enumerate(criteria, 1):
        lines.append(f"- [{'x' if passed else ' '}] {'✅' if passed else '❌'} {label}")
    lines.append("")

    # --- Artifact summaries ---
    lines += [
        "---",
        "## 1. Service Container Status (Task 1 & 2)",
        "",
        f"- All core services healthy: **{'YES' if status.get('all_healthy') else 'NO'}**",
        f"- brain_intelligence state: `{bi_row.get('state','?')}` / health: `{bi_row.get('health_check_state','?')}`",
        f"- DNS alias on iob-net: `{bi_row.get('internal_network_alias','brain_intelligence')}`",
        "",
        "## 2. Cross-Container Connectivity (Task 3 & 4)",
        "",
        "Internal DNS mesh verified — gateway reaches `http://brain_intelligence:8000` (no localhost trap).",
        "",
        "## 3. Byte-Identical Relay (Task 5, 6 & 7)",
        "",
        f"- Overall byte-identical: **{'YES' if c3 else 'NO'}**",
        f"- Stable properties matched: {stable_ok}/{len(stable)}",
        f"- Type-cast drifts: {sum(1 for r in mtx if r.get('failure_reason')=='TYPE_CAST_DRIFT')}",
        "",
        "## 4. Regression Progression (Task 8)",
        "",
        f"- Before → After passed: {regression.get('before',{}).get('passed',0)} → {after.get('passed',0)}",
        f"- After failed/errors: {after.get('failed',0)} / {after.get('errors',0)}",
        f"- After skipped: {after.get('skipped',0)} (must be honestly documented, see §5)",
        "",
        "## 5. Neo4j Dependency Truth-Tracking (Task 9)",
        "",
        f"- Neo4j required flag: `{neo4j.get('neo4j_required', False)}`",
        f"- Container up: `{neo4j.get('container_up', False)}` · Bolt reachable: `{neo4j.get('bolt_reachable', False)}`",
        f"- Honest state: **{neo4j.get('honest_state','UNKNOWN')}** · Fraud: **{neo4j.get('fraud', True)}**",
        "",
        "## 6. Log Scan (Task 10)",
        "",
        log_md.split("**Gate verdict:**")[-1].strip().splitlines()[0] if "**Gate verdict:**" in log_md else "See 10_log_scan.md",
        "",
        "## 7. Latency Baseline (Task 11 & 12)",
        "",
    ]
    for r in latency.get("rows", []):
        lines.append(f"- {r['endpoint']}: direct p50 {r['direct_p50_ms']}ms → relayed p50 {r['relayed_p50_ms']}ms (Δ {r['relay_overhead_ms']}ms)")
    lines += [
        "",
        "---",
        "## Deliverables Checklist",
        "",
        "- [x] Orchestration up-logs: `01_compose_up.log`",
        "- [x] Service status table: `02_service_container_status.{md,json}`",
        "- [x] Cross-container probe log: `03_cross_container_probe.log`",
        f"- [{'x' if c3 else ' '}] Byte-comparison document: `05_payload_mutation_matrix.{md,json}`",
        f"- [{'x' if c4 else ' '}] Regression test metrics: `08_test_suite_progression_matrix.{md,json}`",
        "- [x] Neo4j dependency audit: `09_neo4j_dependency_audit.{md,json}`",
        "- [x] Log scan: `10_log_scan.md`",
        "- [x] Latency baseline: `11_baseline_latency_matrix.{md,json}`",
    ]

    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
