"""Phase 11 — UI-shaped FastAPI sub-router.
Phase 2 Recovery — Router Recovery & Mount Verification

Mounts at ``/api/v1/ai/ui`` and exposes the *frontend contract* projection
of the same engines that power the raw ``/api/v1/ai/*`` endpoints.

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

Phase 2 Recovery Changes:
- Replaces Dict[str, Any] untyped payloads with explicit Pydantic request models
  from app.ai_service.integration.schemas.ui_request_schemas
- Restores missing request/response models for OpenAPI generation
- Ensures operation_ids are unique and tags are explicit
- No silent try/except masking at import/mount time — only per-request degraded fallback
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.ai_service.middleware import get_request_id, make_ui_contract_route
from app.ai_service.responses import create_ui_response
from app.ai_service.integration.adapters.chat_event_adapter import (
    to_chat_event_stream,
    to_ui_chat_message,
)
from app.ai_service.integration.adapters.frontend_adapters import (
    adapt_digital_twin_payload,
    adapt_explainability_payload,
    adapt_graphrag_payload,
    adapt_recommendations_to_actions,
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
    format_shap_force_plot,
    format_shap_waterfall,
)
# Phase 2 Recovery: Explicit response models for OpenAPI
from app.ai_service.integration.schemas.ui_schemas import (
    UIAPIResponse,
    UIChat,
    UIDigitalTwinPayload,
    UIGraphRAGPayload,
    UIRecommendationAction,
    UIShapExplanation,
)
# Phase 2 Recovery: Explicit request models (replaces Dict[str, Any])
from app.ai_service.integration.schemas.ui_request_schemas import (
    UIAgentChatRequest,
    UIAgentChatStreamRequest,
    UIGraphRAGQueryRequest,
    UIRecommendationRequest,
)

logger = logging.getLogger(__name__)


def _get_cors_origins() -> List[str]:
    """Return the configured CORS origins, falling back to documented defaults."""
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
    route_class=make_ui_contract_route(module="phase-11-ui"),
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
    """A FastAPI ``Depends`` wrapper that defers ``dependencies`` import."""

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
    """Use the request id resolved once by the UI contract route."""
    return get_request_id(request)


def _ui_response(
    *,
    data: Any = None,
    request_id: str,
    success: bool = True,
    error: Optional[Dict[str, Any]] = None,
    status_code: Optional[int] = None,
) -> JSONResponse:
    """Return the sole UI JSON response format via the shared helper."""
    return create_ui_response(
        data=data,
        request_id=request_id,
        success=success,
        error=error,
        module="phase-11-ui",
        status_code=status_code,
    )


# ===========================================================================
# 1. Digital Twin — fixed response_model to explicit payload
# ===========================================================================
@ui_router.get(
    "/digital-twin/{asset_id}",
    response_model=UIAPIResponse[UIDigitalTwinPayload],
    summary="DigitalTwinView.tsx payload",
    description=(
        "Returns the asset + live telemetry + chronological history shape "
        "consumed by ``src/components/DigitalTwinView.tsx``. Drives the "
        "rotational-speed / vibration / pressure / AI-risk cards and the "
        "SVG schematic."
    ),
    operation_id="ui_get_digital_twin",
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
# 2. GraphRAG — Phase 2 Recovery: explicit Pydantic request model
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
    operation_id="ui_post_graphrag_query",
)
async def graphrag_query(
    body: UIGraphRAGQueryRequest,
    request: Request,
    graphrag_engine: Any = _LazyEngineDep("get_graphrag_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        from app.models.graphrag import GraphRagQueryRequest

        resolved_query = body.resolved_query_text()
        resolved_asset = body.resolved_asset_id()

        req = GraphRagQueryRequest(
            query_text=resolved_query or "diagnose asset",
            asset_id=resolved_asset,
            top_k=int(body.top_k),
        )
        response = await graphrag_engine.query(req)
        payload = adapt_graphrag_payload(response, query=req.query_text)
        payload["badge"] = confidence_to_badge(payload["confidence"]).value
        payload["warningLevel"] = confidence_to_warning_level(payload["confidence"])
        payload["color"] = confidence_to_color(payload["confidence"])
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
# 3. SHAP / LIME explainability — already typed query params
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
    operation_id="ui_get_explain",
)
async def explain(
    prediction_id: Annotated[str, Path(min_length=1)],
    request: Request,
    asset_id: Annotated[str, Query(min_length=1)] = "P-101A",
    method: Annotated[str, Query(pattern="^(SHAP|LIME|INTEGRATED_GRADIENTS|PERMUTATION)$")] = "SHAP",
    xai_engine: Any = _LazyEngineDep("get_xai_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        from app.models.xai import ExplanationMethod, ExplanationRequest, ExplanationScope
        from app.predictive.telemetry_simulator import generate_episode

        history = generate_episode(asset_id=asset_id).frames[:24]
        # Phase 2: support lower-case and alias normalization
        method_normalized = method.upper()
        try:
            method_enum = ExplanationMethod(method_normalized)
        except ValueError:
            # allow lowercase LIME etc via case-insensitive fallback
            method_enum = ExplanationMethod[method_normalized]

        explanation = await xai_engine.explain(
            ExplanationRequest(
                asset_id=asset_id,
                explanation_id=prediction_id,
                method=method_enum,
                scope=ExplanationScope.LOCAL,
            ),
            history,
        )
        payload = adapt_explainability_payload(
            explanation=explanation, prediction_id=prediction_id, asset_id=asset_id
        )
        # Enrich with explicit Phase 2 waterfall/forcePlot structures
        payload["waterfall"] = format_shap_waterfall(
            payload["features"], base_value=payload["baseValue"]
        )
        payload["forcePlot"] = format_shap_force_plot(
            payload["features"],
            base_value=payload["baseValue"],
            prediction_value=payload["predictionValue"],
        )
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
# 4. Recommendations — Phase 2 Recovery: explicit Pydantic request model
# ===========================================================================
@ui_router.post(
    "/recommendations",
    response_model=UIAPIResponse[List[UIRecommendationAction]],
    summary="Prescriptive-action card panel payload",
    description=(
        "Returns a list of action cards ordered by ``rank`` (ascending). "
        "Each card is a flattened, card-friendly view of the Phase 8 "
        "Recommendation model."
    ),
    operation_id="ui_post_recommendations",
)
async def recommendations(
    body: UIRecommendationRequest,
    request: Request,
    decision_engine: Any = _LazyEngineDep("get_decision_engine"),
) -> JSONResponse:
    request_id = _request_id(request)
    try:
        from app.models.decision import RecommendationRequest

        req = RecommendationRequest(
            asset_id=body.resolved_asset_id(),
            component_id=body.resolved_component_id(),
            risk_horizon_days=body.resolved_risk_horizon(),
            max_recommendations=body.resolved_max_rec(),
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
            error={"code": "RECOMMEND_FAILED", "message": str(exc), "details": None},
        )


# ===========================================================================
# 5. Agent chat (non-streaming) — Phase 2 Recovery: explicit request model
# ===========================================================================
@ui_router.post(
    "/agent/chat",
    response_model=UIAPIResponse[UIChat],
    summary="Agent chat — non-streaming",
    description="Returns a single UIChat message with final_answer and states.",
    operation_id="ui_post_agent_chat",
)
async def agent_chat(
    body: UIAgentChatRequest,
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

        # Validate messages not empty / blank per test_contract expectation
        if not body.messages:
            return _ui_response(
                data={},
                request_id=request_id,
                success=False,
                error={"code": "INVALID_REQUEST", "message": "messages must not be empty", "details": None},
            )
        # Check for whitespace-only content
        if all(not (m.content or "").strip() for m in body.messages):
            return _ui_response(
                data={},
                request_id=request_id,
                success=False,
                error={"code": "INVALID_REQUEST", "message": "messages content blank", "details": None},
            )

        messages = [
            AgentChatMessage(
                role=AgentRole(str(m.role).lower()),
                content=str(m.content),
            )
            for m in body.messages
            if (m.content or "").strip()
        ]

        session_id = body.resolved_session_id() or str(uuid.uuid4())
        asset_id = body.resolved_asset_id()

        req = AgentChatRequest(
            session_id=session_id,
            asset_id=asset_id,
            messages=messages,
            stream=False,
            include_graph_context=body.resolved_include_graph(),
            include_recommendations=body.resolved_include_recs(),
        )
        response = await run_agent_chat(req)

        chat = to_ui_chat_message(response)
        chat["sessionId"] = session_id
        chat["messageId"] = chat.get("messageId") or f"msg-{session_id}"
        chat["reply"] = response.final_answer or ""
        chat["payload"] = response.final_answer or ""
        chat["timestamp"] = chat.get("timestamp") or datetime.now(timezone.utc).isoformat()
        chat["suggestedActions"] = []
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
# 6. Agent chat (streaming NDJSON) — Phase 2 Recovery: explicit request model
# ===========================================================================
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
    operation_id="ui_post_agent_chat_stream",
)
async def agent_chat_stream(
    body: UIAgentChatStreamRequest,
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

        messages = [
            AgentChatMessage(
                role=AgentRole(str(m.role).lower()),
                content=str(m.content or ""),
            )
            for m in body.messages
            if (m.content or "").strip()
        ]

        session_id = body.resolved_session_id() or str(uuid.uuid4())

        req = AgentChatRequest(
            session_id=session_id,
            asset_id=body.resolved_asset_id(),
            messages=messages,
            stream=True,
            include_graph_context=True,
            include_recommendations=True,
        )
        response = await run_agent_chat(req)

        async def event_iter() -> AsyncIterator[bytes]:
            seq_num = 1
            async for block in to_chat_event_stream(
                response.states, session_id=response.session_id, asset_id=response.asset_id
            ):
                import json as _json

                block["seq"] = seq_num
                event_type = block.get("eventType")
                if event_type == "heartbeat":
                    block["type"] = "ping"
                elif seq_num == 2 or (seq_num == 1 and event_type != "heartbeat"):
                    block["type"] = "start"
                elif block.get("isFinal") or event_type == "final":
                    block["type"] = "done"
                    block["metadata"] = block.get("payload") or {}
                else:
                    block["type"] = "delta"
                    block["content"] = block.get("message") or ""

                seq_num += 1
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
            headers={"x-request-id": request_id, "x-ai-module": "phase-11-ui"},
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
    operation_id="ui_get_cors_check",
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
    operation_id="ui_options_preflight",
)
async def preflight(request: Request) -> JSONResponse:
    request_id = _request_id(request)
    request_origin = request.headers.get("origin")
    origin = safe_cors_origin(request_origin, _get_cors_origins())
    headers = build_ui_preflight_headers(origin=origin)
    headers["x-request-id"] = request_id
    headers["x-ai-module"] = "phase-11-ui"
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
    operation_id="ui_get_contracts",
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
