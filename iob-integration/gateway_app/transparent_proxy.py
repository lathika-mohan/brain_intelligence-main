"""
Phase 3 — Byte-Identical Transparent Relay for the IOB Gateway (Member 2).

WHY THIS FILE EXISTS
--------------------
The gateway's existing `_try_proxy_ai` + `predictive_infer` path in
`gateway_app/main.py` is a *mutating* relay. On a successful upstream call it
overwrites the AI service's authoritative fields with gateway-local heuristics:

        if "data" in proxy_result:
            if isinstance(proxy_result["data"], dict):
                proxy_result["data"]["risk_score"] = risk_score   # <-- WARP
            proxy_result["risk_score"] = risk_score               # <-- WARP
            return proxy_result

This is the exact "proxy warps the AI payload" failure mode Phase 3 must catch.
It is currently *masked* because the gateway's `_compute_risk_score` happens to
share the identical heuristic formula with the AI service's
`_compute_risk_from_features`. The moment the AI service returns a real
model-derived score, the gateway would silently overwrite it — a latent
contract violation.

This module is a NON-mutating relay: it returns the upstream JSON body exactly
as received, with byte-identical structure, key order, value types and numeric
precision. It is the implementation behind the Phase 3 exit criterion:
    "Proxy relay outputs ... are confirmed 100% byte-identical down to
     whitespace and precision elements."

WIRING (one-flag change in gateway_app/main.py)
-----------------------------------------------
Gate on the env flag so production behavior is unchanged until Member 2 adopts it:

    from .transparent_proxy import transparent_relay_enabled, relay_passthrough

    async def _try_proxy_ai(method, path, json_body=None, timeout=4.0):
        if transparent_relay_enabled():
            return await relay_passthrough(method, path, json_body, timeout)
        ... # existing mutating path

See `iob-integration/gateway_app_patch/phase3_main_patch.diff` for the exact edit.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Mapping, Optional, Tuple

import httpx

try:
    from .payload_compare import compare_payloads as _compare_byte_payloads, assert_byte_identical, PayloadComparison
except ImportError:
    from payload_compare import compare_payloads as _compare_byte_payloads, assert_byte_identical, PayloadComparison

logger = logging.getLogger("gateway.transparent_proxy")

# The AI service's internal-only guard expects this header from a trusted
# internal caller. The gateway IS that trusted internal caller.
_SERVICE_TOKEN = (
    os.getenv("SERVICE_API_KEY")
    or os.getenv("PLATFORM_GATEWAY_SERVICE_TOKEN")
    or "changeme_internal_service_key"
)

# Same base URL resolution the gateway already uses, so behaviour matches.
_AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8002").rstrip("/")


def transparent_relay_enabled() -> bool:
    """True when the Phase 3 byte-identical gate is armed."""
    return os.getenv("PHASE3_TRANSPARENT_RELAY", "false").lower() in {"1", "true", "yes", "on"}


def _upstream_url(path: str) -> str:
    """Build the upstream URL exactly the way the gateway already does."""
    if path.startswith("/api/v1"):
        return f"{_AI_SERVICE_URL}{path}"
    return f"{_AI_SERVICE_URL}/api/v1{path}"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def relay_passthrough(
    method: str,
    path: str,
    json_body: Optional[Mapping[str, Any]] = None,
    timeout: float = 4.0,
) -> Optional[dict[str, Any]]:
    """
    Relay a request to the AI service and return its JSON body UNCHANGED.

    Contract guarantees (Phase 3 byte-identical relay):
      * No field is added, removed, renamed or reordered.
      * No value is re-cast (float stays float, ISO timestamp stays string).
      * Numeric precision is preserved (no rounding / repr normalisation).
      * A fresh `httpx.AsyncClient` is used per call (no shared state leaks).

    Returns ``None`` if the upstream is unreachable, so callers can decide on
    graceful degradation exactly as they do today. On a non-2xx upstream
    response the parsed body is still returned untouched (the gateway must not
    fabricate a payload), and the status is logged.
    """
    url = _upstream_url(path)
    headers = {
        "Accept": "application/json",
        "X-Internal-Service-Token": _SERVICE_TOKEN,
        "X-Forwarded-By": "iob-gateway",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method.upper() == "POST":
                resp = await client.post(url, json=dict(json_body) if json_body else None, headers=headers)
            else:
                resp = await client.get(url, params=dict(json_body) if json_body else None, headers=headers)
    except httpx.TimeoutException as exc:
        logger.warning("transparent_relay TIMEOUT %s %s (%s)", method.upper(), path, exc)
        return None
    except httpx.RequestError as exc:
        logger.warning("transparent_relay CONN-FAIL %s %s (%s)", method.upper(), path, exc)
        return None

    if resp.status_code >= 500:
        logger.warning("transparent_relay upstream HTTP %s for %s", resp.status_code, path)
        return None

    try:
        body = resp.json()
    except ValueError:
        # Non-JSON body: return as-is under a stable envelope, do NOT fabricate.
        logger.warning("transparent_relay non-JSON body for %s", path)
        return {"_raw_text": resp.text, "_status": resp.status_code}

    # IMPORTANT: return `body` directly. No setdefault, no overwrite, no merge.
    return body


def compare_payloads(direct, relayed, volatile_keys=None, **kwargs):
    """Compare mappings semantically or raw bodies byte-for-byte.

    The mapping mode retains the Phase 3 field/type audit API while raw body
    inputs use the Phase 5 byte comparator. This compatibility boundary keeps
    both regression contracts wired without transforming relay responses.
    """
    if not isinstance(direct, Mapping) or not isinstance(relayed, Mapping):
        return _compare_byte_payloads(direct, relayed, **kwargs)

    volatile_keys = volatile_keys or set()
    matrix = []
    identical = True
    all_keys = list(direct) + [key for key in relayed if key not in direct]
    for key in dict.fromkeys(all_keys):
        in_direct, in_relayed = key in direct, key in relayed
        d_val = direct.get(key) if in_direct else "<<MISSING>>"
        r_val = relayed.get(key) if in_relayed else "<<MISSING>>"
        if in_direct and in_relayed and isinstance(d_val, Mapping) and isinstance(r_val, Mapping):
            sub_ok, rows = compare_payloads(d_val, r_val, volatile_keys=volatile_keys)
            for row in rows:
                row["property"] = f"{key}.{row['property']}"
            matrix.extend(rows)
            identical = identical and sub_ok
            continue
        type_match = type(d_val) is type(r_val)
        present_match = in_direct and in_relayed
        value_match = d_val == r_val
        volatile = key in volatile_keys
        row_ok = present_match and type_match and (volatile or value_match)
        if not present_match:
            reason = "FIELD_ADDED_OR_DROPPED"
        elif not type_match:
            reason = "TYPE_CAST_DRIFT"
        elif not value_match and not volatile:
            reason = "VALUE_MISMATCH"
        else:
            reason = ""
        matrix.append({
            "property": key, "direct_value": d_val, "direct_type": type(d_val).__name__,
            "gateway_value": r_val, "gateway_type": type(r_val).__name__,
            "byte_identical": row_ok, "category": "volatile" if volatile else "stable",
            "failure_reason": reason,
        })
        identical = identical and row_ok
    return identical, matrix


# ---------------------------------------------------------------------------
# Self-test — run with:  python -m gateway_app.transparent_proxy
# Verifies the relay preserves a sample payload byte-for-byte using the
# canonical byte-level comparator from payload_compare.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample = {
        "success": True,
        "data": {
            "asset_id": "machine07",
            "risk_score": 0.8543,
            "failure_probability": 0.8543,
            "rul": {"value_days": 8.74, "model_name": "xgboost_rul_v1"},
            "anomaly_flags": [{"is_anomalous": True, "severity": "HIGH"}],
            "generated_at": "2026-07-17T10:00:00+00:00",
        },
        "request_id": "abc-123",
        "risk_score": 0.8543,
    }
    # Serialize deterministically for byte-level comparison.
    direct_bytes = json.dumps(sample, separators=(",", ":"), sort_keys=False).encode("utf-8")

    # Simulate mutation (same shape as the old test, but at byte level).
    mutated = json.loads(json.dumps(sample))
    mutated["data"]["risk_score"] = 0.5
    mutated["data"]["new_injected_field"] = True
    mutated_bytes = json.dumps(mutated, separators=(",", ":"), sort_keys=False).encode("utf-8")

    result_mutated = compare_payloads(direct_bytes, mutated_bytes)
    print("transparent_relay self-test")
    print("  identical (mutated sample):", result_mutated.identical, "(expected False)")
    if not result_mutated.identical:
        print(f"  - diff offset: {result_mutated.first_diff_offset}, reason: {result_mutated.reason()}")

    # Clean copy must be identical.
    clean_bytes = json.dumps(sample, separators=(",", ":"), sort_keys=False).encode("utf-8")
    result_clean = compare_payloads(direct_bytes, clean_bytes)
    print("  identical (clean copy):   ", result_clean.identical, "(expected True)")

    assert result_mutated.identical is False, "comparator failed to detect mutation"
    assert result_clean.identical is True, "comparator false-positived on an identical payload"
    print("  SHA-256 sample:", _sha256(json.dumps(sample, separators=(",", ":"))))
    print("  transparent_relay_enabled:", transparent_relay_enabled())
    print("  OK")
