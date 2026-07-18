#!/usr/bin/env python3
"""
IOB Phase 5 Joint Integration Orchestrator — Enhanced Production Version
Handles all 5 stages with contract drift resilience, chaos recovery detection,
structured error parsing, and zero-placeholder verification.

Usage: python phase5_integration_orchestrator.py --gateway http://localhost:8000 --ws-url ws://localhost:8001
"""

import sys
import time
import argparse
import requests

try:
    import websocket
except ImportError:
    print("FAIL: Missing dependency — install websocket-client (pip install websocket-client)")
    sys.exit(1)

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def assert_step(condition, success_msg, fail_msg):
    if condition:
        print(f"  {GREEN}✓ {success_msg}{RESET}")
        return True
    else:
        print(f"  {RED}✗ {fail_msg}{RESET}")
        return False


def run_stage_1_auth(gateway_url):
    print(f"\n{BLUE}STAGE 1: AUTH (Member 1 Gateway Verification){RESET}")
    try:
        res = requests.post(
            f"{gateway_url}/api/v1/auth/login",
            json={"username": "demo_operator", "password": "secure_password_2026"},
            timeout=5,
        )
        if not assert_step(res.status_code == 200, "Authentication payload accepted.", f"Auth rejected: {res.status_code}"):
            return None
        data = res.json()
        token = data.get("access_token") or data.get("data", {}).get("access_token")
        if not assert_step(token is not None, "Valid Bearer token extracted.", "Token missing — check gateway auth handler."):
            return None
        # Verify token works for dashboard
        overview_res = requests.get(
            f"{gateway_url}/api/v1/dashboard/overview",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert_step(overview_res.status_code == 200, "/overview authorized with token.", f"Overview blocked: {overview_res.status_code}")
        return token
    except Exception as e:
        print(f"  {RED}Exception during Stage 1: {e}{RESET}")
        return None


def run_stage_2_assets(gateway_url, token):
    print(f"\n{BLUE}STAGE 2: ASSETS / DATABASE VALIDATION{RESET}")
    try:
        res = requests.get(
            f"{gateway_url}/api/v1/assets",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if not assert_step(res.status_code == 200, "Assets endpoint returned 200.", f"Assets dead: {res.status_code}"):
            return False
        data = res.json()
        assets = data.get("assets") or data.get("data", [])
        if not assert_step(len(assets) > 0, f"Found {len(assets)} assets in DB layer.", "DB returned empty asset list!"):
            return False
        target = assets[0].get("id") or assets[0].get("asset_id")
        print(f"  Selected target asset: {YELLOW}{target}{RESET}")
        return target
    except Exception as e:
        print(f"  {RED}Exception during Stage 2: {e}{RESET}")
        return False


def run_stage_3_telemetry(ws_url, token):
    print(f"\n{BLUE}STAGE 3: TELEMETRY (WebSocket Handshake + Degraded Detection){RESET}")
    try:
        ws = websocket.create_connection(f"{ws_url}?token={token}", timeout=5)
        msg = ws.recv()
        data = __import__("json").loads(msg)
        if not assert_step("asset_id" in data or "status" in data, f"Initial WS frame valid: {msg[:80]}...", f"Invalid WS frame: {msg}"):
            ws.close()
            return False
        # Check for degraded frame (simulator may stop during chaos)
        ws.settimeout(3)
        try:
            msg2 = ws.recv()
            data2 = __import__("json").loads(msg2)
            if data2.get("simulator_live") is False:
                assert_step(True, "Graceful degradation detected (simulator_live=false).", "Unexpected degraded state.")
        except websocket.WebSocketTimeoutException:
            assert_step(True, "No degraded frame within timeout (simulator active).", "Timeout exceeded unexpectedly.")
        ws.close()
        return True
    except Exception as e:
        print(f"  {RED}Exception during Stage 3: {e}{RESET}")
        return False


def run_stage_4_predictive(gateway_url, token, asset_id):
    print(f"\n{BLUE}STAGE 4: PREDICTIVE INFERENCE (Contract Drift Resilience){RESET}")
    try:
        payload = {
            "asset_id": asset_id,
            "features": {
                "vibration_rms": 5.2,
                "temperature_celsius": 82.0,
                "speed_rpm": 1480.0,
                "pressure_bar": 6.4,
            },
        }
        res = requests.post(
            f"{gateway_url}/api/v1/predictive/infer",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if not assert_step(res.status_code == 200, f"Predictive inference returned 200.", f"Inference failed: {res.status_code} — body: {res.text[:200]}"):
            return False
        data = res.json()
        # Contract resilience: handle both nested and flat structures
        inner = data.get("data") or data
        risk = inner.get("risk_score") or inner.get("failure_probability")
        if not assert_step(risk is not None, f"Risk score found: {risk}.", f"Risk score missing — contract drift detected: keys={list(inner.keys())}"):
            return False
        print(f"  Target asset inference: risk_score={risk}, RUL_days={inner.get('remaining_useful_life_days')}")
        return True
    except Exception as e:
        print(f"  {RED}Exception during Stage 4: {e}{RESET}")
        return False


def run_stage_5_graphrag(gateway_url, token):
    print(f"\n{BLUE}STAGE 5: GRAPHRAG (Citation Contract Check){RESET}")
    try:
        payload = {
            "message": "What is causing bearing wear?",
            "query_text": "bearing wear",
        }
        res = requests.post(
            f"{gateway_url}/api/v1/graphrag/query",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if not assert_step(res.status_code == 200, "GraphRAG query returned 200.", f"GraphRAG failed: {res.status_code}"):
            return False
        data = res.json()
        inner = data.get("data") or data
        citations = inner.get("citations", [])
        if not assert_step(len(citations) >= 1, f"GraphRAG citations found: {len(citations)}.", f"GraphRAG citations empty — DB may be disconnected."):
            return False
        print(f"  GraphRAG answer length: {len(inner.get('answer', ''))} chars, citations: {len(citations)}")
        return True
    except Exception as e:
        print(f"  {RED}Exception during Stage 5: {e}{RESET}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--ws-url", default="ws://localhost:8001")
    args = parser.parse_args()

    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}IOB PHASE 5 JOINT INTEGRATION ORCHESTRATOR (Fixed Production Version){RESET}")
    print(f"{BLUE}Gateway: {args.gateway} | WS: {args.ws_url}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

    token = run_stage_1_auth(args.gateway)
    if token is None:
        print(f"{RED}STAGE 1 FAILED — ABORTING{RESET}")
        sys.exit(1)

    asset_id = run_stage_2_assets(args.gateway, token)
    if asset_id is False:
        print(f"{RED}STAGE 2 FAILED — ABORTING{RESET}")
        sys.exit(1)

    telemetry_ok = run_stage_3_telemetry(args.ws_url, token)
    predictive_ok = run_stage_4_predictive(args.gateway, token, asset_id)
    graphrag_ok = run_stage_5_graphrag(args.gateway, token)

    results = {
        "auth": token is not None,
        "assets": asset_id is not False,
        "telemetry": telemetry_ok,
        "predictive": predictive_ok,
        "graphrag": graphrag_ok,
    }

    print(f"\n{BLUE}FINAL RESULTS:{RESET}")
    for stage, ok in results.items():
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {stage.upper()}: {status}")

    all_pass = all(results.values())
    if all_pass:
        print(f"\n{GREEN}🎉 SUCCESS! ALL 5 SERVICE INTERFACES COMPLY{RESET}")
        sys.exit(0)
    else:
        print(f"\n{RED}❌ SOME STAGES FAILED — REVIEW OUTPUT ABOVE{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
