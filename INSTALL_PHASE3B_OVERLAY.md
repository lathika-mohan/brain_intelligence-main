# Phase 3B — Joint Integration Worked Files · Install / Overlay Guide

Unzip into your **repo root** (the folder that contains the root `Dockerfile`
and `app/`), **preserving paths**. Every path mirrors the repo exactly so files
land in the right place. These are **additive** — no existing AI-engine source
file is overwritten.

## Contents

| File | Type | Action on your repo |
|---|---|---|
| `docker-compose.phase3.yml` | **NEW** | Add — unified multi-container stack (postgres, neo4j, qdrant, brain_intelligence, gateway) on shared `iob-net`. Source of truth for Phase 3. |
| `.env.phase3.example` | **NEW** | Add — Phase 3 networking/integration tunables (merge into `.env`, do not replace). |
| `.dockerignore` | **NEW** | Add — keeps the AI image lean (excludes frontend, node_modules, caches, secrets). |
| `iob-integration/gateway_app/Dockerfile.phase3` | **NEW** | Add — clean gateway image (fixes the malformed `COPY … 2>/dev/null \|\| true` line in the legacy Dockerfile). |
| `iob-integration/gateway_app/transparent_proxy.py` | **NEW** | Add — byte-identical transparent relay + shared `compare_payloads` comparator. |
| `iob-integration/gateway_app_patch/phase3_main_patch.diff` | **NEW** | Add — one-line env gate wiring the transparent relay into `gateway_app/main.py` (Member 2 to apply). |
| `scripts/phase3/run_phase3_smoke.sh` | **NEW** | Add — master orchestrator for all 13 tasks. |
| `scripts/phase3/phase3_status_table.py` | **NEW** | Add — Tasks 1 & 2 (Service Container Status Table). |
| `scripts/phase3/phase3_cross_container_probe.sh` | **NEW** | Add — Tasks 3 & 4 (internal DNS mesh proofs). |
| `scripts/phase3/phase3_byte_identical_relay.py` | **NEW** | Add — Tasks 5–7 (Payload Mutation Matrix). |
| `scripts/phase3/phase3_regression.py` | **NEW** | Add — Task 8 (Test Suite Progression Matrix). |
| `scripts/phase3/phase3_neo4j_audit.py` | **NEW** | Add — Task 9 (Neo4j dependency truth-tracking). |
| `scripts/phase3/phase3_log_scan.sh` | **NEW** | Add — Task 10 (runtime exception scan). |
| `scripts/phase3/phase3_latency_baseline.py` | **NEW** | Add — Tasks 11 & 12 (latency matrix). |
| `scripts/phase3/phase3_integration_report.py` | **NEW** | Add — Task 13 (Integration Summary Report + gate criteria). |
| `tests/test_phase3_byte_identical_relay.py` | **NEW** | Add — unit tests for the transparent relay comparator (7 tests, pure/no-network). |
| `PHASE3_ENGINEERING_EXECUTION_GUIDE_LATHIKA.md` | **NEW** | Add — the exhaustive execution guide. |
| `PHASE3_GATEWAY_TRANSPARENT_RELAY_AUDIT.md` | **NEW** | Add — documents the mutation defect + fix. |
| `PHASE3_WORKED_FILES_MANIFEST_PHASE3B.md` | **NEW** | Add — this manifest. |

## Why this shape?

Phase 3 is **verification + integration plumbing**, not AI-engine construction.
No `app/` business logic is modified — by design, editing a frozen Phase 0
contract here would be the exact failure this phase guards against. The only
"behaviour change" is the **gateway** transparent-relay gate, which is
additive and inert until `PHASE3_TRANSPARENT_RELAY=true` (and is Member 2's
to apply via the provided patch).

## Apply

```bash
# from your repo root
unzip phase3b_worked_files.zip

# merge Phase 3 tunables into your full .env
cp .env.example .env
cat .env.phase3.example >> .env        # append, do not overwrite

# (Member 2) arm the transparent relay in the gateway
cd iob-integration && git apply gateway_app_patch/phase3_main_patch.diff && cd ..

# verify the relay unit tests pass (pure, no containers needed)
PYTHONPATH=iob-integration python -m pytest tests/test_phase3_byte_identical_relay.py -q

# run the full Phase 3 gate
bash scripts/phase3/run_phase3_smoke.sh
```

## Roll-back

The compose, scripts, and Dockerfile are all new files — delete them to revert.
The gateway patch is reversible with `git apply -R iob-integration/gateway_app_patch/phase3_main_patch.diff`.
Nothing in `app/` is touched.
