#!/usr/bin/env bash
# =============================================================================
# PHASE 3 — TASKS 3 & 4: INTERNAL CROSS-CONTAINER CONNECTIVITY PROOFS
# -----------------------------------------------------------------------------
# Proves the gateway container resolves and reaches the AI service by its
# Compose service DNS name on the shared iob-net bridge network — NOT by
# localhost. This is the direct fix for the classic "localhost container
# isolation trap".
#
# Probes run FROM INSIDE the gateway container:
#   1. DNS resolution of `brain_intelligence` (getent / nslookup)
#   2. TCP reachability to brain_intelligence:8000
#   3. HTTP GET http://brain_intelligence:8000/health  (AI root identity)
#   4. HTTP GET http://brain_intelligence:8000/api/v1/predictive/health
#   5. Confirm AI_SERVICE_URL env inside the gateway points at the DNS name
#
# Exits 0 if every probe is clean; exits 3 on ANY routing drop.
# =============================================================================
set -uo pipefail

AI_CONTAINER="${1:-brain_intelligence}"
GW_CONTAINER="${2:-iob-gateway}"
AI_HOST_PORT="${3:-8002}"
GW_HOST_PORT="${4:-8000}"

pass=0; fail=0
section() { printf '\n\033[1;36m--- %s ---\033[0m\n' "$*"; }
check()  { if [ "$1" -eq 0 ]; then printf '  \033[1;32mPASS\033[0m %s\n' "$2"; pass=$((pass+1)); \
           else printf '  \033[1;31mFAIL\033[0m %s\n' "$2"; fail=$((fail+1)); fi; }

section "0. Containers present on shared network (iob-net)"
docker network inspect iob-net --format '{{range .Containers}}{{.Name}} {{end}}' \
  | tee /dev/stderr
for c in "${GW_CONTAINER}" "${AI_CONTAINER}"; do
  docker network inspect iob-net --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' \
    | grep -q "${c}" ; check $? "container '${c}' attached to iob-net"
done

section "1. DNS resolution of '${AI_CONTAINER}' from inside the gateway"
docker exec "${GW_CONTAINER}" sh -c "getent hosts ${AI_CONTAINER} || nslookup ${AI_CONTAINER} 2>/dev/null || cat /etc/hosts" \
  | tee /dev/stderr
docker exec "${GW_CONTAINER}" sh -c "getent hosts ${AI_CONTAINER} >/dev/null 2>&1" ; check $? "gateway resolves DNS name '${AI_CONTAINER}'"

section "2. AI_SERVICE_URL env inside the gateway (must be DNS name, NOT localhost)"
docker exec "${GW_CONTAINER}" sh -c 'echo "AI_SERVICE_URL=$AI_SERVICE_URL"' | tee /dev/stderr
docker exec "${GW_CONTAINER}" sh -c 'echo "$AI_SERVICE_URL" | grep -qv localhost' ; check $? "AI_SERVICE_URL does NOT point at localhost"
docker exec "${GW_CONTAINER}" sh -c 'echo "$AI_SERVICE_URL" | grep -q "brain_intelligence"' ; check $? "AI_SERVICE_URL targets the '${AI_CONTAINER}' DNS name"

section "3. TCP reachability ${AI_CONTAINER}:8000 from the gateway"
docker exec "${GW_CONTAINER}" sh -c "(echo > /dev/tcp/${AI_CONTAINER}/8000) >/dev/null 2>&1 || nc -zv ${AI_CONTAINER} 8000 2>&1" ; check $? "gateway can open TCP to ${AI_CONTAINER}:8000"

section "4. HTTP GET http://${AI_CONTAINER}:8000/health from inside the gateway (raw relay path)"
docker exec "${GW_CONTAINER}" sh -c "wget -qO- http://${AI_CONTAINER}:8000/health || curl -s http://${AI_CONTAINER}:8000/health" | tee /dev/stderr
docker exec "${GW_CONTAINER}" sh -c "wget -qO- http://${AI_CONTAINER}:8000/health >/dev/null 2>&1 || curl -fsS http://${AI_CONTAINER}:8000/health >/dev/null" ; check $? "gateway GETs AI /health over internal DNS"

section "5. HTTP GET /api/v1/predictive/health (the contract endpoint the gateway proxies)"
docker exec "${GW_CONTAINER}" sh -c "wget -qO- http://${AI_CONTAINER}:8000/api/v1/predictive/health || curl -s http://${AI_CONTAINER}:8000/api/v1/predictive/health" | tee /dev/stderr
docker exec "${GW_CONTAINER}" sh -c "wget -qO- http://${AI_CONTAINER}:8000/api/v1/predictive/health >/dev/null 2>&1 || curl -fsS http://${AI_CONTAINER}:8000/api/v1/predictive/health >/dev/null" ; check $? "gateway reaches /api/v1/predictive/health internally"

section "6. Reverse: AI container can resolve the gateway + postgres (full mesh sanity)"
for tgt in gateway:8000 postgres:5432 neo4j:7474 qdrant:6333; do
  name="${tgt%%:*}"
  docker exec "${AI_CONTAINER}" sh -c "getent hosts ${name} >/dev/null 2>&1" ; check $? "AI container resolves DNS name '${name}'"
done

section "RESULT"
printf 'passes=%d failures=%d\n' "${pass}" "${fail}"
if [ "${fail}" -ne 0 ]; then
  printf '\033[1;31m[PHASE3][HALT] cross-container routing drop detected (%d failure(s)).\033[0m\n' "${fail}"
  exit 3
fi
printf '\033[1;32m[PHASE3][OK] internal DNS mesh verified — no localhost trap.\033[0m\n'
exit 0
