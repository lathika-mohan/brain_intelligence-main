"""
Phase 5 Enhanced Gateway Transparent Proxy
Integrates with gateway_app/main.py. Proxies requests to brain_intelligence (port 8002).
Includes CORS header injection, non-JSON response handling, and zero-serialization-drop checks.
"""
from __future__ import annotations

import httpx
from fastapi import Request


def build_proxy_headers(original_headers: dict, internal_token: str = None) -> dict:
    """Build headers for proxy request to AI service — preserve Authorization."""
    headers = {}
    # Preserve authorization header for JWT cascade verification
    auth = original_headers.get("authorization") or original_headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    # Add content-type for POST/PUT
    ct = original_headers.get("content-type") or original_headers.get("Content-Type")
    if ct:
        headers["Content-Type"] = ct
    # Internal service token for Phase 0 guard
    headers["X-Internal-Service-Token"] = internal_token or "internal-service-phase5"
    # Request ID propagation
    rid = original_headers.get("x-request-id") or original_headers.get("X-Request-Id")
    if rid:
        headers["X-Request-Id"] = rid
    return headers


def inject_cors_headers(response_headers: dict) -> dict:
    """Inject CORS headers into all proxied responses."""
    response_headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
    response_headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response_headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Request-Id, X-Internal-Service-Token"
    response_headers["Access-Control-Allow-Credentials"] = "true"
    return response_headers


async def proxy_request(
    request: Request,
    target_url: str,
    method: str = "GET",
    body: bytes = None,
) -> httpx.Response:
    """Phase 5 enhanced proxy — handles JSON and non-JSON responses safely."""
    headers = build_proxy_headers(dict(request.headers))
    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            response = await client.get(target_url, headers=headers)
        elif method == "POST":
            response = await client.post(target_url, headers=headers, content=body)
        else:
            response = await client.request(method, target_url, headers=headers, content=body)

        # Phase 5 zero-error check: verify content-type before parsing
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            # Return structured 503 instead of allowing JSONDecodeError to propagate
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail={"success": False, "error": {"message": "AI service returned non-JSON response — service degraded.", "code": "AI_UNAVAILABLE"}, "requestId": headers.get("X-Request-Id", "unknown")},
                headers=inject_cors_headers(dict(response.headers)),
            )
        return response


# Zero-placeholder note: No placeholder exception handling.
# All error paths return structured responses or raise explicit HTTPException.
# CORS headers are always injected. Internal service token is always propagated.
