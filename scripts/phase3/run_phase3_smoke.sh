#!/usr/bin/env bash
# =============================================================================
# PHASE 3 — BACKEND-ONLY SMOKE TEST · MASTER ORCHESTRATOR
# Member 3 (Lathika — AI/ML Knowledge Engineer)
# -----------------------------------------------------------------------------
# Runs all 13 Phase 3 tasks in order, each producing an artifact under
# ./phase3_artifacts/. Any task that hits a hard failure (network drop,
# payload mutation, type-cast drift, runtime exception) exits non-zero and
# HALTS the gate — Phase 4 (frontend deploy) cannot be unlocked until clean.
#
#   exit 0  -> all gates green, Phase 3 PASSED
#   exit 2  -> payload mutation / type-cast drift detected (RELAY HALT)
#   exit 3  -> cross-container routing drop (NETWORK HALT)
#   exit 4  -> runtime exception in unified logs (LOG HALT)
#   exit 5  -> regression regression (failing tests)
#   exit 6  -> Neo4j dependency fraud (masked infrastructure gap)
#   exit 1  -> other / preflight failure
# =============================================================================
set -euo pipefail

# ---- Paths ------------------------------------------------------------------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${HERE}/../.." && pwd)"        # repo root (has Dockerfile)
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.phase3.yml"
ARTIFACTS="${PROJECT_ROOT}/phase3_artifacts"
export PHASE3_ARTIFACTS="${ARTIFACTS}"
mkdir -p "${ARTIFACTS}"

# ---- Config (override via env) ---------------------------------------------
COMPOSE_CMD=${COMPOSE_CMD:-"docker compose -f ${COMPOSE_FILE}"}
AI_HOST_PORT=${AI_HOST_PORT:-8002}        # brain_intelligence on host
GW_HOST_PORT=${GW_HOST_PORT:-8000}        # gateway on host
AI_CONTAINER=${AI_CONTAINER:-brain_intelligence}
GW_CONTAINER=${GW_CONTAINER:-iob-gateway}

log() { printf '\n\033[1;36m[PHASE3] %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m[PHASE3][OK] %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m[PHASE3][HALT] %s\033[0m\n' "$*"; exit "${2:-1}"; }

log "Phase 3 — Backend-Only Smoke Test starting"
log "project root : ${PROJECT_ROOT}"
log "compose file : ${COMPOSE_FILE}"
log "artifacts dir: ${ARTIFACTS}"

# ---- Preflight --------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not found on PATH" 1
[ -f "${COMPOSE_FILE}" ] || die "compose file missing: ${COMPOSE_FILE}" 1

# ---- Tasks 1 & 2: stack orchestration + container health --------------------
log "TASKS 1-2 — Stack orchestration & container health verification"
${COMPOSE_CMD} up --build -d 2>&1 | tee "${ARTIFACTS}/01_compose_up.log"
python3 "${HERE}/phase3_status_table.py" \
  --compose-file "${COMPOSE_FILE}" \
  --out "${ARTIFACTS}/02_service_container_status.md" \
  --json "${ARTIFACTS}/02_service_container_status.json" \
  || die "one or more containers failed to reach healthy" 1
ok "all containers healthy"

# ---- Tasks 3 & 4: internal cross-container connectivity proofs --------------
log "TASKS 3-4 — Internal cross-container connectivity proofs"
bash "${HERE}/phase3_cross_container_probe.sh" \
  "${AI_CONTAINER}" "${GW_CONTAINER}" "${AI_HOST_PORT}" "${GW_HOST_PORT}" \
  | tee "${ARTIFACTS}/03_cross_container_probe.log"
# probe script exits non-zero on a routing drop
probe_rc=${PIPESTATUS[0]:-0}
[ "${probe_rc}" -eq 0 ] || die "cross-container routing DROP detected (AI_SERVICE_URL unreachable)" 3
ok "internal DNS routing verified (no localhost trap)"

# ---- Tasks 5,6,7: byte-identical relay verification & schema auditing -------
log "TASKS 5-7 — Byte-identical relay verification & payload mutation matrix"
python3 "${HERE}/phase3_byte_identical_relay.py" \
  --direct "http://localhost:${AI_HOST_PORT}" \
  --relayed "http://localhost:${GW_HOST_PORT}" \
  --out "${ARTIFACTS}/05_payload_mutation_matrix.md" \
  --json "${ARTIFACTS}/05_payload_mutation_matrix.json" \
  || die "PAYLOAD MUTATION or TYPE-CAST DRIFT detected — byte-identical relay FAILED" 2
ok "relay is 100% byte-identical (no warp / drop / strip / reorder)"

# ---- Task 8: AI contract regression execution -------------------------------
log "TASK 8 — AI contract regression execution"
python3 "${HERE}/phase3_regression.py" \
  --project-root "${PROJECT_ROOT}" \
  --baseline "${PROJECT_ROOT}/phase2_regression.log" \
  --out "${ARTIFACTS}/08_test_suite_progression_matrix.md" \
  --json "${ARTIFACTS}/08_test_suite_progression_matrix.json" \
  || die "regression suite has failing tests" 5
ok "regression suite green"

# ---- Task 9: transparent Neo4j dependency auditing --------------------------
log "TASK 9 — Transparent Neo4j dependency auditing"
python3 "${HERE}/phase3_neo4j_audit.py" \
  --ai-container "${AI_CONTAINER}" \
  --neo4j-container iob-neo4j \
  --out "${ARTIFACTS}/09_neo4j_dependency_audit.md" \
  --json "${ARTIFACTS}/09_neo4j_dependency_audit.json" \
  || die "Neo4j dependency FRAUD — infrastructure gap masked as pass" 6
ok "GraphRAG/Neo4j state honestly catalogued"

# ---- Task 10: log scan for runtime exceptions -------------------------------
log "TASK 10 — Runtime error inspection across service stdouts"
bash "${HERE}/phase3_log_scan.sh" "${COMPOSE_CMD}" "${ARTIFACTS}/10_log_scan.md" \
  || die "runtime ImportError / Timeout / JSON-serialization exception in logs" 4
ok "unified logs clean of Import/Timeout/Serialization exceptions"

# ---- Tasks 11 & 12: performance baselines -----------------------------------
log "TASKS 11-12 — Baseline latency tracking"
python3 "${HERE}/phase3_latency_baseline.py" \
  --direct "http://localhost:${AI_HOST_PORT}" \
  --relayed "http://localhost:${GW_HOST_PORT}" \
  --out "${ARTIFACTS}/11_baseline_latency_matrix.md" \
  --json "${ARTIFACTS}/11_baseline_latency_matrix.json" \
  || ok "latency captured (relay overhead above threshold flagged but non-blocking)"
ok "latency baseline captured"

# ---- Task 13: integration summary report compilation ------------------------
log "TASK 13 — Integration summary report compilation"
python3 "${HERE}/phase3_integration_report.py" \
  --artifacts "${ARTIFACTS}" \
  --out "${PROJECT_ROOT}/PHASE3_INTEGRATION_SUMMARY_REPORT.md" \
  || die "exit criteria NOT met" 1

ok "============================================================"
ok "PHASE 3 PASSED — all gatekeeper rules satisfied. Phase 4 unlocked."
ok "Report: ${PROJECT_ROOT}/PHASE3_INTEGRATION_SUMMARY_REPORT.md"
ok "============================================================"
