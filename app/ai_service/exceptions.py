"""Standardized exception handlers for the AI service and UI contract."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai_service.middleware import get_request_id
from app.ai_service.responses import create_ui_response

logger = logging.getLogger(__name__)
UI_PREFIX = "/api/v1/ai/ui/"

class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool = False
    error_code: str = Field(...)
    message: str = Field(...)
    request_id: str = Field(...)
    details: Optional[Any] = None

class AIServiceError(RuntimeError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "AI_SERVICE_ERROR"
    public_message = "The AI service is temporarily unavailable."
    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        super().__init__(message or self.public_message)
        self.message, self.details = message or self.public_message, details

class AIDependencyUnavailable(AIServiceError):
    status_code, error_code, public_message = 503, "AI_DEPENDENCY_UNAVAILABLE", "A required AI dependency is temporarily unavailable."
class AIInvalidRequest(AIServiceError):
    status_code, error_code, public_message = 422, "AI_INVALID_REQUEST", "The AI request is invalid for this operation."
class AIEngineTimeout(AIServiceError):
    status_code, error_code, public_message = 504, "AI_ENGINE_TIMEOUT", "The AI engine timed out while processing the request."

def _request_id(request: Request) -> str:
    return get_request_id(request)
def _is_ui(request: Request) -> bool:
    return request.url.path.startswith(UI_PREFIX)
def _response(status_code: int, payload: ErrorEnvelope) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
def _ui_error(request: Request, status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return create_ui_response(request_id=_request_id(request), success=False,
        error={"code": code, "message": message, "details": details},
        module="phase-11-ui", status_code=status_code)

async def ai_service_exception_handler(request: Request, exc: AIServiceError):
    if _is_ui(request):
        return _ui_error(request, exc.status_code, exc.error_code, exc.public_message, exc.details)
    return _response(exc.status_code, ErrorEnvelope(error_code=exc.error_code, message=exc.public_message, request_id=_request_id(request), details=exc.details))

async def ai_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if _is_ui(request):
        return _ui_error(request, exc.status_code, "HTTP_ERROR", str(exc.detail))
    return _response(exc.status_code, ErrorEnvelope(error_code="HTTP_ERROR", message=str(exc.detail), request_id=_request_id(request)))

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = exc.errors()
    if _is_ui(request):
        return _ui_error(request, 422, "VALIDATION_ERROR", "Request validation failed. Check payload shape, field types, and allowed values.", details)
    return _response(422, ErrorEnvelope(error_code="VALIDATION_ERROR", message="Request validation failed. Check payload shape, field types, and allowed values.", request_id=_request_id(request), details=details))

async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception path=%s", request.url.path, exc_info=exc)
    if _is_ui(request):
        return _ui_error(request, 500, "INTERNAL_SERVER_ERROR", "An unexpected UI service error occurred.")
    return _response(500, ErrorEnvelope(error_code="INTERNAL_SERVER_ERROR", message="An unexpected service error occurred.", request_id=_request_id(request)))

def install_ai_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AIServiceError, ai_service_exception_handler)
    app.add_exception_handler(StarletteHTTPException, ai_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
