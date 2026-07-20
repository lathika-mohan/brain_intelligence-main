"""Phase 11 — UI-shaped FastAPI sub-router.

Mounts at ``/api/v1/ai/ui`` and exposes the *frontend contract* projection
of the same engines that power the raw ``/api/v1/ai/*`` endpoints:

==================================  =====================================
UI endpoint                         Component it feeds
==================================  =====================================
``GET  /ui/digital-twin/{asset}``   ``DigitalTwinView.tsx``
``POST /ui/graphrag/query``         ``GraphRagPanel.tsx``
``GET  /ui/explain/{prediction}``   ``ShapExplainability.tsx``
``POST /ui/recommendations``        prescriptive-action card panel
``POST /ui/agent/chat``             multi-agent chat panel (with stream)
``POST /ui/agent/chat/stream``      multi-agent chat panel (NDJSON stream)
``GET  /ui/cors-check``             CORS preflight verification
``GET  /ui/options``                explicit OPTIONS preflight handler
``GET  /ui/contracts``              machine-readable contract manifest
==================================  =====================================

Every response validates through a Phase 11 schema (see
:mod:`app.ai_service.integration.schemas`) so any drift between the
backend shape and the front-end expectation surfaces as a 500 in CI
instead of a silently malformed payload in production.
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.ai_service.integration.adapters.chat_event_adapter import (
    to_chat_event_stream,
    to_ui_chat_message,
)
from app.ai_service.integration.adapters.frontend_adapters import (
    adapt_digital_twin_payload,
    adapt_explainability_payload,
    adapt_graphrag_payload,
    adapt_inference_to_prediction,
    adapt_recommendations_to_actions,
    build_telemetry_chart_series,
    to_ui_api_envelope,
)
from app.ai_service.integration.cors_headers import (
    build_ui_preflight_headers,
    safe_cors_origin,
    verify_cors_configuration,
)
from app.ai_service.integration.formatters.confidence_badge import (
    confidence_to_badge,
    confidence_to_color,
    confidence_to_warning_level,
)
from app.ai_service.integration.formatters.payload_formatters import (
    format_recharts_line_series,
    format_recharts_radar_series,
    format_shap_force_plot,
    format_shap_waterfall,
    format_subgraph_update_packet,
    format_time_series_points,
    format_vis_network_elements,
)
from app.ai_service.integration.response_shaping import (
    SUPPORTED_EXPLAIN_METHODS,
    UnsupportedExplainMethodError,
    resolve_explain_method,
    sanitize_arrays,
)
from app.ai_service.integration.schemas.ui_schemas import (
    UIAPIResponse,
    UIGraphRAGPayload,
    UIPrediction,
    UIShapExplanation,
    UITelemetry,
)

logger = logging.getLogger(__name__)


def _get_cors_origins() -> List[str]:
    """Return the configured CORS origins, falling back to documented defaults.

    The import is lazy so the UI router remains importable in tests and
    in environments where the full Phase 0-10 backend is not on the
    Python path. If the backend config is unreachable we return the
    documented defaults from
    :mod:`app.ai_service.integration.cors_headers`.
    """

    try:
        from app.core.config import get_settings

        settings = get_settings()
        return settings.cors_origins_list
    except Exception:  # noqa: BLE001 - safe fallback
        from app.ai_service.integration.cors_headers import DEFAULT_FRONTEND_ORIGINS

        return list(DEFAULT_FRONTEND_ORIGINS)



ui_router = APIRouter(
    prefix="/ui",
    tags=["AI Platform — UI Contracts (Phase 11)"],
    responses={
        200: {"description": "UI-shaped payload (Section 11 strict contract)."},
        422: {"description": "Pydantic validation error — see details for the offending field."},
        503: {"description": "AI dependency temporarily unavailable."},
    },
)


# ---------------------------------------------------------------------------
# Internal: shared engine dependency proxies
# ---------------------------------------------------------------------------
from fastapi.params import Depends as FastAPIDepends


class _LazyEngineDep(FastAPIDepends):
    """A FastAPI ``Depends`` wrapper that defers ``dependencies`` import.

    Inherits from ``fastapi.params.Depends`` so FastAPI recognizes it during route
    registration, and resolves the underlying dependency getter lazily via property access.
    """

    def __init__(self, getter_name: str, use_cache: bool = True) -> None:
        super().__init__(dependency=None, use_cache=use_cache)
        self._getter_name = getter_name

    @property
    def dependency(self):
        from app.ai_service import dependencies as _deps

        return getattr(_deps, self._getter_name)

    @dependency.setter
    def dependency(self, value):
        pass

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"_LazyEngineDep({self._getter_name!r})"

    @staticmethod
    def __get_pydantic_json_schema__(schema, generator):  # pragma: no cover
        return {"not_serialization_default": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _request_id(request: Request) -> str:
    return (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or str(uuid.uuid4())
    )


def _ui_response(
    *,
    data: Any,
    request_id: str,
    success: bool = True,
    error: Optional[Dict[str, Any]] = None,
    http_status: Optional[int] = None,
) -> JSONResponse:
    """Wrap a payload in the Section 11 ``UIAPIResponse`` envelope.

    Always returns a ``UIAPIResponse``-shaped dict, even on errors, so
    the front-end can rely on a single parsing path.

    Phase 2 — ``http_status`` lets a handler pick a specific non-200 code
    (e.g. **400** for a client-side validation error such as an
    unsupported explainability ``method``) while keeping the envelope
    shape identical; engine failures still default to 503.
    """

    body = to_ui_api_envelope(
        success=success, data=data, request_id=request_id, error=error
    )
    if success:
        status_code = status.HTTP_200_OK
    else:
        status_code = http_status or status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"x-request-id": request_id, "x-ai-module": "phase-11-ui"},
    )


# ===========================================================================
# 1. Digital Twin
# ===========================================================================
@ui_router.get(
    "/digital-twin/{asset_id}",
    response_model=UIAPIResponse[Dict[str, Any]],
    summary="DigitalTwinView.tsx payload",
    description=(
        "Returns the asset + live telemetry + chronological history shape "
        "consumed by ``src/components/DigitalTwinView.tsx``. Drives the "
        "rotational-speed / vibration / pressure / AI-risk cards and the "
        "SVG schematic."
    ),
)
async def digital_twin(
    asset_id: Annotated[str, Path(min_length=1, description="Asset id, e.g. 'P-101A'.")],
    request: Request,
    horizon: Annotated[
        int,
        Query(ge=1, le=168, description="Lookback window in hours for the history frames."),
    ] = 24,
    include_inference: Annotated[
        bool, Query(description="When true, runs predictive inference to populate riskScore.")
    ] = True,
    prediction_engine: Any = _LazyEngineDep("get_prediction_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        # Lazily import to avoid a hard import dependency in environments
        # where the predictive engine is not yet implemented.
        from app.predictive.telemetry_simulator import generate_episode
        from app.models.predictive import InferenceRequest

        episode = generate_episode(asset_id=asset_id)
        history_frames = episode.frames[-horizon:]

        inference = None
        if include_inference and prediction_engine is not None:
            try:
                inference = await prediction_engine.infer(
                    InferenceRequest(
                        asset_id=asset_id,
                        history=history_frames,
                        horizon_hours=min(horizon, 72),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - degraded mode is OK
                logger.warning("Predictive inference degraded for %s: %s", asset_id, exc)
                inference = None

        asset = {
            "id": asset_id,
            "name": asset_id,
            "type": "PUMP",
            "status": "OPERATIONAL",
            "parentId": None,
        }
        payload = adapt_digital_twin_payload(
            asset=asset, inference=inference, history=history_frames
        )
        # Phase 2 — response-shaping isolation: the top-level ``riskScore``
        # is now attached by the adapter (computed from the inference
        # failure probability, safely defaulted otherwise). Run the
        # explicit array sanitizer here as a final guarantee that no
        # list attribute ever serializes as null.
        payload = sanitize_arrays(payload)
        # Validate the response through the strict Pydantic model
        # so any drift surfaces as a 500 in CI.
        from app.ai_service.integration.schemas.ui_schemas import UIDigitalTwinPayload

        UIDigitalTwinPayload.model_validate(payload)
        return _ui_response(data=payload, request_id=request_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("digital_twin failed for %s", asset_id)
        return _ui_response(
            data={},
            request_id=request_id,
            success=False,
            error={"code": "DIGITAL_TWIN_FAILED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 2. GraphRAG
# ===========================================================================
@ui_router.post(
    "/graphrag/query",
    response_model=UIAPIResponse[UIGraphRAGPayload],
    summary="GraphRagPanel.tsx payload",
    description=(
        "Returns the full GraphRagPanel payload: nodes (with deterministic "
        "x/y layout), edges, log timeline, answer, highlighted node/edge "
        "ids, citations, and an overall confidence badge."
    ),
)
async def graphrag_query(
    body: Dict[str, Any],
    request: Request,
    graphrag_engine: Any = _LazyEngineDep("get_graphrag_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        from app.models.graphrag import GraphRagQueryRequest

        req = GraphRagQueryRequest(
            query_text=str(body.get("query") or body.get("query_text") or ""),
            asset_id=body.get("asset_id"),
            top_k=int(body.get("top_k", 8)),
        )
        response = await graphrag_engine.query(req)
        # Phase 2 — the adapter now appends structured execution logs,
        # aligns node ids/labels/relation names to the frontend vocabulary,
        # and strictly validates node types against the panel ontology.
        payload = adapt_graphrag_payload(response, query=req.query_text)
        # Augment with chart-ready extras
        from app.ai_service.integration.formatters.confidence_badge import confidence_to_badge

        payload["badge"] = confidence_to_badge(payload["confidence"]).value
        payload["warningLevel"] = confidence_to_warning_level(payload["confidence"])
        payload["color"] = confidence_to_color(payload["confidence"])
        # Phase 2 — strict non-null array protection prior to serialization.
        payload = sanitize_arrays(payload)
        UIGraphRAGPayload.model_validate(payload)
        return _ui_response(data=payload, request_id=request_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("graphrag_query failed")
        return _ui_response(
            data={"answer": "", "logs": [], "nodes": [], "edges": []},
            request_id=request_id,
            success=False,
            error={"code": "GRAPHRAG_FAILED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 3. SHAP / LIME explainability
# ===========================================================================
@ui_router.get(
    "/explain/{prediction_id}",
    response_model=UIAPIResponse[UIShapExplanation],
    summary="ShapExplainability.tsx payload",
    description=(
        "Returns the SHAP/LIME feature list **pre-sorted by |shapValue| desc** "
        "so the waterfall / force / bar layouts render in one pass. Also "
        "exposes ``baseValue`` and ``predictionValue`` for the force-plot "
        "anchors and the confidence matrix for the diagnostic strip."
    ),
)
async def explain(
    prediction_id: Annotated[str, Path(min_length=1)],
    request: Request,
    asset_id: Annotated[str, Query(min_length=1)] = "P-101A",
    method: Annotated[
        str,
        Query(
            description=(
                "Explainability method. Case-insensitive; accepts shap, lime, "
                "integrated_gradients (ig), permutation. Unsupported values "
                "return a clear HTTP 400 validation error."
            )
        ),
    ] = "SHAP",
    xai_engine: Any = _LazyEngineDep("get_xai_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    # ------------------------------------------------------------------
    # Phase 2 — strictly honor the ``method`` query parameter.
    # Case-insensitive + alias-aware (?method=shap, ?method=lime,
    # ?method=integrated_gradients all resolve). Anything unsupported is a
    # client error → HTTP 400 in the UIAPIResponse envelope, never a 422
    # or a silent fallback to SHAP.
    # ------------------------------------------------------------------
    try:
        resolved_method = resolve_explain_method(method)
    except UnsupportedExplainMethodError as exc:
        return _ui_response(
            data={
                "predictionId": prediction_id,
                "assetId": asset_id,
                "baseValue": 0.0,
                "predictionValue": 0.0,
                "features": [],
                "confidenceMatrix": [],
                "rootCause": {},
            },
            request_id=request_id,
            success=False,
            error={
                "code": "XAI_UNSUPPORTED_METHOD",
                "message": str(exc),
                "details": {
                    "method": method,
                    "supported": list(SUPPORTED_EXPLAIN_METHODS),
                    "acceptedAliases": ["shap", "lime", "integrated_gradients", "ig", "permutation"],
                },
            },
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        from app.models.xai import ExplanationMethod, ExplanationRequest, ExplanationScope

        from app.predictive.telemetry_simulator import generate_episode

        history = generate_episode(asset_id=asset_id).frames[:24]
        explanation = await xai_engine.explain(
            ExplanationRequest(
                asset_id=asset_id,
                explanation_id=prediction_id,
                method=ExplanationMethod(resolved_method),
                scope=ExplanationScope.LOCAL,
            ),
            history,
        )
        # requested_method tailors the structural payload (feature
        # descriptors, method echo) to the requested explainability method.
        payload = adapt_explainability_payload(
            explanation=explanation,
            prediction_id=prediction_id,
            asset_id=asset_id,
            requested_method=resolved_method,
        )
        payload["waterfall"] = format_shap_waterfall(
            payload["features"], base_value=payload["baseValue"]
        )
        payload["forcePlot"] = format_shap_force_plot(
            payload["features"],
            base_value=payload["baseValue"],
            prediction_value=payload["predictionValue"],
        )
        # Phase 2 — strict non-null array protection prior to serialization.
        payload = sanitize_arrays(payload)
        UIShapExplanation.model_validate(payload)
        return _ui_response(data=payload, request_id=request_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("explain failed for %s", prediction_id)
        return _ui_response(
            data={
                "predictionId": prediction_id,
                "assetId": asset_id,
                "baseValue": 0.0,
                "predictionValue": 0.0,
                "features": [],
                "confidenceMatrix": [],
                "rootCause": {},
            },
            request_id=request_id,
            success=False,
            error={"code": "XAI_FAILED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 4. Recommendations
# ===========================================================================
@ui_router.post(
    "/recommendations",
    response_model=UIAPIResponse[List[Dict[str, Any]]],
    summary="Prescriptive-action card panel payload",
    description=(
        "Returns a list of action cards ordered by ``rank`` (ascending). "
        "Each card is a flattened, card-friendly view of the Phase 8 "
        "Recommendation model."
    ),
)
async def recommendations(
    body: Dict[str, Any],
    request: Request,
    decision_engine: Any = _LazyEngineDep("get_decision_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        from app.models.decision import RecommendationRequest

        req = RecommendationRequest(
            asset_id=str(body.get("asset_id", "P-101A")),
            component_id=body.get("component_id"),
            risk_horizon_days=int(body.get("risk_horizon_days", 30)),
            max_recommendations=int(body.get("max_recommendations", 5)),
        )
        response = await decision_engine.recommend(req)
        actions = adapt_recommendations_to_actions(response)
        return _ui_response(
            data=actions,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("recommendations failed")
        return _ui_response(
            data=[],
            request_id=request_id,
            success=False,
            error={"code": "DECISION_FAILED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 5. Agent chat (non-streaming)
# ===========================================================================
@ui_router.post(
    "/agent/chat",
    response_model=UIAPIResponse[Dict[str, Any]],
    summary="Multi-agent chat panel payload (non-streaming)",
    description=(
        "Runs the Phase 9 LangGraph-style diagnostic agent turn and returns "
        "the final answer plus a Section 11 ``UIChat`` message envelope."
    ),
)
async def agent_chat(
    body: Dict[str, Any],
    request: Request,
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        from app.ai_service.schemas import (
            AgentChatMessage,
            AgentChatRequest,
            AgentRole,
        )
        from app.ai_service.agent_runtime import run_agent_chat

        messages_raw = body.get("messages", [])
        messages = [
            AgentChatMessage(
                role=AgentRole(str(m.get("role", "user")).lower()),
                content=str(m.get("content", "")),
            )
            for m in messages_raw
            if m.get("content")
        ]
        if not messages:
            return _ui_response(
                data={},
                request_id=request_id,
                success=False,
                error={
                    "code": "INVALID_REQUEST",
                    "message": "At least one message is required.",
                    "details": {"field": "messages"},
                },
            )
        req = AgentChatRequest(
            session_id=body.get("session_id"),
            asset_id=body.get("asset_id"),
            messages=messages,
            stream=False,
            include_graph_context=bool(body.get("include_graph_context", True)),
            include_recommendations=bool(body.get("include_recommendations", True)),
        )
        response = await run_agent_chat(req)
        chat = to_ui_chat_message(response)
        chat["states"] = [s.model_dump(mode="json") for s in response.states]
        return _ui_response(data=chat, request_id=request_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_chat failed")
        return _ui_response(
            data={},
            request_id=request_id,
            success=False,
            error={"code": "AGENT_FAILED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 6. Agent chat (streaming NDJSON)
# ============================================================================
@ui_router.post(
    "/agent/chat/stream",
    summary="Multi-agent chat NDJSON stream",
    description=(
        "Returns a newline-delimited JSON stream of ``AgentStreamEvent`` "
        "blocks. Each line is a fully serialised event — the front-end's "
        "``ReadableStream`` reader iterates them and appends chips to the "
        "timeline / tool-execution / source-chip / sub-graph panels in "
        "real time."
    ),
)
async def agent_chat_stream(
    body: Dict[str, Any],
    request: Request,
) -> StreamingResponse:
    request_id = _request_id(request)
    try:
        from app.ai_service.schemas import (
            AgentChatMessage,
            AgentChatRequest,
            AgentRole,
        )
        from app.ai_service.agent_runtime import run_agent_chat

        messages_raw = body.get("messages", [])
        messages = [
            AgentChatMessage(
                role=AgentRole(str(m.get("role", "user")).lower()),
                content=str(m.get("content", "")),
            )
            for m in messages_raw
            if m.get("content")
        ]
        req = AgentChatRequest(
            session_id=body.get("session_id"),
            asset_id=body.get("asset_id"),
            messages=messages,
            stream=True,
            include_graph_context=bool(body.get("include_graph_context", True)),
            include_recommendations=bool(body.get("include_recommendations", True)),
        )
        response = await run_agent_chat(req)

        async def event_iter() -> AsyncIterator[bytes]:
            async for block in to_chat_event_stream(
                response.states, session_id=response.session_id, asset_id=response.asset_id
            ):
                import json as _json

                yield (_json.dumps(block, default=str) + "\n").encode("utf-8")

        return StreamingResponse(
            event_iter(),
            media_type="application/x-ndjson",
            headers={
                "x-request-id": request_id,
                "x-ai-module": "phase-11-ui",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_chat_stream failed")

        async def error_iter() -> AsyncIterator[bytes]:
            import json as _json

            yield _json.dumps(
                {
                    "eventType": "error",
                    "isError": True,
                    "message": str(exc),
                    "requestId": request_id,
                }
            ).encode("utf-8") + b"\n"

        return StreamingResponse(
            error_iter(),
            media_type="application/x-ndjson",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"x-request-id": request_id},
        )


# ===========================================================================
# 7. CORS / preflight probe
# ===========================================================================
@ui_router.get(
    "/cors-check",
    summary="Verify CORS allow-list for the Next.js frontend",
    description=(
        "Returns 200 when the configured CORS allow-list includes the "
        "documented Next.js origins (``http://localhost:3000`` and the "
        "production host). Returns 503 + remediation message otherwise. "
        "Use from CI to catch CORS misconfiguration before Member 4 "
        "discovers it in the browser console."
    ),
)
async def cors_check(request: Request) -> JSONResponse:
    request_id = _request_id(request)
    try:
        verify_cors_configuration(_get_cors_origins())
        return _ui_response(
            data={
                "status": "ok",
                "allowedOrigins": _get_cors_origins(),
                "exposedHeaders": [
                    "content-type",
                    "x-request-id",
                    "x-correlation-id",
                    "x-ai-module",
                    "x-ai-version",
                ],
            },
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        return _ui_response(
            data={
                "status": "misconfigured",
                "allowedOrigins": _get_cors_origins(),
                "remediation": str(exc),
            },
            request_id=request_id,
            success=False,
            error={"code": "CORS_MISCONFIGURED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 8. Explicit OPTIONS preflight handler
# ===========================================================================
@ui_router.options(
    "/options",
    summary="CORS preflight probe (deterministic header echo)",
    description=(
        "Returns the exact CORS headers the AI UI endpoints will emit. "
        "Member 4 can call this from the browser console to verify "
        "header negotiation without running a real request."
    ),
)
async def preflight(request: Request) -> JSONResponse:
    request_id = _request_id(request)
    request_origin = request.headers.get("origin")
    origin = safe_cors_origin(request_origin, _get_cors_origins())
    headers = build_ui_preflight_headers(origin=origin)
    headers["x-request-id"] = request_id
    # Starlette's CORSMiddleware blindly appends to existing Vary headers via add_vary_header.
    # Pop Vary here so CORSMiddleware sets 'Vary: Origin' exactly once instead of 'Origin, Origin'.
    headers.pop("Vary", None)
    headers.pop("vary", None)
    return JSONResponse(status_code=204, content=None, headers=headers)


# ===========================================================================
# 9. Contract manifest (machine-readable)
# ===========================================================================
@ui_router.get(
    "/contracts",
    summary="Machine-readable contract manifest",
    description=(
        "Returns a JSON manifest of every Phase 11 UI endpoint, its "
        "request/response shape, and the source-of-truth component it "
        "feeds. Use to drive TypeScript type generation on the frontend."
    ),
)
async def contracts(request: Request) -> JSONResponse:
    request_id = _request_id(request)
    return _ui_response(
        data={
            "phase": "11-frontend-integration-support",
            "version": "0.11.0",
            "endpoints": [
                {
                    "path": "/api/v1/ai/ui/digital-twin/{asset_id}",
                    "method": "GET",
                    "feeds": "src/components/DigitalTwinView.tsx",
                    "schema": "UIDigitalTwinPayload",
                },
                {
                    "path": "/api/v1/ai/ui/graphrag/query",
                    "method": "POST",
                    "feeds": "src/components/GraphRagPanel.tsx",
                    "schema": "UIGraphRAGPayload",
                },
                {
                    "path": "/api/v1/ai/ui/explain/{prediction_id}",
                    "method": "GET",
                    "feeds": "src/components/ShapExplainability.tsx",
                    "schema": "UIShapExplanation",
                },
                {
                    "path": "/api/v1/ai/ui/recommendations",
                    "method": "POST",
                    "feeds": "prescriptive-action card panel",
                    "schema": "List[UIRecommendationAction]",
                },
                {
                    "path": "/api/v1/ai/ui/agent/chat",
                    "method": "POST",
                    "feeds": "multi-agent chat panel (non-streaming)",
                    "schema": "UIAPIResponse[UIChat]",
                },
                {
                    "path": "/api/v1/ai/ui/agent/chat/stream",
                    "method": "POST",
                    "feeds": "multi-agent chat panel (NDJSON stream)",
                    "schema": "AgentStreamEvent[] (NDJSON)",
                },
                {
                    "path": "/api/v1/ai/ui/cors-check",
                    "method": "GET",
                    "feeds": "CORS verification (CI / smoke test)",
                    "schema": "CORSStatus",
                },
                {
                    "path": "/api/v1/ai/ui/options",
                    "method": "OPTIONS",
                    "feeds": "Browser preflight probe",
                    "schema": "CORS preflight headers",
                },
                {
                    "path": "/api/v1/ai/ui/contracts",
                    "method": "GET",
                    "feeds": "Contract manifest for type generation",
                    "schema": "ContractManifest",
                },
            ],
        },
        request_id=request_id,
    )
