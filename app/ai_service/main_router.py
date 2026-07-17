"""Phase 10 isolated FastAPI router for the AI Intelligence Platform."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, FastAPI, Path, Query, status
from fastapi.responses import StreamingResponse

from app.ai_service.agent_runtime import iter_agent_states, run_agent_chat
from app.ai_service.dependencies import (
    AIRuntimeConfig,
    get_ai_runtime,
    get_decision_engine,
    get_graphrag_engine,
    get_prediction_engine,
    get_xai_engine,
)
from app.ai_service.exceptions import (
    AIDependencyUnavailable,
    AIEngineTimeout,
    AIInvalidRequest,
    install_ai_exception_handlers,
)
from app.ai_service.schemas import (
    AIHealthResponse,
    AgentAIEnvelope,
    AgentChatRequest,
    ExplainAIEnvelope,
    ExplainFetchResponse,
    GraphRagAIEnvelope,
    PredictiveAIEnvelope,
    RecommendAIEnvelope,
)
from app.core.config import get_settings
from app.models.common import APIResponse
from app.models.decision import RecommendationRequest
from app.models.graphrag import GraphRagQueryRequest
from app.models.predictive import InferenceRequest
from app.models.xai import ExplanationMethod, ExplanationRequest, ExplanationScope

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ai_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Best-effort async lifecycle for Neo4j and Qdrant pools.

    Startup intentionally avoids failing the whole gateway if an AI dependency
    is temporarily unavailable; route-level service calls return sanitized
    503/504 responses via custom handlers.
    """

    app.state.ai_neo4j_driver = None
    app.state.ai_qdrant_client = None
    try:
        try:
            from neo4j import AsyncGraphDatabase
            from app.graph.client import _driver_config

            settings = get_settings()
            # Construct the async pool without an eager connectivity probe so the
            # enterprise gateway can boot even when an offline CI/test runner has
            # no Neo4j container. Route-level services still verify/use the pool.
            app.state.ai_neo4j_driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                **_driver_config(),
            )
            logger.info("Phase 10 lifespan initialized Neo4j driver pool.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j startup degraded: %s", exc)

        try:
            from app.vector.client import get_qdrant_client

            app.state.ai_qdrant_client = get_qdrant_client()
            logger.info("Phase 10 lifespan initialized Qdrant client.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant startup degraded: %s", exc)
        yield
    finally:
        try:
            driver = getattr(app.state, "ai_neo4j_driver", None)
            if driver is not None:
                await driver.close()
            from app.graph.client import GraphDriverManager

            await GraphDriverManager.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Neo4j shutdown skipped: %s", exc)
        try:
            from app.vector.client import close_qdrant_client

            close_qdrant_client()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Qdrant shutdown skipped: %s", exc)


ai_router = APIRouter(
    prefix="/ai",
    tags=["AI Platform"],
    responses={
        422: {"description": "Pydantic validation error or semantic AI request error"},
        503: {"description": "AI dependency temporarily unavailable"},
        504: {"description": "AI engine timeout"},
    },
)


@ai_router.get(
    "/health",
    response_model=AIHealthResponse,
    summary="AI module health and dependency readiness",
    description="Returns readiness for the isolated Phase 10 AI service boundary.",
)
async def health(runtime: Annotated[AIRuntimeConfig, Depends(get_ai_runtime)]) -> AIHealthResponse:
    settings = runtime.settings
    deps = {
        "neo4j_pool_initialized": runtime.neo4j_driver is not None,
        "qdrant_client_initialized": runtime.qdrant_client is not None,
        "llm_provider": settings.llm_provider,
        "embedding_model": settings.embedding_model_name,
    }
    return AIHealthResponse(status="ready" if any(deps.values()) else "degraded", version="0.10.0", dependencies=deps)


@ai_router.post(
    "/query",
    response_model=GraphRagAIEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Run GraphRAG query",
    description="Wraps the Phase 5 hybrid GraphRAG engine and returns answer text, vector chunks, citations, and graph visualization nodes/edges.",
)
async def query_graphrag(
    body: GraphRagQueryRequest,
    engine: Annotated[Any, Depends(get_graphrag_engine)],
) -> GraphRagAIEnvelope:
    request_id = str(uuid.uuid4())
    try:
        result = await engine.query(body)
        return APIResponse(success=True, data=result, request_id=request_id)
    except TimeoutError as exc:
        raise AIEngineTimeout(details={"engine": "graphrag"}) from exc
    except ValueError as exc:
        raise AIInvalidRequest(str(exc), details={"engine": "graphrag"}) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("GraphRAG /ai/query failed")
        raise AIDependencyUnavailable(details={"engine": "graphrag"}) from exc


@ai_router.post(
    "/predict",
    response_model=PredictiveAIEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Run predictive maintenance inference",
    description="Routes live telemetry through Phase 6 feature engineering and inference to return RUL, failure probability, and anomaly matrices.",
)
async def predict_maintenance(
    body: InferenceRequest,
    engine: Annotated[Any, Depends(get_prediction_engine)],
) -> PredictiveAIEnvelope:
    request_id = str(uuid.uuid4())
    try:
        result = await engine.infer(body)
        return APIResponse(success=True, data=result, request_id=request_id)
    except ValueError as exc:
        raise AIInvalidRequest(str(exc), details={"engine": "predictive"}) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Predictive /ai/predict failed")
        raise AIDependencyUnavailable(details={"engine": "predictive"}) from exc


@ai_router.get(
    "/explain/{prediction_id}",
    response_model=ExplainAIEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Fetch or compute explainability for a prediction",
    description="Computes/fetches SHAP/LIME rankings, root causes, and confidence vectors for ShapExplainability.tsx.",
)
async def explain_prediction(
    prediction_id: Annotated[str, Path(min_length=1, description="Prediction/explanation correlation id")],
    engine: Annotated[Any, Depends(get_xai_engine)],
    asset_id: Annotated[str, Query(min_length=1, description="Asset id associated with the prediction")] = "P-101A",
    method: Annotated[ExplanationMethod, Query(description="Explanation method")] = ExplanationMethod.SHAP,
    scope: Annotated[ExplanationScope, Query(description="Explanation scope")] = ExplanationScope.LOCAL,
) -> ExplainAIEnvelope:
    request_id = str(uuid.uuid4())
    try:
        from app.predictive.telemetry_simulator import generate_episode

        history = generate_episode(asset_id=asset_id).frames[:24]
        explanation = await engine.explain(
            ExplanationRequest(asset_id=asset_id, explanation_id=prediction_id, method=method, scope=scope),
            history,
        )
        return APIResponse(success=True, data=ExplainFetchResponse(prediction_id=prediction_id, explanation=explanation), request_id=request_id)
    except ValueError as exc:
        raise AIInvalidRequest(str(exc), details={"engine": "xai"}) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("XAI /ai/explain failed")
        raise AIDependencyUnavailable(details={"engine": "xai"}) from exc


@ai_router.post(
    "/recommend",
    response_model=RecommendAIEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Generate risk-ranked maintenance recommendations",
    description="Evaluates asset risk and returns SOP-backed prescriptive checklists from the Phase 8 decision engine.",
)
async def recommend_actions(
    body: RecommendationRequest,
    engine: Annotated[Any, Depends(get_decision_engine)],
) -> RecommendAIEnvelope:
    request_id = str(uuid.uuid4())
    try:
        result = await engine.recommend(body)
        return APIResponse(success=True, data=result, request_id=request_id)
    except ValueError as exc:
        raise AIInvalidRequest(str(exc), details={"engine": "decision"}) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Decision /ai/recommend failed")
        raise AIDependencyUnavailable(details={"engine": "decision"}) from exc


@ai_router.post(
    "/agent/chat",
    response_model=AgentAIEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Run structured diagnostic agent chat",
    description="Returns LangGraph-style diagnostic states for multi-turn support. Set stream=true for NDJSON state streaming.",
)
async def agent_chat(
    body: AgentChatRequest,
    graphrag_engine: Annotated[Any, Depends(get_graphrag_engine)],
    decision_engine: Annotated[Any, Depends(get_decision_engine)],
):
    async def factory():
        return await run_agent_chat(body, graphrag_engine=graphrag_engine, decision_engine=decision_engine)

    if body.stream:
        return StreamingResponse(iter_agent_states(factory), media_type="application/x-ndjson")
    request_id = str(uuid.uuid4())
    result = await factory()
    return APIResponse(success=True, data=result, request_id=request_id)


def create_ai_service_app() -> FastAPI:
    """Create a standalone FastAPI app exposing only the Phase 10 AI router."""

    app = FastAPI(
        title="IOB AI Service Integration",
        version="0.10.0",
        description="Isolated FastAPI surface for GraphRAG, PdM inference, XAI, decision recommendations, and diagnostic agents.",
        lifespan=ai_lifespan,
    )
    install_ai_exception_handlers(app)
    app.include_router(ai_router, prefix="/api/v1")
    return app
