"""Golden sample payloads used by the Phase 11 contract tests.

These fixtures are *the* reference for what each UI endpoint must emit.
Any change here is a breaking change for Member 4 — the test suite will
fail loudly and the AI_PAYLOAD_SPEC.md playbook must be updated.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

NOW = datetime(2026, 7, 7, 7, 15, tzinfo=timezone.utc)


def _reading(metric: str, value: float, unit: str = "") -> Dict[str, Any]:
    return {"sensor_id": f"sns-{metric}", "metric": metric, "value": value, "unit": unit, "quality": 0.99}


def sample_telemetry_frame(asset_id: str = "P-101A", offset_minutes: int = 0) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "asset_id": asset_id,
        "component_id": "bearing-de",
        "timestamp": (NOW + timedelta(minutes=offset_minutes)).isoformat(),
        "operating_mode": "RUNNING",
        "readings": [
            _reading("bearing_temp", 82.0, "C"),
            _reading("vibration_rms", 5.2, "mm/s"),
            _reading("rpm", 1480.0, "rpm"),
            _reading("pressure", 6.4, "bar"),
            _reading("flow_rate", 240.0, "L/m"),
            _reading("load_kw", 312.0, "kW"),
        ],
        "metadata": {},
    }


def sample_telemetry_history(asset_id: str = "P-101A", n: int = 24) -> List[Dict[str, Any]]:
    return [sample_telemetry_frame(asset_id, offset_minutes=5 * i) for i in range(n)]


SAMPLE_DIGITAL_TWIN_PAYLOAD: Dict[str, Any] = {
    "asset": {
        "id": "P-101A",
        "name": "P-101A",
        "type": "PUMP",
        "status": "OPERATIONAL",
        "parentId": None,
    },
    "telemetry": {
        "speed": 1480.0,
        "vibration": 5.2,
        "pressure": 6.4,
        "temperature": 82.0,
        "flowRate": 240.0,
        "load": 312.0,
        "riskScore": 64.0,
        "status": "warning",
    },
    "history": [],
    "activeAnomaly": "bearing-wear",
    "generated_at": NOW.isoformat(),
}


SAMPLE_GRAPH_NODES: List[Dict[str, Any]] = [
    {"id": "asset:P-101A", "label": "P-101A", "type": "Asset"},
    {"id": "fm:bearing", "label": "Bearing Wear", "type": "FailureMode"},
    {"id": "sop:SOP-MECH-042", "label": "SOP-MECH-042", "type": "SOP"},
]


SAMPLE_GRAPH_EDGES: List[Dict[str, Any]] = [
    {"source": "asset:P-101A", "target": "fm:bearing", "relationship": "HAS_FAILURE_MODE", "weight": 1.0},
    {"source": "fm:bearing", "target": "sop:SOP-MECH-042", "relationship": "MITIGATED_BY", "weight": 1.0},
]


SAMPLE_SHAP_FEATURES: List[Dict[str, Any]] = [
    {"feature_name": "vibration_rms", "impact_weight": 0.42, "feature_value": 9.5, "rank": 1},
    {"feature_name": "bearing_temp", "impact_weight": 0.31, "feature_value": 82.0, "rank": 2},
    {"feature_name": "rpm", "impact_weight": -0.05, "feature_value": 1480.0, "rank": 3},
    {"feature_name": "pressure", "impact_weight": 0.02, "feature_value": 6.4, "rank": 4},
]


SAMPLE_UI_SHAP_PAYLOAD: Dict[str, Any] = {
    "predictionId": "pred-p101a-001",
    "assetId": "P-101A",
    "method": "SHAP",
    "scope": "LOCAL",
    "baseValue": 0.31,
    "predictionValue": 0.72,
    "features": [
        {"name": "vibration_rms", "value": "9.5mm/s", "shapValue": 0.42, "desc": "SHAP contribution +0.42 (rank 1, observed 9.5mm/s)"},
        {"name": "bearing_temp", "value": "82°C", "shapValue": 0.31, "desc": "SHAP contribution +0.31 (rank 2, observed 82°C)"},
        {"name": "rpm", "value": "1480RPM", "shapValue": -0.05, "desc": "SHAP contribution -0.05 (rank 3, observed 1480RPM)"},
        {"name": "pressure", "value": "6.4bar", "shapValue": 0.02, "desc": "SHAP contribution +0.02 (rank 4, observed 6.4bar)"},
    ],
    "confidenceMatrix": [{"label": "SHAP convergence", "confidence": 0.95}],
    "rootCause": {
        "headline": "Vibration dominated alert",
        "narrative": "Elevated vibration is consistent with bearing wear.",
        "contributingFailureModes": ["fm-bearing-wear"],
    },
    "generatedAt": NOW.isoformat(),
}


SAMPLE_UI_PREDICTION: Dict[str, Any] = {
    "id": "pred-p101a-001",
    "assetId": "P-101A",
    "remainingUsefulLifeDays": 5.2,
    "failureProbability": 0.64,
    "inferredFaultMechanism": "Bearing wear",
}


SAMPLE_UI_CHAT_MESSAGE: Dict[str, Any] = {
    "messageId": "msg-sess-maint-001",
    "sender": "AI_ENGINE",
    "payload": "P-101A shows a likely bearing lubrication issue.",
    "timestamp": NOW.isoformat(),
}
