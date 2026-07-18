#!/usr/bin/env bash
# Phase 4 — CORS Verification Script
# Verifies that the AI UI endpoints are reachable from the documented Next.js origins.

set -euo pipefail

BASE_URL="${1:-http://localhost:8002}"
ORIGIN="http://localhost:3000"

echo "============================================="
echo "PHASE 4 — CORS VERIFICATION"
echo "============================================="
echo "Base URL:  $BASE_URL"
echo "Origin:    $ORIGIN"
echo ""

# Test 1: CORS Check Endpoint
echo "[1] CORS Check Endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/ai/ui/cors-check")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "503" ]; then
    echo "    ✅ CORS check endpoint reachable (HTTP $HTTP_CODE)"
else
    echo "    ❌ CORS check endpoint unreachable (HTTP $HTTP_CODE)"
fi

# Test 2: OPTIONS Preflight
echo "[2] OPTIONS Preflight..."
PREFLIGHT_RESPONSE=$(curl -s -X OPTIONS "$BASE_URL/api/v1/ai/ui/options" \
    -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type,x-request-id" \
    -D - -o /dev/null)

if echo "$PREFLIGHT_RESPONSE" | grep -qi "access-control-allow-origin"; then
    echo "    ✅ Access-Control-Allow-Origin header present"
else
    echo "    ❌ Access-Control-Allow-Origin header missing"
fi

if echo "$PREFLIGHT_RESPONSE" | grep -qi "access-control-allow-methods"; then
    echo "    ✅ Access-Control-Allow-Methods header present"
else
    echo "    ❌ Access-Control-Allow-Methods header missing"
fi

if echo "$PREFLIGHT_RESPONSE" | grep -qi "access-control-allow-headers"; then
    echo "    ✅ Access-Control-Allow-Headers header present"
else
    echo "    ❌ Access-Control-Allow-Headers header missing"
fi

# Test 3: Actual GET request with Origin header
echo "[3] Actual GET request with Origin header..."
GET_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/ai/ui/contracts" \
    -H "Origin: $ORIGIN")
if [ "$GET_CODE" = "200" ]; then
    echo "    ✅ GET /ui/contracts with Origin header (HTTP $GET_CODE)"
else
    echo "    ❌ GET /ui/contracts with Origin header (HTTP $GET_CODE)"
fi

# Test 4: POST with Origin header
echo "[4] POST request with Origin header..."
POST_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ai/ui/graphrag/query" \
    -H "Origin: $ORIGIN" \
    -H "Content-Type: application/json" \
    -d '{"query":"test","asset_id":"P-101A"}')
if [ "$POST_CODE" = "200" ] || [ "$POST_CODE" = "503" ]; then
    echo "    ✅ POST /ui/graphrag/query with Origin header (HTTP $POST_CODE)"
else
    echo "    ❌ POST /ui/graphrag/query with Origin header (HTTP $POST_CODE)"
fi

# Test 5: Wrong origin rejection
echo "[5] Wrong Origin rejection..."
WRONG_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE_URL/api/v1/ai/ui/options" \
    -H "Origin: http://evil-site.com" \
    -H "Access-Control-Request-Method: POST")
# Should return 204 but without Access-Control-Allow-Origin for evil-site.com
echo "    Response code: $WRONG_CODE (should be 204 but without Allow-Origin for evil origin)"

echo ""
echo "============================================="
echo "CORS VERIFICATION COMPLETE"
echo "============================================="
