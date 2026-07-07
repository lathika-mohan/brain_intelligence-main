"""Phase 11 — CORS / preflight verification helpers.

Member 4's Next.js client runs on ``http://localhost:3000`` (or
``https://app.iob.enterprise.internal`` in production) and the FastAPI
service lives on a different origin. When the front-end ``fetch`` fires
the browser sends a CORS preflight (``OPTIONS``) before the real POST.

This module provides:

* :data:`UI_ALLOWED_HEADERS` — exact list of headers the AI UI endpoints
  will accept (request side). Member 4 must send exactly these (browsers
  allow ``*`` only in narrow cases).
* :data:`UI_ALLOWED_METHODS` — exact list of HTTP methods the AI UI
  endpoints support.
* :data:`UI_EXPOSED_HEADERS` — headers the front-end may *read* from
  responses (``x-request-id`` for tracing, ``x-correlation-id``, etc.).
* :func:`build_ui_preflight_headers` — utility used by the dedicated
  ``/api/v1/ai/ui/options`` probe endpoint so Member 1 (gateway) and
  Member 4 (frontend) can verify CORS wiring from CI.
* :func:`verify_cors_configuration` — lightweight sanity check that the
  configured origins include the documented Next.js origins; raises
  :class:`CORSConfigurationError` with a precise remediation message
  when something is off.
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Header / method allow-lists
# ---------------------------------------------------------------------------
# These mirror the production values Member 4 documents in their
# ``apiClient`` interceptor and the Member 1 gateway's
# ``CORSMiddleware`` configuration. Any drift here is the #1 source of
# "blocked by CORS" tickets, so the values are kept in code (not env)
# and surfaced in the preflight probe.
UI_ALLOWED_METHODS: List[str] = ["GET", "POST", "OPTIONS"]
UI_ALLOWED_HEADERS: List[str] = [
    "accept",
    "accept-language",
    "authorization",
    "content-type",
    "x-request-id",
    "x-correlation-id",
    "x-feature-flags",
]
UI_EXPOSED_HEADERS: List[str] = [
    "content-type",
    "x-request-id",
    "x-correlation-id",
    "x-ai-module",
    "x-ai-version",
]

# Origin allow-list (must include Member 4's Next.js dev + prod origins).
DEFAULT_FRONTEND_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://app.iob.enterprise.internal",
]


class CORSConfigurationError(RuntimeError):
    """Raised when the configured CORS origins are missing the Next.js origin."""


def build_ui_preflight_headers(*, origin: Optional[str] = None) -> Dict[str, str]:
    """Build the headers the FastAPI preflight handler should return.

    Browsers check ``Access-Control-Allow-Origin``, ``Access-Control-
    Allow-Methods``, ``Access-Control-Allow-Headers`` and
    ``Access-Control-Max-Age`` against the preflight request before
    letting the real ``fetch`` fly. We always echo the request
    ``Origin`` (when present) so the gateway's wildcard configuration
    doesn't accidentally expose credentials to the wrong origin.
    """

    headers = {
        "Access-Control-Allow-Methods": ", ".join(UI_ALLOWED_METHODS),
        "Access-Control-Allow-Headers": ", ".join(UI_ALLOWED_HEADERS),
        "Access-Control-Expose-Headers": ", ".join(UI_EXPOSED_HEADERS),
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    return headers


def verify_cors_configuration(
    configured_origins: Sequence[str],
    *,
    required_origins: Optional[Sequence[str]] = None,
) -> bool:
    """Sanity check the gateway CORS allow-list.

    Returns ``True`` when every required origin is present. When
    something is missing a :class:`CORSConfigurationError` is raised
    with a precise remediation message — this is the same message
    surfaced in the ``/api/v1/ai/ui/cors-check`` endpoint so Member 1
    can self-diagnose from CI.
    """

    required = list(required_origins or DEFAULT_FRONTEND_ORIGINS)
    configured = {o.strip() for o in configured_origins if o and o.strip()}

    missing = [origin for origin in required if origin not in configured]
    if missing:
        msg = (
            "CORS allow-list is missing Next.js frontend origins: "
            f"{missing}. Add them to the CORS_ALLOW_ORIGINS env var "
            "(comma-separated) on the FastAPI service and re-deploy. "
            "See docs/AI_CORS_INTEGRATION.md for the full allow-list."
        )
        logger.error(msg)
        raise CORSConfigurationError(msg)

    if "*" in configured:
        logger.warning(
            "CORS allow-list contains a wildcard '*'; this is incompatible with "
            "credentialed requests. Replace it with the explicit Next.js origins."
        )

    return True


def safe_cors_origin(request_origin: Optional[str], allowed: Iterable[str]) -> Optional[str]:
    """Return ``request_origin`` only if it appears in the allow-list.

    Used by the OPTIONS probe so the response is never wider than the
    configured allow-list, even when the gateway uses ``*``.
    """

    if not request_origin:
        return None
    allowed_set = {a.strip() for a in allowed if a and a.strip()}
    if request_origin in allowed_set:
        return request_origin
    return None
