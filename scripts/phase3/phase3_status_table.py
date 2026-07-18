#!/usr/bin/env python3
"""
Phase 3 — Task 1 & 2: Stack Orchestration & Container Health Verification.

Builds the **Service Container Status Table** by querying the live Compose stack
(`docker compose ps --format json`) and `docker inspect` for the real health
state. Writes a Markdown table + JSON artifact.

Columns produced (per the Phase 3 guide):
    Service | Status | Health Check State | Internal Network Alias

Exits non-zero if any of the four core services (postgres, gateway,
brain_intelligence, neo4j) is not (created/running + healthy where a healthcheck
is defined). This is the binary gate for Tasks 1 & 2.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

# Core services that MUST be up+healthy for the Phase 3 gate.
REQUIRED = {
    "postgres": "iob-postgres",
    "gateway": "iob-gateway",
    "brain_intelligence": "brain_intelligence",
    "neo4j": "iob-neo4j",
    "qdrant": "iob-qdrant",
}


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        return r.stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        print(f"[status_table] command failed {' '.join(cmd)}: {exc}", file=sys.stderr)
        return ""


def _compose_ps(compose_file: str) -> list[dict]:
    out = _run(["docker", "compose", "-f", compose_file, "ps", "--format", "json"])
    if not out.strip():
        return []
    items: list[dict] = []
    for line in out.strip().splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            items.extend(data)
        else:
            items.append(data)
    return items


def _inspect_health(container: str) -> str:
    out = _run(["docker", "inspect", "--format",
                "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}",
                container])
    if not out.strip():
        return "absent|absent"
    return out.strip()


def build_table(compose_file: str) -> tuple[list[dict], bool]:
    ps_rows = {r.get("Service") or r.get("service") or "": r for r in _compose_ps(compose_file)}
    rows: list[dict] = []
    all_healthy = True

    for service, expected_container in REQUIRED.items():
        ps = ps_rows.get(service, {})
        container = ps.get("Name") or ps.get("name") or expected_container
        state, health = _inspect_health(container).split("|", 1)
        status = ps.get("Status") or state or "absent"
        running = state in {"running"} and ("Up" in status or state == "running")
        healthy = health == "healthy" or health == "no-healthcheck"
        gate_ok = running and healthy
        if not gate_ok and service in {"postgres", "gateway", "brain_intelligence", "neo4j"}:
            all_healthy = False
        rows.append({
            "service": service,
            "container": container,
            "status": status if status else "absent",
            "state": state,
            "health_check_state": health,
            "internal_network_alias": service,  # DNS name on iob-net
            "ports": ps.get("Ports") or ps.get("Publishers") or "",
            "gate_ok": gate_ok,
        })
    return rows, all_healthy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compose-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()

    rows, all_healthy = build_table(args.compose_file)

    lines = [
        "# Service Container Status Table (Phase 3 — Task 1 & 2)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Compose file: `{args.compose_file}`",
        "",
        "| Service | Container | Status | Health Check State | Internal Network Alias (DNS) | Gate |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['service']}` | `{r['container']}` | {r['status']} | "
            f"**{r['health_check_state']}** | `{r['internal_network_alias']}` | "
            f"{'✅' if r['gate_ok'] else '❌'} |"
        )
    lines += ["", f"**All core services healthy: {'YES ✅' if all_healthy else 'NO ❌'}**"]

    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(args.json, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "all_healthy": all_healthy, "rows": rows}, f, indent=2)

    print("\n".join(lines))
    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
