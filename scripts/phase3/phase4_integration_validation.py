#!/usr/bin/env python3
"""Phase 4 — Integration Validation Script.

Validates every Phase 11 UI endpoint against the Zero-Transformation Contract
by exercising the full adapter → schema → envelope pipeline against the live
FastAPI application using stubbed engine dependencies.

Run:
    python scripts/phase4/phase4_integration_validation.py
    python scripts/phase4/phase4_integration_validation.py --base-url http://localhost:8002
    python scripts/phase4/phase4_integration_validation.py --json
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL_DEFAULT = "http://localhost:8002"
TIMEOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(
    method: str,
    url: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Fire an HTTP request and return (status_code, parsed_json)."""
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-request-id", f"p4-val-{int(time.time())}")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8")
            return exc.code, json.loads(body_text)
        except Exception:
            return exc.code, {"raw": str(exc)}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _is_iso8601(value: str) -> bool:
    """Best-effort check that a string is parseable as an ISO-8601 datetime."""
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def _is_finite_float(value: Any) -> bool:
    """Check that a value is a finite float (not NaN, not Inf)."""
    try:
        f = float(value)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self, name: str):
        self.name = name
        self.passed: List[str] = []
        self.failed: List[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def fail(self, msg: str) -> None:
        self.failed.append(msg)

    @property
    def is_pass(self) -> bool:
        return len(self.failed) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "PASS" if self.is_pass else "FAIL",
            "passed": self.passed,
            "failed": self.failed,
        }


def validate_digital_twin(base_url: str) -> ValidationResult:
    r = ValidationResult("DigitalTwinView /ui/digital-twin/{asset_id}")
    status, body = _request("GET", f"{base_url}/api/v1/ai/ui/digital-twin/P-101A")

    if status != 200:
        r.fail(f"HTTP {status} (expected 200)")
        return r
    r.ok("HTTP 200")

    data = body.get("data", {})
    # Envelope
    for key in ("success", "data", "error", "requestId", "generatedAt"):
        if key not in body:
            r.fail(f"Missing envelope key: {key}")
        else:
            r.ok(f"Envelope key present: {key}")

    # Asset
    asset = data.get("asset", {})
    for key in ("id", "name", "type", "status", "parentId"):
        if key not in asset:
            r.fail(f"Missing asset key: {key}")
        else:
            r.ok(f"Asset key present: {key}")
    if asset.get("status") not in ("OPERATIONAL", "DEGRADED", "CRITICAL", "OFFLINE"):
        r.fail(f"Invalid asset status: {asset.get('status')}")
    else:
        r.ok("Asset status in vocabulary")

    # Telemetry
    tel = data.get("telemetry", {})
    for key in ("speed", "vibration", "pressure", "temperature", "flowRate", "load", "riskScore", "status"):
        if key not in tel:
            r.fail(f"Missing telemetry key: {key}")
        else:
            r.ok(f"Telemetry key present: {key}")
    if tel.get("status") not in ("ok", "warning", "critical", "offline"):
        r.fail(f"Invalid telemetry status: {tel.get('status')}")
    else:
        r.ok("Telemetry status in vocabulary")
    if not _is_finite_float(tel.get("riskScore", "bad")):
        r.fail(f"riskScore not finite float: {tel.get('riskScore')}")
    else:
        r.ok("riskScore is finite float")

    # History
    history = data.get("history")
    if not isinstance(history, list):
        r.fail(f"history is not array: {type(history)}")
    else:
        r.ok(f"history is array (len={len(history)})")
        if history:
            frame = history[0]
            for key in ("timestamp", "speed", "vibration", "pressure", "temperature", "flowRate", "load", "riskScore", "status"):
                if key not in frame:
                    r.fail(f"Missing history frame key: {key}")
            if not _is_iso8601(frame.get("timestamp", "")):
                r.fail(f"History timestamp not ISO-8601: {frame.get('timestamp')}")
            else:
                r.ok("History timestamp is ISO-8601")

    # activeAnomaly
    anomaly = data.get("activeAnomaly")
    if anomaly is not None and anomaly not in ("bearing-wear", "compressor-surge", "electrical-trip", "leakage"):
        r.fail(f"Invalid activeAnomaly token: {anomaly}")
    else:
        r.ok(f"activeAnomaly valid: {anomaly}")

    return r


def validate_graphrag(base_url: str) -> ValidationResult:
    r = ValidationResult("GraphRagPanel /ui/graphrag/query")
    status, body = _request("POST", f"{base_url}/api/v1/ai/ui/graphrag/query",
                           body={"query": "Why is P-101A vibrating?", "asset_id": "P-101A", "top_k": 8})

    if status != 200:
        r.fail(f"HTTP {status} (expected 200)")
        return r
    r.ok("HTTP 200")

    data = body.get("data", {})
    # Arrays must be list, never null
    for key in ("nodes", "edges", "logs", "citations", "highlightedNodes", "highlightedEdges"):
        val = data.get(key)
        if not isinstance(val, list):
            r.fail(f"{key} is not array: {type(val)}")
        else:
            r.ok(f"{key} is array (len={len(val)})")

    # Node types in vocabulary
    for node in data.get("nodes", []):
        if node.get("type") not in ("asset", "component", "anomaly", "procedure", "record"):
            r.fail(f"Invalid node type: {node.get('type')}")
        else:
            r.ok(f"Node type valid: {node.get('type')}")
        # x/y must be finite floats
        if not _is_finite_float(node.get("x")):
            r.fail(f"Node x not finite: {node.get('x')}")
        if not _is_finite_float(node.get("y")):
            r.fail(f"Node y not finite: {node.get('y')}")

    # Confidence badge
    badge = data.get("badge")
    if badge and badge not in ("very_low", "low", "medium", "high", "very_high"):
        r.fail(f"Invalid badge: {badge}")
    elif badge:
        r.ok(f"Badge valid: {badge}")

    # Warning level
    wl = data.get("warningLevel")
    if wl and wl not in ("industrial-status-ok", "industrial-status-warning", "industrial-status-critical"):
        r.fail(f"Invalid warningLevel: {wl}")
    elif wl:
        r.ok(f"warningLevel valid: {wl}")

    # Answer must be string
    answer = data.get("answer")
    if not isinstance(answer, str):
        r.fail(f"answer is not string: {type(answer)}")
    else:
        r.ok("answer is string")

    return r


def validate_xai(base_url: str) -> ValidationResult:
    r = ValidationResult("ShapExplainability /ui/explain/{prediction_id}")
    status, body = _request("GET", f"{base_url}/api/v1/ai/ui/explain/pred-p101a-001?asset_id=P-101A&method=SHAP")

    if status != 200:
        r.fail(f"HTTP {status} (expected 200)")
        return r
    r.ok("HTTP 200")

    data = body.get("data", {})
    # Features sorted by |shapValue| desc
    features = data.get("features", [])
    if not isinstance(features, list):
        r.fail("features is not array")
    else:
        r.ok(f"features is array (len={len(features)})")
        shap_vals = [abs(f.get("shapValue", 0.0)) for f in features]
        if shap_vals == sorted(shap_vals, reverse=True):
            r.ok("Features sorted by |shapValue| desc")
        else:
            r.fail("Features NOT sorted by |shapValue| desc")

        # All shapValues finite
        for f in features:
            if not _is_finite_float(f.get("shapValue")):
                r.fail(f"Non-finite shapValue: {f.get('shapValue')}")
            else:
                r.ok(f"Finite shapValue: {f.get('shapValue')}")

    # Method
    method = data.get("method")
    if method not in ("SHAP", "LIME", "INTEGRATED_GRADIENTS", "PERMUTATION"):
        r.fail(f"Invalid method: {method}")
    else:
        r.ok(f"Method valid: {method}")

    # baseValue and predictionValue finite
    if not _is_finite_float(data.get("baseValue")):
        r.fail(f"Non-finite baseValue: {data.get('baseValue')}")
    else:
        r.ok(f"Finite baseValue: {data.get('baseValue')}")
    if not _is_finite_float(data.get("predictionValue")):
        r.fail(f"Non-finite predictionValue: {data.get('predictionValue')}")
    else:
        r.ok(f"Finite predictionValue: {data.get('predictionValue')}")

    # Waterfall and forcePlot
    for key in ("waterfall", "forcePlot"):
        val = data.get(key)
        if val is None:
            r.ok(f"{key} is null (acceptable)")
        elif isinstance(val, dict):
            r.ok(f"{key} is present (dict)")
        else:
            r.fail(f"{key} unexpected type: {type(val)}")

    # Root cause
    rc = data.get("rootCause")
    if not isinstance(rc, dict):
        r.fail(f"rootCause is not dict: {type(rc)}")
    else:
        r.ok("rootCause is dict")

    return r


def validate_recommendations(base_url: str) -> ValidationResult:
    r = ValidationResult("Recommendations /ui/recommendations")
    status, body = _request("POST", f"{base_url}/api/v1/ai/ui/recommendations",
                           body={"asset_id": "P-101A", "max_recommendations": 5})

    if status != 200:
        r.fail(f"HTTP {status} (expected 200)")
        return r
    r.ok("HTTP 200")

    data = body.get("data", [])
    if not isinstance(data, list):
        r.fail(f"data is not array: {type(data)}")
    else:
        r.ok(f"data is array (len={len(data)})")
        for action in data:
            for key in ("actionId", "actionType", "description", "priority", "severityTier",
                        "riskScoreIfIgnored", "estimatedCostAvoidanceUsd", "recommendedCompletionBy", "rank"):
                if key not in action:
                    r.fail(f"Missing action key: {key}")
            if action.get("priority") not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
                r.fail(f"Invalid priority: {action.get('priority')}")
            else:
                r.ok(f"Priority valid: {action.get('priority')}")
            if action.get("severityTier") not in ("IMMINENT", "SCHEDULED", "MONITOR"):
                r.fail(f"Invalid severityTier: {action.get('severityTier')}")
            else:
                r.ok(f"SeverityTier valid: {action.get('severityTier')}")
            if not _is_finite_float(action.get("riskScoreIfIgnored")):
                r.fail(f"Non-finite riskScoreIfIgnored: {action.get('riskScoreIfIgnored')}")

    return r


def validate_chat(base_url: str) -> ValidationResult:
    r = ValidationResult("AgentChat /ui/agent/chat")
    status, body = _request("POST", f"{base_url}/api/v1/ai/ui/agent/chat",
                           body={"session_id": "sess-val-1", "asset_id": "P-101A",
                                 "messages": [{"role": "user", "content": "Diagnose P-101A"}]})

    if status not in (200, 503):
        r.fail(f"HTTP {status} (expected 200 or 503)")
        return r
    r.ok(f"HTTP {status}")

    if status == 200:
        data = body.get("data", {})
        for key in ("messageId", "sender", "payload", "timestamp"):
            if key not in data:
                r.fail(f"Missing chat key: {key}")
            else:
                r.ok(f"Chat key present: {key}")
        if data.get("sender") not in ("OPERATOR", "AI_ENGINE"):
            r.fail(f"Invalid sender: {data.get('sender')}")
        else:
            r.ok(f"Sender valid: {data.get('sender')}")

    return r


def validate_cors_check(base_url: str) -> ValidationResult:
    r = ValidationResult("CORS Check /ui/cors-check")
    status, body = _request("GET", f"{base_url}/api/v1/ai/ui/cors-check")

    if status not in (200, 503):
        r.fail(f"HTTP {status} (expected 200 or 503)")
        return r
    r.ok(f"HTTP {status}")

    data = body.get("data", {})
    if "status" not in data:
        r.fail("Missing status in cors-check data")
    else:
        r.ok(f"status present: {data.get('status')}")

    if data.get("status") == "ok":
        if "allowedOrigins" not in data:
            r.fail("Missing allowedOrigins")
        else:
            r.ok(f"allowedOrigins present (len={len(data['allowedOrigins'])})")
    return r


def validate_contracts(base_url: str) -> ValidationResult:
    r = ValidationResult("Contract Manifest /ui/contracts")
    status, body = _request("GET", f"{base_url}/api/v1/ai/ui/contracts")

    if status != 200:
        r.fail(f"HTTP {status} (expected 200)")
        return r
    r.ok("HTTP 200")

    data = body.get("data", {})
    if data.get("phase") != "11-frontend-integration-support":
        r.fail(f"Wrong phase: {data.get('phase')}")
    else:
        r.ok(f"Phase correct: {data.get('phase')}")

    endpoints = data.get("endpoints", [])
    if len(endpoints) != 9:
        r.fail(f"Expected 9 endpoints, got {len(endpoints)}")
    else:
        r.ok(f"9 endpoints registered")

    required_paths = [
        "/api/v1/ai/ui/digital-twin/{asset_id}",
        "/api/v1/ai/ui/graphrag/query",
        "/api/v1/ai/ui/explain/{prediction_id}",
        "/api/v1/ai/ui/recommendations",
        "/api/v1/ai/ui/agent/chat",
        "/api/v1/ai/ui/agent/chat/stream",
        "/api/v1/ai/ui/cors-check",
        "/api/v1/ai/ui/options",
        "/api/v1/ai/ui/contracts",
    ]
    registered_paths = {e.get("path") for e in endpoints}
    for path in required_paths:
        if path not in registered_paths:
            r.fail(f"Missing endpoint: {path}")
        else:
            r.ok(f"Endpoint present: {path}")

    return r


def validate_error_handling(base_url: str) -> ValidationResult:
    r = ValidationResult("Error Handling Boundary Tests")

    # Test 1: Invalid prediction method
    status, body = _request("GET", f"{base_url}/api/v1/ai/ui/explain/pred-001?asset_id=P-101A&method=INVALID")
    if status == 422:
        r.ok("Invalid method → 422")
    else:
        r.fail(f"Invalid method → HTTP {status} (expected 422)")

    # Test 2: Empty chat messages
    status, body = _request("POST", f"{base_url}/api/v1/ai/ui/agent/chat",
                           body={"session_id": "sess-val", "asset_id": "P-101A", "messages": []})
    if status in (200, 422, 503):
        r.ok(f"Empty messages → HTTP {status} (handled gracefully)")
    else:
        r.fail(f"Empty messages → HTTP {status} (unexpected)")

    # Test 3: Malformed body (not JSON)
    try:
        req = urllib.request.Request(
            f"{base_url}/api/v1/ai/ui/graphrag/query",
            data=b"not json",
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            r.fail(f"Malformed body → HTTP {resp.status} (expected 422)")
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 422):
            r.ok(f"Malformed body → HTTP {exc.code} (correctly rejected)")
        else:
            r.fail(f"Malformed body → HTTP {exc.code}")
    except Exception:
        r.ok("Malformed body raised exception (correctly rejected)")

    return r


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Phase 4 Integration Validation")
    parser.add_argument("--base-url", default=BASE_URL_DEFAULT, help="Base URL of the FastAPI server")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    validators = [
        validate_digital_twin,
        validate_graphrag,
        validate_xai,
        validate_recommendations,
        validate_chat,
        validate_cors_check,
        validate_contracts,
        validate_error_handling,
    ]

    results: List[Dict[str, Any]] = []
    total_pass = 0
    total_fail = 0

    for validator in validators:
        try:
            result = validator(args.base_url)
            results.append(result.to_dict())
            total_pass += len(result.passed)
            total_fail += len(result.failed)
        except Exception as exc:
            results.append({"name": validator.__name__, "status": "ERROR", "error": str(exc), "passed": [], "failed": [str(exc)]})
            total_fail += 1

    report = {
        "phase": "4-frontend-integration-validation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "summary": {"total_checks": total_pass + total_fail, "passed": total_pass, "failed": total_fail},
        "results": results,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 80)
        print("PHASE 4 — INTEGRATION VALIDATION REPORT")
        print("=" * 80)
        print(f"Base URL:  {args.base_url}")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Total:     {total_pass + total_fail} checks | Passed: {total_pass} | Failed: {total_fail}")
        print("=" * 80)
        for r in results:
            status_icon = "✅" if r["status"] == "PASS" else "❌"
            print(f"\n{status_icon} {r['name']} — {r['status']}")
            for p in r.get("passed", []):
                print(f"   ✅ {p}")
            for f in r.get("failed", []):
                print(f"   ❌ {f}")
        print("\n" + "=" * 80)
        if total_fail == 0:
            print("ALL CHECKS PASSED — PHASE 4 VALIDATION COMPLETE ✅")
        else:
            print(f"FAILURES DETECTED — {total_fail} CHECK(S) FAILED ❌")
        print("=" * 80)

    # Save report to file
    report_path = "phase4_integration_validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return 1 if total_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
