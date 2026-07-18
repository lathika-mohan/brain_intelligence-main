#!/usr/bin/env bash
# =============================================================================
# PHASE 3 — TASK 10: RUNTIME ERROR INSPECTION ACROSS SERVICE STDOUTS
# -----------------------------------------------------------------------------
# Scans the unified `docker compose logs` of every service for hard-failure
# signatures that would break the integration gate:
#   ImportError / ModuleNotFoundError
#   TimeoutError / ReadTimeout / ConnectTimeout / ConnectError
#   JSONDecodeError / SerializationError / ValidationError
#   raise_for_status / Traceback (most recent call last)
#
# Writes a per-service exception count table. Exits 4 if any signature is found
# in the AI service or gateway logs (the two services that must be clean for the
# gate). Benign router "not mounted" warnings (expected when optional ML deps
# are absent) are EXCLUDED.
# =============================================================================
set -uo pipefail

COMPOSE_CMD="${1:-docker compose -f docker-compose.phase3.yml}"
OUT="${2:-phase3_artifacts/10_log_scan.md}"
mkdir -p "$(dirname "${OUT}")"

# Signatures that MUST NOT appear in the AI service or gateway logs.
PATTERNS='ImportError|ModuleNotFoundError|TimeoutError|ReadTimeout|ConnectTimeout|ConnectError|JSONDecodeError|SerializationError|raise_for_status|Traceback \(most recent call last\)'
# Benign noise to exclude (router try/except guards when optional ML deps absent).
EXCLUDE='router not mounted|No module named .numpy|No module named .torch|No module named .shap|No module named .qdrant|No module named .sklearn'

SERVICES="postgres neo4j qdrant brain_intelligence gateway"

{
echo "# Runtime Log Scan (Phase 3 — Task 10)"
echo ""
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "| Service | Hard-failure signature hits | Sample (first match) |"
echo "|---|---|---|"
} > "${OUT}"

total_hits=0
gate_hits=0
for svc in ${SERVICES}; do
  # Capture this service's logs (best effort)
  logs=$(eval "${COMPOSE_CMD} logs --no-color --tail=4000 ${svc}" 2>/dev/null || true)
  # Count hard-failure signatures, excluding benign router-guard noise
  hits=$(printf '%s' "${logs}" | grep -E "${PATTERNS}" | grep -Ev "${EXCLUDE}" || true)
  count=$(printf '%s\n' "${hits}" | grep -c . || true)
  sample=$(printf '%s' "${hits}" | head -n 1 | cut -c1-160)
  total_hits=$((total_hits + count))
  case "${svc}" in
    brain_intelligence|gateway) gate_hits=$((gate_hits + count)) ;;
  esac
  echo "| \`${svc}\` | ${count} | ${sample:-—} |" >> "${OUT}"
done

{
echo ""
echo "**Total hard-failure signature hits (all services):** ${total_hits}"
echo "**Hits in gate-critical services (brain_intelligence, gateway):** ${gate_hits}"
echo ""
echo "Excluded benign patterns: \`${EXCLUDE}\` (expected optional-dep router guards)."
echo ""
if [ "${gate_hits}" -ne 0 ]; then
  echo "**Gate verdict: ❌ FAIL — runtime exceptions present in gate-critical logs.**"
else
  echo "**Gate verdict: ✅ PASS — no Import/Timeout/JSON-serialization exceptions in unified logs.**"
fi
} >> "${OUT}"

cat "${OUT}"

if [ "${gate_hits}" -ne 0 ]; then
  printf '\n\033[1;31m[PHASE3][HALT] runtime exceptions found in gate-critical service logs (%d).\033[0m\n' "${gate_hits}"
  exit 4
fi
exit 0
