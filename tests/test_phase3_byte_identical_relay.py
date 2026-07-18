"""
Phase 3 — Byte-Identical Transparent Relay unit test.

Validates that `gateway_app.transparent_proxy` preserves an AI payload
byte-for-byte and correctly detects every class of mutation the Phase 3 gate
forbids: value warp, type-cast drift (float vs string timestamp), and field
addition/drop. This test is intentionally pure (no network) so it runs in CI
without live containers.

Run:
    pytest tests/test_phase3_byte_identical_relay.py -q
"""
from __future__ import annotations

import copy
import os
import sys

import pytest

# Locate the gateway_app package (iob-integration/) regardless of cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (
    os.path.abspath(os.path.join(_HERE, "..", "iob-integration")),
    os.path.abspath(os.path.join(_HERE, "..", "..", "iob-integration")),
):
    if os.path.isdir(cand) and cand not in sys.path:
        sys.path.insert(0, cand)

from gateway_app.transparent_proxy import compare_payloads  # type: ignore  # noqa: E402

# Canonical AI microservice predictive/infer payload (deterministic).
CANONICAL = {
    "success": True,
    "data": {
        "asset_id": "machine07",
        "component_id": "bearing",
        "risk_score": 0.8543,
        "failure_probability": 0.8543,
        "rul": {
            "value_days": 8.74,
            "lower_bound_days": 5.82,
            "upper_bound_days": 11.66,
            "confidence_level": 0.9,
            "model_name": "xgboost_rul_v1",
            "model_version": "1.0.0",
        },
        "failure_probability_detail": {
            "probability": 0.8543,
            "failure_mode_id": "failuremode-bearing-overheat",
            "failure_mode_label": "Bearing Overheat",
            "model_name": "xgboost_failure_classifier_v1",
        },
        "anomaly_flags": [
            {
                "sensor_id": "vib-sensor-1",
                "metric": "vibration_rms",
                "anomaly_score": -0.12,
                "is_anomalous": True,
                "severity": "HIGH",
            }
        ],
        "explanation_id": "9f2c1a7e-0000-0000-0000-000000000001",
        "inference_latency_ms": 18.4,
        "generated_at": "2026-07-17T10:00:00.000000+00:00",
    },
    "error": None,
    "request_id": "req-phase3-0001",
    "generated_at": "2026-07-17T10:00:00.000000+00:00",
    "risk_score": 0.8543,
}

VOLATILE = {"request_id", "generated_at", "explanation_id", "inference_latency_ms"}


def test_identical_payload_is_byte_identical():
    relayed = copy.deepcopy(CANONICAL)
    identical, matrix = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    assert identical is True
    assert all(r["byte_identical"] for r in matrix)


def test_value_warp_is_detected_and_halts():
    """The exact bug in the gateway: overwriting risk_score with a heuristic."""
    relayed = copy.deepcopy(CANONICAL)
    # Mirror the real gateway bug: it warps BOTH data.risk_score and top-level risk_score.
    relayed["data"]["risk_score"] = 0.5            # value warp
    relayed["data"]["failure_probability"] = 0.5
    relayed["risk_score"] = 0.5                     # top-level warp too
    identical, matrix = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    assert identical is False
    warped = [r for r in matrix if r["property"].endswith("risk_score")]
    assert len(warped) == 2
    assert all(r["failure_reason"] == "VALUE_MISMATCH" for r in warped)


def test_type_cast_drift_is_detected():
    """Float timestamp cast to string (or vice versa) must halt the gate."""
    relayed = copy.deepcopy(CANONICAL)
    # cast numeric precision field to string -> type drift
    relayed["data"]["rul"]["value_days"] = "8.74"
    identical, matrix = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    assert identical is False
    assert any(r["property"] == "data.rul.value_days" and r["failure_reason"] == "TYPE_CAST_DRIFT"
               for r in matrix)


def test_field_addition_is_detected():
    relayed = copy.deepcopy(CANONICAL)
    relayed["data"]["gateway_injected_field"] = True
    identical, matrix = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    assert identical is False
    assert any(r["property"] == "data.gateway_injected_field" and r["failure_reason"] == "FIELD_ADDED_OR_DROPPED"
               for r in matrix)


def test_field_drop_is_detected():
    relayed = copy.deepcopy(CANONICAL)
    del relayed["data"]["anomaly_flags"]
    identical, matrix = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    assert identical is False
    assert any(r["property"] == "data.anomaly_flags" and r["failure_reason"] == "FIELD_ADDED_OR_DROPPED"
               for r in matrix)


def test_volatile_value_drift_is_allowed_but_type_preserved():
    """request_id may differ per call, but must stay a string."""
    relayed = copy.deepcopy(CANONICAL)
    relayed["request_id"] = "req-phase3-9999"   # value differs
    identical, matrix = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    req_row = [r for r in matrix if r["property"] == "request_id"][0]
    assert req_row["byte_identical"] is True          # type preserved -> acceptable
    assert req_row["category"] == "volatile"
    assert identical is True

    # But a volatile field drifting TYPE must halt.
    relayed2 = copy.deepcopy(CANONICAL)
    relayed2["request_id"] = 12345                    # string -> int
    identical2, matrix2 = compare_payloads(CANONICAL, relayed2, volatile_keys=VOLATILE)
    assert identical2 is False
    assert [r for r in matrix2 if r["property"] == "request_id"][0]["failure_reason"] == "TYPE_CAST_DRIFT"


def test_numeric_precision_preserved():
    """0.8543 must not be rounded to 0.85 by the relay."""
    relayed = copy.deepcopy(CANONICAL)
    relayed["data"]["risk_score"] = 0.85
    identical, _ = compare_payloads(CANONICAL, relayed, volatile_keys=VOLATILE)
    assert identical is False
