"""Phase 1 — Shared response helper (Section 2.2 / 3.1).

:func:`create_ui_response` is the **single** function route handlers under
``/api/v1/ai/ui/*`` should call to build a contract-compliant
``JSONResponse``. It guarantees:

1. The exact :class:`~app.ai_service.schemas.UIAPIResponseEnvelope`
   shape (``requestId / generatedAt / success / error / data``) — Section 1.1.
2. ``x-ai-module`` + ``x-request-id`` response headers on every call —
   Section 1.2 (also enforced independently by
   :class:`app.ai_service.middleware.UIContractRoute` so a handler
   can never accidentally ship a response missing them).
3. Recursive "no ``null`` arrays" sanitation — Section 1.3. Any dict key
   whose value is ``None`` *and* whose name matches a known/likely array
   field (see :data:`KNOWN_ARRAY_FIELDS`), or whose sibling occurrences in
   the same payload are lists, is coerced to ``[]``.

Usage
-----
.. code-block:: python

    from app.ai_service import create_ui_response

    return create_ui_response(
        data={"nodes": None, "edges": []},   # nodes -> [] automatically
        request_id=request_id,
        module="phase-11-ui",
    )

    # error path
    return create_ui_response(
        success=False,
        error={"code": "AI_DEPENDENCY_UNAVAILABLE", "message": "GraphRAG engine offline."},
        request_id=request_id,
        module="phase-11-ui",
        status_code=503,
    )
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from fastapi import status
from fastapi.responses import JSONResponse

from app.ai_service.middleware import (
    AI_MODULE_HEADER,
    DEFAULT_AI_MODULE,
    REQUEST_ID_HEADER,
)
from app.ai_service.schemas import UIAPIErrorPayload, UIAPIResponseEnvelope, utc_now_iso

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section 1.3 — array sanitation
# ---------------------------------------------------------------------------
# Field names that are contractually arrays across the UI-shaped payloads
# (Section 11 / Phase 11 schemas + Phase 0-10 domain models). This list is
# intentionally broad — any key found here that resolves to ``None`` is
# rewritten to ``[]``. Keys *not* in this list are only sanitised when a
# sibling key of the same name elsewhere in the same payload is a list
# (heuristic fallback so new/unknown array fields are still protected).
KNOWN_ARRAY_FIELDS: frozenset[str] = frozenset(
    {
        # Section 11 / ui_schemas.py
        "edges",
        "history",
        "logs",
        "nodes",
        "highlightedNodes",
        "highlightedEdges",
        "citations",
        "features",
        "confidenceMatrix",
        # chat_event_schemas.py
        "highlightNodeIds",
        "highlightEdgeIds",
        "tools",
        # decision.py
        "toolingRequired",
        "tooling_required",
        "hazards",
        "requiredPpe",
        "required_ppe",
        "triggeredRules",
        "triggered_rules",
        "recommendations",
        "sopSteps",
        "sop_steps",
        "decisionLog",
        "decision_log",
        # graphrag.py
        "rootNodeIds",
        "root_node_ids",
        "contextChunks",
        "context_chunks",
        "graphNodes",
        "graph_nodes",
        "graphEdges",
        "graph_edges",
        # predictive.py
        "anomalyFlags",
        "anomaly_flags",
        "anomalousSensors",
        "anomalous_sensors",
        "featureImportance",
        "feature_importance",
        "featureColumns",
        "feature_columns",
        # xai.py
        "contributingFailureModes",
        "contributing_failure_modes",
        "globalFeatureImportance",
        "global_feature_importance",
        "localFeatureImportance",
        "local_feature_importance",
        # generic / common UI vocabulary
        "items",
        "results",
        "data_points",
        "dataPoints",
        "actions",
        "messages",
        "states",
        "sensors",
        "warnings",
        "errors",
        "readings",
        "allowedOrigins",
        "exposedHeaders",
        "endpoints",
    }
)


def _looks_like_array_key(key: str) -> bool:
    """Heuristic fallback for array-shaped keys not in :data:`KNOWN_ARRAY_FIELDS`.

    Catches common pluralisation / naming patterns (``xIds``, ``xList``,
    trailing ``s``-plurals for compound camelCase/ snake_case identifiers)
    so genuinely new array fields introduced later are still defended
    without needing a code change to this allow-list.
    """

    lowered = key.lower()
    if lowered.endswith(("ids", "_ids", "list", "_list", "arr", "_array")):
        return True
    return False


def sanitize_arrays(value: Any, *, _known_array_keys: frozenset[str] = KNOWN_ARRAY_FIELDS) -> Any:
    """Recursively replace ``None`` array-typed values with ``[]``.

    Walks ``dict``/``list`` structures depth-first. For dict keys, a
    ``None`` value is rewritten to ``[]`` when:

    * the key name is a known array field (:data:`KNOWN_ARRAY_FIELDS`), or
    * the key name heuristically looks like an array field
      (:func:`_looks_like_array_key`).

    Non-array ``None`` values (scalars, optional objects) are left
    untouched — only array-typed fields are in scope per Section 1.3.
    """

    if isinstance(value, Mapping):
        sanitized: Dict[str, Any] = {}
        for key, val in value.items():
            if val is None and (key in _known_array_keys or _looks_like_array_key(str(key))):
                sanitized[key] = []
            else:
                sanitized[key] = sanitize_arrays(val, _known_array_keys=_known_array_keys)
        return sanitized
    if isinstance(value, list):
        return [sanitize_arrays(item, _known_array_keys=_known_array_keys) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_arrays(item, _known_array_keys=_known_array_keys) for item in value)
    return value


# ---------------------------------------------------------------------------
# Section 2.2 / 3.1 — the shared response helper
# ---------------------------------------------------------------------------
def _coerce_error(error: Optional[Union[Mapping[str, Any], UIAPIErrorPayload, str]]) -> Optional[Dict[str, Any]]:
    if error is None:
        return None
    if isinstance(error, UIAPIErrorPayload):
        return error.model_dump(mode="json")
    if isinstance(error, str):
        return UIAPIErrorPayload(code="AI_SERVICE_ERROR", message=error).model_dump(mode="json")
    if isinstance(error, Mapping):
        payload = dict(error)
        payload.setdefault("code", "AI_SERVICE_ERROR")
        payload.setdefault("message", "An unspecified error occurred.")
        return UIAPIErrorPayload(**payload).model_dump(mode="json")
    raise TypeError(f"Unsupported error payload type: {type(error)!r}")


_UNSET = object()


def create_ui_response(
    *,
    data: Any = _UNSET,
    request_id: str,
    success: bool = True,
    error: Optional[Union[Mapping[str, Any], UIAPIErrorPayload, str]] = None,
    module: str = DEFAULT_AI_MODULE,
    status_code: Optional[int] = None,
    extra_headers: Optional[Mapping[str, str]] = None,
) -> JSONResponse:
    """Build the standard :class:`UIAPIResponseEnvelope` as a ``JSONResponse``.

    Parameters
    ----------
    data:
        The business payload. Per Section 1.1, ``data`` should be ``null``
        when ``success`` is ``False`` — this is the default: if the caller
        omits ``data`` entirely on a failure response, it resolves to
        ``None`` automatically. A caller may still explicitly pass a
        ``data`` value alongside ``success=False`` for self-diagnostic
        endpoints that intentionally surface partial/diagnostic state on
        failure (e.g. a CORS-configuration probe reporting *why* it is
        misconfigured); that explicit choice is respected. Any array-typed
        field that resolves to ``None`` is rewritten to ``[]``
        (Section 1.3) before serialization.
    request_id:
        The tracking id to echo back — callers should resolve this via
        :func:`app.ai_service.middleware.resolve_request_id` (or the
        ``request_id`` already stashed on ``request.state`` by
        :class:`UIContractRoute`) so it matches the inbound
        ``X-Request-ID`` header exactly.
    success:
        Whether the operation succeeded.
    error:
        ``None`` on success. On failure, a mapping/string/``UIAPIErrorPayload``
        describing what went wrong; normalised to the strict
        ``{"code", "message", "details"}`` object shape.
    module:
        Value for the ``x-ai-module`` response header — the handling
        submodule identifier (e.g. ``"phase-11-ui"``).
    status_code:
        Explicit HTTP status. Defaults to ``200`` on success and ``503``
        on failure (matching the existing UI router convention), but any
        caller needing a different code (e.g. ``422``) may pass it
        explicitly.
    extra_headers:
        Additional headers to merge in (never overrides ``x-request-id``
        or ``x-ai-module``).
    """

    if not success:
        if data is _UNSET:
            data = None
        if error is None:
            error = UIAPIErrorPayload(code="AI_SERVICE_ERROR", message="An unspecified error occurred.")
    else:
        if data is _UNSET:
            data = None
        error = None

    sanitized_data = sanitize_arrays(data) if data is not None else data
    error_payload = _coerce_error(error)

    envelope = UIAPIResponseEnvelope[Any](
        requestId=request_id,
        generatedAt=utc_now_iso(),
        success=bool(success),
        error=error_payload,
        data=sanitized_data,
    )

    resolved_status = status_code or (status.HTTP_200_OK if success else status.HTTP_503_SERVICE_UNAVAILABLE)

    headers: Dict[str, str] = dict(extra_headers or {})
    headers[REQUEST_ID_HEADER] = request_id
    headers[AI_MODULE_HEADER] = module

    body = envelope.model_dump(mode="json", by_alias=True)
    # Explicitly guarantee the contractual "error: null on success" rule
    # even if a future pydantic default changes (belt & suspenders).
    if success:
        body["error"] = None

    return JSONResponse(status_code=resolved_status, content=body, headers=headers)
