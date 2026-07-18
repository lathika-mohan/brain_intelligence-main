#!/usr/bin/env python3
"""
Phase 3 — Tasks 5, 6 & 7: Byte-Identical Relay Verification & Schema Auditing.

This is the heart of Phase 3. It captures an AI payload TWICE in parallel,
from two independent transports, then proves they are byte-identical:

  DIRECT  : POST http://localhost:<AI_HOST_PORT>/api/v1/predictive/infer
            (straight into the brain_intelligence microservice)
  RELAYED : POST http://localhost:<GW_HOST_PORT>/api/v1/predictive/infer
            (through Member 2's gateway, which must act as a transparent proxy)

It then produces the **Payload Mutation Matrix Table** cross-examining, per
property: Direct Value (+type) | Gateway Value (+type) | Byte-Identical (YES/NO)
plus the failure reason on any drift.

ZERO-TOLERANCE: a single value mismatch, a single type-cast drift (float vs
string timestamp), or a single field added/dropped on a STABLE property is a
HARD FAIL (exit 2) and halts the gate. Volatile properties (request_id,
generated_at, explanation_id, inference_latency_ms, ISO timestamps) may differ
in value but MUST preserve type — a timestamp string drifting to a float is a
type-cast HALT.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Mapping
from concurrent.futures import ThreadPoolExecutor

import urllib.request
import urllib.error

# Import the shared comparator (same one the gateway self-test uses) so there is
# exactly one definition of "byte-identical" across the whole stack.
_HERE = os.path.dirname(os.path.abspath(__file__))
for candidate in (
    os.path.abspath(os.path.join(_HERE, "..", "..", "iob-integration")),
    os.path.abspath(os.path.join(_HERE, "..", "..", "..", "iob-integration")),
):
    if os.path.isdir(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)
try:
    from gateway_app.transparent_proxy import compare_payloads  # type: ignore
except Exception:  # pragma: no cover - fallback if run standalone w/o the module
    def compare_payloads(direct, relayed, volatile_keys=None):
        raise RuntimeError("transparent_proxy.compare_payloads unavailable; "
                           "ensure iob-integration/ is on sys.path")

VOLATILE_KEYS = {
    "request_id", "generated_at", "explanation_id", "inference_latency_ms",
    "detected_at", "timestamp", "last_updated", "predicted_window",
    "earliest", "latest", "most_likely", "last_trained_at",
}

# Deterministic input so the AI service produces a STABLE, comparable payload.
# vibration/temperature chosen inside the heuristic band so risk_score is fixed.
PREDICTIVE_BODY = {
    "asset_id": "machine07",
    "component_id": "bearing",
    "features": {"vibration": 4.2, "temperature": 92.5},
}


def _post(url: str, body: dict, timeout: float = 6.0) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json",
                                  "Accept": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _capture(direct_base: str, relayed_base: str) -> tuple[dict, dict, dict]:
    """Fire direct + relayed in parallel to minimise temporal divergence."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_dir = ex.submit(_post, f"{direct_base}/api/v1/predictive/infer", PREDICTIVE_BODY)
        f_rel = ex.submit(_post, f"{relayed_base}/api/v1/predictive/infer", PREDICTIVE_BODY)
        direct = f_dir.result()
        relayed = f_rel.result()
    return direct, relayed, PREDICTIVE_BODY


def _md_table(matrix: list[dict], direct: dict, relayed: dict) -> list[str]:
    lines = [
        "# Payload Mutation Matrix (Phase 3 — Tasks 5, 6 & 7)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Deterministic input (identical for both transports):",
        "```json",
        json.dumps(PREDICTIVE_BODY, indent=2),
        "```",
        "",
        "| # | Property | Direct Value | Direct Type | Gateway Value | Gateway Type | Byte-Identical | Reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(matrix, 1):
        d = json.dumps(row["direct_value"]) if not isinstance(row["direct_value"], str) else row["direct_value"]
        g = json.dumps(row["gateway_value"]) if not isinstance(row["gateway_value"], str) else row["gateway_value"]
        flag = "✅ YES" if row["byte_identical"] else "❌ NO"
        lines.append(
            f"| {i} | `{row['property']}` | {d} | `{row['direct_type']}` | "
            f"{g} | `{row['gateway_type']}` | {flag} | {row['failure_reason']} |"
        )
    identical = all(r["byte_identical"] for r in matrix)
    lines += [
        "",
        f"**Overall byte-identical verdict: {'✅ PASS — 100% identical' if identical else '❌ FAIL — drift detected'}**",
        "",
        "### Raw direct payload (AI microservice)",
        "```json",
        json.dumps(direct, indent=2),
        "```",
        "### Raw relayed payload (through gateway)",
        "```json",
        json.dumps(relayed, indent=2),
        "```",
    ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--direct", required=True, help="AI microservice base URL, e.g. http://localhost:8002")
    ap.add_argument("--relayed", required=True, help="Gateway base URL, e.g. http://localhost:8000")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()

    print(f"[byte_identical] direct  -> {args.direct}/api/v1/predictive/infer")
    print(f"[byte_identical] relayed -> {args.relayed}/api/v1/predictive/infer")

    try:
        direct, relayed, body = _capture(args.direct.rstrip("/"), args.relayed.rstrip("/"))
    except Exception as exc:
        print(f"[byte_identical][ERROR] capture failed: {exc}", file=sys.stderr)
        # Write a failure artifact so the report can record it.
        with open(args.out, "w") as f:
            f.write(f"# Payload Mutation Matrix\n\nCAPTURE FAILED: {exc}\n")
        with open(args.json, "w") as f:
            json.dump({"error": str(exc), "byte_identical": False}, f, indent=2)
        return 2

    identical, matrix = compare_payloads(direct, relayed, volatile_keys=VOLATILE_KEYS)

    with open(args.out, "w") as f:
        f.write("\n".join(_md_table(matrix, direct, relayed)) + "\n")
    with open(args.json, "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": body,
            "byte_identical": identical,
            "matrix": matrix,
            "direct_raw": direct,
            "relayed_raw": relayed,
        }, f, indent=2)

    print("\n".join(_md_table(matrix, direct, relayed)))

    # Categorise failures for a precise halt reason.
    stable_fails = [r for r in matrix if not r["byte_identical"] and r["category"] == "stable"]
    type_drifts = [r for r in matrix if r["failure_reason"] == "TYPE_CAST_DRIFT"]

    if type_drifts:
        props = ", ".join(r["property"] for r in type_drifts)
        print(f"\n[byte_identical][HALT] TYPE-CAST DRIFT on: {props}", file=sys.stderr)
    if stable_fails:
        props = ", ".join(f"{r['property']}({r['failure_reason']})" for r in stable_fails)
        print(f"\n[byte_identical][HALT] STABLE-PROPERTY DRIFT on: {props}", file=sys.stderr)

    return 0 if identical else 2


if __name__ == "__main__":
    sys.exit(main())
