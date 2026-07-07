"""Phase 10 standardized AI API exceptions and FastAPI handlers."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorEnvelope(BaseModel):
    """Sanitized error payload returned by the AI network boundary."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    error_code: str = Field(..., examples=["AI_DEPENDENCY_UNAVAILABLE"])
    message: str = Field(..., examples=["The requested AI dependency is temporarily unavailable."])
    request_id: str = Field(..., examples=["9b116ef2-36ec-4429-9b0d-14f6ed8dbf37"])
    details: Optional[Any] = None


class AIServiceError(RuntimeError):
    """Base class for sanitized service errors raised inside Phase 10 routers."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "AI_SERVICE_ERROR"
    public_message = "The AI service is temporarily unavailable."

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        super().__init__(message or self.public_message)
        self.message = message or self.public_message
        self.details = details


class AIDependencyUnavailable(AIServiceError):
    """Raised when Neo4j, Qdrant, model artifacts, or an LLM runtime cannot be reached."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "AI_DEPENDENCY_UNAVAILABLE"
    public_message = "A required AI dependency is temporarily unavailable."


class AIInvalidRequest(AIServiceError):
    """Raised when semantic validation fails after Pydantic parsing succeeds."""

    status_code = 422
    error_code = "AI_INVALID_REQUEST"
    public_message = "The AI request is invalid for this operation."


class AIEngineTimeout(AIServiceError):
    """Raised when an LLM, vector search, graph query, or ML operation exceeds its deadline."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "AI_ENGINE_TIMEOUT"
    public_message = "The AI engine timed out while processing the request."


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def _response(status_code: int, payload: ErrorEnvelope):
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def ai_service_exception_handler(request: Request, exc: AIServiceError):
    request_id = _request_id(request)
    logger.warning(
        "AI service exception [%s] request_id=%s path=%s message=%s",
        exc.error_code,
        request_id,
        request.url.path,
        exc.message,
    )
    return _response(
        exc.status_code,
        ErrorEnvelope(
            error_code=exc.error_code,
            message=exc.public_message,
            request_id=request_id,
            details=exc.details,
        ),
    )


async def ai_http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = _request_id(request)
    logger.info("HTTP exception request_id=%s path=%s status=%s", request_id, request.url.path, exc.status_code)
    return _response(
        exc.status_code,
        ErrorEnvelope(
            error_code="HTTP_ERROR",
            message=str(exc.detail),
            request_id=request_id,
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = _request_id(request)
    logger.warning("Request validation failed request_id=%s path=%s errors=%s", request_id, request.url.path, exc.errors())
    return _response(
        422,
        ErrorEnvelope(
            error_code="VALIDATION_ERROR",
            message="Request validation failed. Check payload shape, field types, and allowed values.",
            request_id=request_id,
            details=exc.errors(),
        ),
    )


def install_ai_exception_handlers(app: FastAPI) -> None:
    """Install sanitized exception handlers on a FastAPI application.

    Member 1 should call this when mounting the router into the enterprise
    gateway so internal Cypher queries, embedding/runtime paths, or LLM details
    are not leaked to clients.
    """

    app.add_exception_handler(AIServiceError, ai_service_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
