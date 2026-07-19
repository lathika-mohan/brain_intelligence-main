"""Contract tests for the Member 3 Stage 1 AI gateway."""
from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_client

AI_BASE_URL = "http://ai-platform.test"
UNAVAILABLE_ENVELOPE = {
    "error": {
        "code": "AI_UNAVAILABLE",
        "message": "AI service is temporarily unavailable",
    }
}
RICH_PREDICTION_PAYLOAD = {
    "success": True,
    "data": {
        "asset_id": "P-101A",
        "component_id": "bearing-de",
        "rul": {
            "value_days": 5.25,
            "lower_bound_days": 3.5,
            "upper_bound_days": 7.0,
        },
        "failure_probability": {
            "probability": 0.82,
            "failure_mode_id": "bearing-wear",
            "failure_mode_label": "Bearing Wear",
        },
        "anomaly_flags": ["HIGH_VIBRATION", "BEARING_TEMPERATURE_RISE"],
        "anomalous_sensors": ["vibration_rms", "bearing_temp"],
        "explanation_id": "exp-p101a-001",
    },
    "error": None,
    "request_id": "req-stage1-001",
}


@pytest.fixture(autouse=True)
def configured_ai_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a deterministic configuration while retaining runtime lookup."""
    monkeypatch.setattr(
        ai_client,
        "settings",
        SimpleNamespace(AI_PLATFORM_URL=AI_BASE_URL),
    )


def install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    """Route only the gateway's outbound AsyncClient through MockTransport."""
    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def async_client_factory(*args, **kwargs):
        return real_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(ai_client.httpx, "AsyncClient", async_client_factory)


def test_predictive_happy_path_is_byte_for_byte_transparent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_bytes = json.dumps(
        RICH_PREDICTION_PAYLOAD,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    inbound_payload = {
        "asset_id": "P-101A",
        "history": [{"timestamp": "2026-07-15T10:00:00Z", "vibration_rms": 5.2}],
    }

    def upstream(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{AI_BASE_URL}/api/v1/predictive/infer"
        assert json.loads(request.content) == inbound_payload
        return httpx.Response(
            200,
            content=upstream_bytes,
            headers={"content-type": "application/json"},
        )

    install_mock_transport(monkeypatch, upstream)

    with TestClient(app) as client:
        response = client.post("/api/v1/ai/predictive/infer", json=inbound_payload)

    assert response.status_code == 200
    assert response.json() == RICH_PREDICTION_PAYLOAD
    assert response.content == upstream_bytes


@pytest.mark.parametrize(
    ("gateway_method", "gateway_path", "upstream_method", "upstream_path", "body"),
    [
        (
            "GET",
            "/api/v1/ai/predictive/P-101A/explain",
            "GET",
            "/api/v1/xai/explain?asset_id=P-101A",
            None,
        ),
        (
            "POST",
            "/api/v1/ai/graphrag/query",
            "POST",
            "/api/v1/graphrag/query",
            {"query_text": "Why is P-101A vibrating?", "asset_id": "P-101A"},
        ),
        (
            "POST",
            "/api/v1/ai/chat",
            "POST",
            "/api/v1/chat",
            {"message": "Diagnose P-101A", "session_id": "session-1"},
        ),
        (
            "GET",
            "/api/v1/ai/knowledge/search?q=bearing%20wear",
            "GET",
            "/api/v1/knowledge/search?q=bearing%20wear",
            None,
        ),
        (
            "GET",
            "/api/v1/ai/decision/P-101A/recommendation",
            "GET",
            "/api/v1/decision/P-101A/recommendation",
            None,
        ),
    ],
)
def test_all_relay_routes_use_the_frozen_upstream_mapping(
    monkeypatch: pytest.MonkeyPatch,
    gateway_method: str,
    gateway_path: str,
    upstream_method: str,
    upstream_path: str,
    body: dict | None,
) -> None:
    upstream_payload = {"success": True, "data": {"unchanged": [1, "two", None]}}

    def upstream(request: httpx.Request) -> httpx.Response:
        assert request.method == upstream_method
        assert str(request.url) == f"{AI_BASE_URL}{upstream_path}"
        if body is not None:
            assert json.loads(request.content) == body
        else:
            assert request.content == b""
        return httpx.Response(200, json=upstream_payload)

    install_mock_transport(monkeypatch, upstream)

    with TestClient(app) as client:
        response = client.request(gateway_method, gateway_path, json=body)

    assert response.status_code == 200
    assert response.json() == upstream_payload


def test_timeout_returns_ai_unavailable_without_internal_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timed_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated upstream timeout", request=request)

    install_mock_transport(monkeypatch, timed_out)

    started = time.monotonic()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/predictive/infer",
            json={"asset_id": "P-101A", "history": []},
        )
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert response.json() == UNAVAILABLE_ENVELOPE
    assert elapsed < 4.5


@pytest.mark.parametrize("failure_kind", ["connect", "http-status"])
def test_connection_and_http_status_failures_share_the_frozen_envelope(
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        if failure_kind == "connect":
            raise httpx.ConnectError("simulated dead port", request=request)
        return httpx.Response(503, json={"detail": "maintenance"})

    install_mock_transport(monkeypatch, unavailable)

    with TestClient(app) as client:
        response = client.post("/api/v1/ai/chat", json={"message": "status"})

    assert response.status_code == 200
    assert response.json() == UNAVAILABLE_ENVELOPE
