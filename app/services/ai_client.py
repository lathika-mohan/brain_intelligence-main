"""Asynchronous client for the external IOB AI platform.

This module is deliberately limited to transport concerns. Successful JSON
responses are returned unchanged; unavailable upstream responses use the
frozen ``AI_UNAVAILABLE`` error envelope.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

try:
    # Member 1/backend layout documented by the Stage 1 contract.
    from app.config import settings  # type: ignore[import-not-found]
except ImportError:
    # Compatibility with this repository's existing centralized settings.
    from app.core.config import get_settings

    settings = get_settings()

logger = logging.getLogger(__name__)

_DEFAULT_AI_PLATFORM_URL = "http://localhost:8000"
_AI_UNAVAILABLE_MESSAGE = "AI service is temporarily unavailable"


def _ai_platform_url() -> str:
    """Read the AI platform URL from application configuration at call time."""
    configured_url = getattr(settings, "AI_PLATFORM_URL", None) or getattr(
        settings, "ai_platform_url", None
    )
    return str(configured_url or os.getenv("AI_PLATFORM_URL", _DEFAULT_AI_PLATFORM_URL)).rstrip(
        "/"
    )


def _unavailable_envelope() -> dict[str, dict[str, str]]:
    """Return a fresh copy of the frozen graceful-failure contract."""
    return {
        "error": {
            "code": "AI_UNAVAILABLE",
            "message": _AI_UNAVAILABLE_MESSAGE,
        }
    }


async def call_ai(
    path: str,
    payload: dict[str, Any] | None = None,
    method: str = "GET",
    timeout: float = 4.0,
) -> dict[str, Any]:
    """Call an AI-platform endpoint and transparently return its JSON body.

    Timeouts, non-success HTTP statuses, and connection-level failures are
    translated to the frozen ``AI_UNAVAILABLE`` envelope so the gateway never
    leaks an upstream transport exception as an internal-server error.
    """
    url = f"{_ai_platform_url()}/{path.lstrip('/')}"
    request_kwargs: dict[str, Any] = {}
    if payload is not None:
        request_kwargs["json"] = payload

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method.upper(), url, **request_kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        logger.warning("AI platform request timed out: %s %s (%s)", method.upper(), path, exc)
        return _unavailable_envelope()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "AI platform returned HTTP %s: %s %s",
            exc.response.status_code,
            method.upper(),
            path,
        )
        return _unavailable_envelope()
    except httpx.RequestError as exc:
        # ConnectError and other network failures must follow the same contract
        # as a timeout (for example, when AI_PLATFORM_URL points at a dead port).
        logger.warning("AI platform request failed: %s %s (%s)", method.upper(), path, exc)
        return _unavailable_envelope()
