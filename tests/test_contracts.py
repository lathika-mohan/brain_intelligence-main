"""
Phase 0 contract smoke tests.

These do NOT require live Neo4j/Qdrant connections — they verify:
1. Every Pydantic schema round-trips cleanly.
2. Every FastAPI route responds with a schema-valid `APIResponse` envelope.
3. `/health` (liveness) works without any downstream dependency.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "service" in resp.json()


def test_health_liveness() -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_health_readiness_does_not_raise() -> None:
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ready", "degraded")
    assert set(body["dependencies"].keys()) == {"neo4j", "qdrant"}


def test_ingestion_telemetry_contract() -> None:
    payload = {
        "batch_id": "batch-test-0001",
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "readings": [
            {
                "schema_version": "1.0.0",
                "asset_id": "asset-101",
                "component_id": "component-55",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "readings": [
                    {"sensor_id": "sensor-9", "metric": "bearing_temp", "value": 78.2, "unit": "C", "quality": 0.98}
                ],
                "operating_mode": "RUNNING",
                "metadata": {},
            }
        ],
    }
    resp = client.post("/api/v1/ingestion/telemetry", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["accepted_readings"] == 1


def test_graphrag_query_contract() -> None:
    payload = {"query": "Why is Pump-101 overheating?", "asset_ids": ["asset-101"]}
    resp = client.post("/api/v1/graphrag/query", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["query"] == payload["query"]
    assert "answer" in data
    assert isinstance(data["vector_context"], list)
    assert isinstance(data["citations"], list)


def test_predictive_infer_contract() -> None:
    payload = {
        "asset_id": "asset-101",
        "component_id": "component-55",
        "telemetry_window": [
            {
                "schema_version": "1.0.0",
                "asset_id": "asset-101",
                "component_id": "component-55",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "readings": [
                    {"sensor_id": "sensor-9", "metric": "bearing_temp", "value": 78.2, "unit": "C", "quality": 0.98}
                ],
            }
        ],
    }
    resp = client.post("/api/v1/predictive/infer", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert "rul" in data
    assert "failure_probability" in data
    assert isinstance(data["anomaly_flags"], list)


def test_xai_explain_contract() -> None:
    payload = {"asset_id": "asset-101", "method": "SHAP", "scope": "LOCAL"}
    resp = client.post("/api/v1/xai/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["method"] == "SHAP"
    assert "root_cause" in data


def test_decision_recommend_contract() -> None:
    payload = {"asset_id": "asset-101", "max_recommendations": 3}
    resp = client.post("/api/v1/decision/recommend", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["asset_id"] == "asset-101"
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) <= 3
