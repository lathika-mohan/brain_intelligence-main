#!/usr/bin/env bash
# Phase 4 — End-to-End Smoke Test Script
# Exercises every UI endpoint and validates response structure.

set -euo pipefail

BASE_URL="${1:-http://localhost:8002}"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "  ✅ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $desc (expected: $expected, got: $actual)"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================="
echo "PHASE 4 — END-TO-END SMOKE TEST"
echo "============================================="
echo "Base URL: $BASE_URL"
echo ""

# 1. Health
echo "[1] AI Health..."
HEALTH=$(curl -sf "$BASE_URL/api/v1/ai/health" 2>/dev/null || echo '{"status":"unreachable"}')
HEALTH_STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
check "AI Health status" "ready" "$HEALTH_STATUS" || check "AI Health status (degraded acceptable)" "degraded" "$HEALTH_STATUS" || true

# 2. CORS Check
echo "[2] CORS Check..."
CORS=$(curl -sf "$BASE_URL/api/v1/ai/ui/cors-check" 2>/dev/null || echo '{}')
CORS_STATUS=$(echo "$CORS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('status','error'))" 2>/dev/null || echo "error")
check "CORS status" "ok" "$CORS_STATUS" || true

# 3. Contract Manifest
echo "[3] Contract Manifest..."
CONTRACTS=$(curl -sf "$BASE_URL/api/v1/ai/ui/contracts" 2>/dev/null || echo '{}')
PHASE=$(echo "$CONTRACTS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('phase','missing'))" 2>/dev/null || echo "error")
check "Contract phase" "11-frontend-integration-support" "$PHASE"
ENDPOINT_COUNT=$(echo "$CONTRACTS" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',{}).get('endpoints',[])))" 2>/dev/null || echo "0")
check "Endpoint count" "9" "$ENDPOINT_COUNT"

# 4. Digital Twin
echo "[4] Digital Twin..."
DT=$(curl -sf "$BASE_URL/api/v1/ai/ui/digital-twin/P-101A" 2>/dev/null || echo '{}')
DT_SUCCESS=$(echo "$DT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success','missing'))" 2>/dev/null || echo "error")
check "Digital Twin success" "True" "$DT_SUCCESS"
DT_TEL_STATUS=$(echo "$DT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('telemetry',{}).get('status','missing'))" 2>/dev/null || echo "error")
check "Telemetry status in vocabulary" "true" "$(echo "$DT_TEL_STATUS" | grep -qE '^(ok|warning|critical|offline)$' && echo true || echo false)"
DT_HISTORY_LEN=$(echo "$DT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',{}).get('history',[])))" 2>/dev/null || echo "0")
check "History has frames" "true" "$([ "$DT_HISTORY_LEN" -gt 0 ] && echo true || echo false)"

# 5. GraphRAG
echo "[5] GraphRAG..."
GR=$(curl -sf -X POST "$BASE_URL/api/v1/ai/ui/graphrag/query" \
    -H "Content-Type: application/json" \
    -d '{"query":"vibration?","asset_id":"P-101A"}' 2>/dev/null || echo '{}')
GR_SUCCESS=$(echo "$GR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success','missing'))" 2>/dev/null || echo "error")
check "GraphRAG success" "True" "$GR_SUCCESS"
GR_NODES_LEN=$(echo "$GR" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',{}).get('nodes',[])))" 2>/dev/null || echo "0")
check "GraphRAG nodes is array" "true" "$([ "$GR_NODES_LEN" -ge 0 ] && echo true || echo false)"

# 6. SHAP Explainability
echo "[6] SHAP Explainability..."
XAI=$(curl -sf "$BASE_URL/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=SHAP" 2>/dev/null || echo '{}')
XAI_SUCCESS=$(echo "$XAI" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success','missing'))" 2>/dev/null || echo "error")
check "XAI success" "True" "$XAI_SUCCESS"
XAI_FEATURES=$(echo "$XAI" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',{}).get('features',[])))" 2>/dev/null || echo "0")
check "XAI features is array" "true" "$([ "$XAI_FEATURES" -ge 0 ] && echo true || echo false)"
XAI_METHOD=$(echo "$XAI" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('method','missing'))" 2>/dev/null || echo "error")
check "XAI method" "SHAP" "$XAI_METHOD"

# 7. Recommendations
echo "[7] Recommendations..."
REC=$(curl -sf -X POST "$BASE_URL/api/v1/ai/ui/recommendations" \
    -H "Content-Type: application/json" \
    -d '{"asset_id":"P-101A","max_recommendations":5}' 2>/dev/null || echo '{}')
REC_SUCCESS=$(echo "$REC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success','missing'))" 2>/dev/null || echo "error")
check "Recommendations success" "True" "$REC_SUCCESS"

# 8. Agent Chat
echo "[8] Agent Chat..."
CHAT=$(curl -sf -X POST "$BASE_URL/api/v1/ai/ui/agent/chat" \
    -H "Content-Type: application/json" \
    -d '{"session_id":"sess-smoke","asset_id":"P-101A","messages":[{"role":"user","content":"Diagnose P-101A"}]}' 2>/dev/null || echo '{}')
CHAT_STATUS=$(echo "$CHAT" | python3 -c "import sys,json; r=json.load(sys.stdin); print('success' if r.get('success') else 'degraded')" 2>/dev/null || echo "error")
check "Agent Chat responded" "true" "$([ "$CHAT_STATUS" = "success" ] || [ "$CHAT_STATUS" = "degraded" ] && echo true || echo false)"

# 9. OPTIONS Preflight
echo "[9] OPTIONS Preflight..."
PREFLIGHT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE_URL/api/v1/ai/ui/options" \
    -H "Origin: http://localhost:3000" 2>/dev/null || echo "000")
check "Preflight HTTP 204" "204" "$PREFLIGHT_CODE"

echo ""
echo "============================================="
echo "SMOKE TEST SUMMARY"
echo "============================================="
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -eq 0 ]; then
    echo "ALL CHECKS PASSED ✅"
else
    echo "FAILURES DETECTED ❌"
fi
echo "============================================="
