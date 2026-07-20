"""Phase 1 — Common Infrastructure & Response Contract.

This package is the **single source of truth** for the response envelope,
header contract, and sanitation rules shared by every endpoint mounted
under ``/api/v1/ai/ui/*`` (and any future AI UI sub-router).

Modules
-------
``schemas``
    Pydantic model(s) describing the wire-level ``UIAPIResponse`` envelope
    (Section 1.1 of the Phase 1 contract).
``responses``
    ``create_ui_response`` — the one function route handlers should call to
    build a contract-compliant ``JSONResponse``. Also hosts the array
    sanitation helper (Section 1.3).
``middleware``
    ``UIContractRoute`` — an ``APIRoute`` subclass installed as the
    ``route_class`` of the AI UI router so every request/response passing
    through it gets ``x-request-id`` echo + ``x-ai-module`` header
    injection automatically (Section 1.2), even if a handler forgets.

Nothing in this package talks to a database, LLM, or external service —
it is pure, dependency-free plumbing so it can be imported from any
router, test, or future AI UI submodule without pulling in heavy
runtime dependencies.
"""
from __future__ import annotations

from app.ai_service.common.middleware import (
    AI_MODULE_HEADER,
    CORRELATION_ID_HEADER,
    DEFAULT_AI_MODULE,
    REQUEST_ID_HEADER,
    UIContractRoute,
    get_request_id,
    make_ui_contract_route,
    resolve_request_id,
)
from app.ai_service.common.responses import (
    KNOWN_ARRAY_FIELDS,
    create_ui_response,
    sanitize_arrays,
)
from app.ai_service.common.schemas import (
    UIAPIErrorPayload,
    UIAPIResponseEnvelope,
    utc_now_iso,
)

__all__ = [
    "AI_MODULE_HEADER",
    "CORRELATION_ID_HEADER",
    "DEFAULT_AI_MODULE",
    "REQUEST_ID_HEADER",
    "UIContractRoute",
    "get_request_id",
    "make_ui_contract_route",
    "resolve_request_id",
    "KNOWN_ARRAY_FIELDS",
    "create_ui_response",
    "sanitize_arrays",
    "UIAPIErrorPayload",
    "UIAPIResponseEnvelope",
    "utc_now_iso",
]
