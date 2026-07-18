#!/usr/bin/env python3
"""
Phase 3 — Tasks 11 & 12: Performance Baselines.

Builds the **Baseline Latency Tracking Matrix** for internal (direct AI
microservice) vs relayed (through gateway) request durations across the three
core AI surfaces: Predictive, GraphRAG, and Decision/XAI.

Reports p50 / p95 (ms) over N iterations. The relay must add only transport
overhead (a few ms); a large or erratic delta signals a proxy that is doing
work it should not (e.g. re-serialising, re-computing). Non-blocking by default
— flagged but does not halt the gate unless --strict.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone

ENDPOINTS = [
    ("Predictive", "/api/v1/predictive/infer",
     {"asset_id": "machine07", "component_id": "bearing",
      "features": {"vibration": 4.2, "temperature": 92.5}}),
    ("GraphRAG", "/api/v1/graphrag/query",
     {"query_text": "bearing maintenance procedure machine07", "asset_id": "machine07", "top_k": 3}),
    ("Decision/XAI", "/api/v1/predictive/machine07/explain", None),
]


def _call(base: str, path: str, body, timeout: float = 8.0) -> float:
    url = f"{base.rstrip('/')}{path}"
    if body is None:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    else:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read()
    return (time.perf_counter() - t0) * 1000.0


def percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--direct", required=True)
    ap.add_argument("--relayed", required=True)
    ap.add_argument("--iterations", type=int, default=8)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()

    rows = []
    for name, path, body in ENDPOINTS:
        d_vals, r_vals = [], []
        for _ in range(args.iterations):
            try: d_vals.append(_call(args.direct, path, body))
            except Exception: d_vals.append(float("nan"))
            try: r_vals.append(_call(args.relayed, path, body))
            except Exception: r_vals.append(float("nan"))
        d_clean = [v for v in d_vals if v == v]
        r_clean = [v for v in r_vals if v == v]
        d_p50 = percentile(d_clean, 50); d_p95 = percentile(d_clean, 95)
        r_p50 = percentile(r_clean, 50); r_p95 = percentile(r_clean, 95)
        overhead = (r_p50 - d_p50) if (d_p50 and r_p50) else 0.0
        rows.append({
            "endpoint": name, "path": path,
            "direct_p50_ms": round(d_p50, 2), "direct_p95_ms": round(d_p95, 2),
            "relayed_p50_ms": round(r_p50, 2), "relayed_p95_ms": round(r_p95, 2),
            "relay_overhead_ms": round(overhead, 2),
        })

    lines = [
        "# Baseline Latency Tracking Matrix (Phase 3 — Tasks 11 & 12)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Iterations per endpoint: {args.iterations}",
        "",
        "| Endpoint | Path | Direct p50 (ms) | Direct p95 (ms) | Relayed p50 (ms) | Relayed p95 (ms) | Relay Overhead (ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['endpoint']} | `{r['path']}` | {r['direct_p50_ms']} | {r['direct_p95_ms']} | "
            f"{r['relayed_p50_ms']} | {r['relayed_p95_ms']} | {r['relay_overhead_ms']} |"
        )
    lines += ["", "> Relay overhead should be small and stable. A large/erratic delta implies the",
              "> proxy is doing work it should not (re-serialising / re-computing)."]

    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(args.json, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, f, indent=2)

    print("\n".join(lines))

    if args.strict:
        bad = [r for r in rows if r["relay_overhead_ms"] > 50 or r["relayed_p50_ms"] == 0]
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
