"""
Internal-Only Guard Middleware — Phase 0 Enforcement
Ensures brain_intelligence is NOT callable directly from browser without gateway.

Rule:
- If request has valid X-Internal-Service-Token == SERVICE_API_KEY → allow
- If path is /docs, /redoc, /openapi.json, /, /health, /api/v1/graphrag/health, /api/v1/predictive/health → allow in dev (bypass)
- If APP_ENV == development and CORS origin check bypass allowed → allow with warning
- Otherwise → 403 with explicit message about Single Gateway Architecture

This middleware makes Rule #2 enforceable at runtime.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths that are allowed without service token (for local dev / health probes)
ALLOWLIST_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/graphrag/health",
    "/api/v1/predictive/health",
    "/api/v1/decision/health",
    "/api/v1/vector/health",
}

class InternalOnlyGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Service token from env — must match gateway's SERVICE_API_KEY
        self.service_token = os.getenv("SERVICE_API_KEY") or os.getenv("PLATFORM_GATEWAY_SERVICE_TOKEN") or "changeme_internal_service_key"
        self.app_env = os.getenv("APP_ENV", "development").lower()
        logger.info(f"InternalOnlyGuardMiddleware initialized — env={self.app_env}, token_set={bool(self.service_token)}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Allowlist for health/docs always
        if path in ALLOWLIST_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # In development, allow if no token but log warning — enables standalone Phase 5A tests
        # In production, strict enforcement
        token = request.headers.get("X-Internal-Service-Token") or request.headers.get("X-Service-Token") or request.headers.get("x-internal-service-token")
        auth_header = request.headers.get("Authorization", "")

        # Check: service token valid
        if token and token == self.service_token:
            # Valid internal call from gateway
            return await call_next(request)

        # Check: internal service Bearer token (alternative)
        if auth_header.startswith("Bearer ") and self.service_token in auth_header:
            return await call_next(request)

        # Development bypass — allow but warn
        if self.app_env == "development":
            logger.warning(
                f"Internal-only guard BYPASSED in development for path {path}. "
                "In production this would be 403. "
                "Frontend should NEVER call AI direct — must go via Gateway."
            )
            response = await call_next(request)
            # Add header to indicate bypass
            response.headers["X-Phase0-Warning"] = "Direct AI access in dev only - use gateway in prod"
            return response

        # Production — strict 403 for direct browser calls
        logger.warning(f"Blocked direct browser call to internal AI service: {path} from {request.client.host if request.client else 'unknown'}")
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Forbidden — brain_intelligence is internal-only",
                "detail": "Direct browser access to brain_intelligence is forbidden. Use Gateway: POST https://api.iob.enterprise.internal/v1/ai/* . See Phase 0 guide.",
                "pipeline": "Frontend -> Gateway -> REST Gateway Relay -> brain_intelligence",
                "rule_violated": "Rule #1: Frontend NEVER contacts brain_intelligence directly. Rule #2: brain_intelligence is internal-only microservice.",
                "fix": "Call Gateway at /api/v1/ai/* with Authorization Bearer <user_jwt>. Gateway forwards with X-Internal-Service-Token.",
                "request_id": request.headers.get("X-Request-ID", "unknown"),
                "flagged_path": path,
            },
        )
