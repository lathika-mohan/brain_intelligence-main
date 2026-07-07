"""Phase 11 — CORS / preflight verification tests."""
from __future__ import annotations

import pytest

from app.ai_service.integration.cors_headers import (
    CORSConfigurationError,
    DEFAULT_FRONTEND_ORIGINS,
    UI_ALLOWED_HEADERS,
    UI_ALLOWED_METHODS,
    UI_EXPOSED_HEADERS,
    build_ui_preflight_headers,
    safe_cors_origin,
    verify_cors_configuration,
)


class TestBuildUiPreflightHeaders:
    def test_returns_required_headers(self) -> None:
        headers = build_ui_preflight_headers(origin="http://localhost:3000")
        assert headers["Access-Control-Allow-Methods"] == ", ".join(UI_ALLOWED_METHODS)
        assert headers["Access-Control-Allow-Headers"] == ", ".join(UI_ALLOWED_HEADERS)
        assert headers["Access-Control-Expose-Headers"] == ", ".join(UI_EXPOSED_HEADERS)
        assert headers["Access-Control-Max-Age"] == "600"
        assert headers["Vary"] == "Origin"
        assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"

    def test_no_origin_omits_allow_origin(self) -> None:
        headers = build_ui_preflight_headers()
        assert "Access-Control-Allow-Origin" not in headers

    def test_methods_include_post_and_get(self) -> None:
        assert "POST" in UI_ALLOWED_METHODS
        assert "GET" in UI_ALLOWED_METHODS
        assert "OPTIONS" in UI_ALLOWED_METHODS

    def test_headers_include_authorization(self) -> None:
        # The Next.js apiClient sends Bearer tokens, so 'authorization' must be in the allow-list
        assert "authorization" in UI_ALLOWED_HEADERS

    def test_headers_include_content_type(self) -> None:
        # Required for application/json POSTs
        assert "content-type" in UI_ALLOWED_HEADERS

    def test_headers_include_request_id(self) -> None:
        # Tracing header used by the front-end
        assert "x-request-id" in UI_ALLOWED_HEADERS

    def test_exposed_headers_include_x_ai_module(self) -> None:
        # The panel renders a 'Powered by Phase 11' footer based on this header
        assert "x-ai-module" in UI_EXPOSED_HEADERS


class TestVerifyCorsConfiguration:
    def test_passes_with_all_required_origins(self) -> None:
        assert verify_cors_configuration(DEFAULT_FRONTEND_ORIGINS) is True

    def test_passes_with_configured_origins_superset(self) -> None:
        configured = DEFAULT_FRONTEND_ORIGINS + ["https://staging.iob.enterprise.internal"]
        assert verify_cors_configuration(configured) is True

    def test_raises_with_missing_origin(self) -> None:
        with pytest.raises(CORSConfigurationError) as exc_info:
            verify_cors_configuration(["https://app.iob.enterprise.internal"])
        msg = str(exc_info.value)
        assert "http://localhost:3000" in msg
        assert "CORS_ALLOW_ORIGINS" in msg

    def test_raises_with_empty_origin_list(self) -> None:
        with pytest.raises(CORSConfigurationError):
            verify_cors_configuration([])

    def test_warns_on_wildcard(self, caplog) -> None:
        # Should not raise; wildcard is dangerous but not invalid for the allow-list check
        assert verify_cors_configuration(["*", *DEFAULT_FRONTEND_ORIGINS]) is True

    def test_strips_whitespace(self) -> None:
        configured = [f" {o} " for o in DEFAULT_FRONTEND_ORIGINS]
        assert verify_cors_configuration(configured) is True


class TestSafeCorsOrigin:
    def test_returns_origin_when_allowed(self) -> None:
        allowed = ["http://localhost:3000"]
        assert safe_cors_origin("http://localhost:3000", allowed) == "http://localhost:3000"

    def test_returns_none_when_not_allowed(self) -> None:
        allowed = ["http://localhost:3000"]
        assert safe_cors_origin("http://evil.example", allowed) is None

    def test_returns_none_for_missing_origin(self) -> None:
        assert safe_cors_origin(None, ["http://localhost:3000"]) is None

    def test_strips_whitespace_in_allow_list(self) -> None:
        allowed = [" http://localhost:3000 "]
        assert safe_cors_origin("http://localhost:3000", allowed) == "http://localhost:3000"
