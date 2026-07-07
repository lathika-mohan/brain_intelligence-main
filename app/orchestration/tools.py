"""Validated tool adapters that wrap Phases 2-8 behind agent-local methods."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.decision import RecommendationRequest, RecommendationResponse
from app.models.graphrag import GraphRagContextChunk, GraphRagEdge, GraphRagNode
from app.models.predictive import InferenceRequest, InferenceResponse
from app.models.telemetry import TelemetryReading
from app.models.xai import ExplanationRequest, ExplanationResponse

logger = logging.getLogger(__name__)


class KnowledgeQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(..., min_length=1)
    max_hops: int = Field(default=3, ge=1, le=5)


class RetrievalQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_text: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    asset_id: Optional[str] = None
    min_score: float = Field(default=0.55, ge=0.0, le=1.0)


class PredictionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(..., min_length=1)
    component_id: Optional[str] = None
    history: List[TelemetryReading] = Field(..., min_length=1)
    horizon_hours: int = Field(default=720, ge=1, le=2160)


class ExplanationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(..., min_length=1)
    explanation_id: Optional[str] = None
    history: List[TelemetryReading] = Field(..., min_length=1)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(..., min_length=1)
    component_id: Optional[str] = None
    risk_horizon_days: int = Field(default=30, ge=1, le=365)
    max_recommendations: int = Field(default=5, ge=1, le=20)


class KnowledgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_nodes: List[GraphRagNode] = Field(default_factory=list)
    graph_edges: List[GraphRagEdge] = Field(default_factory=list)
    graph_nodes_expanded: int = 0
    fallback_used: bool = False


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_chunks: List[GraphRagContextChunk] = Field(default_factory=list)
    vector_hits: int = 0
    query_embedding_model: str = ""
    fallback_used: bool = False


class ToolRegistry:
    """Agent-local tools backed by previously implemented backend services."""

    async def query_knowledge_graph(self, payload: KnowledgeQueryInput) -> KnowledgeResult:
        try:
            from app.graph.client import GraphDriverManager
            if not (hasattr(GraphDriverManager, "_driver") and GraphDriverManager._driver is not None):
                raise RuntimeError("Neo4j driver is not initialized")
            from app.graph.graph_services import GraphAPIService
            graph_api = await GraphAPIService.connect()
            context = await graph_api.query.get_asset_subgraph(payload.asset_id, payload.max_hops)
            nodes = [
                GraphRagNode(id=n.id, label=n.display_name or n.label, type=n.label, properties=n.properties)
                for n in context.nodes
            ]
            edges = [
                GraphRagEdge(source=e.source_id, target=e.target_id, relationship=e.relationship)
                for e in context.edges
            ]
            return KnowledgeResult(graph_nodes=nodes, graph_edges=edges, graph_nodes_expanded=len(nodes))
        except Exception as exc:
            logger.debug("Knowledge graph fallback for %s: %s", payload.asset_id, exc)
            return KnowledgeResult(
                graph_nodes=[
                    GraphRagNode(
                        id=payload.asset_id,
                        label=payload.asset_id,
                        type="Asset",
                        properties={"source": "orchestrator_fallback"},
                    )
                ],
                graph_nodes_expanded=1,
                fallback_used=True,
            )

    async def semantic_retrieve(self, payload: RetrievalQueryInput) -> RetrievalResult:
        try:
            from app.vector.search_service import get_search_service
            service = get_search_service()
            response = await service.semantic_search(
                payload.query_text,
                top_k=payload.top_k,
                score_threshold=payload.min_score,
            )
            chunks = [
                GraphRagContextChunk(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    score=r.score,
                    document_type=r.document_type,
                    source=r.source_filename or r.document_id,
                )
                for r in response.results
            ]
            return RetrievalResult(
                context_chunks=chunks,
                vector_hits=response.returned,
                query_embedding_model=response.embedding_model,
            )
        except Exception as exc:
            logger.debug("Vector retrieval fallback: %s", exc)
            asset = f" for {payload.asset_id}" if payload.asset_id else ""
            return RetrievalResult(
                context_chunks=[
                    GraphRagContextChunk(
                        chunk_id="fallback-context-1",
                        text=(
                            f"Offline fallback context{asset}: inspect recent pressure, vibration, "
                            "bearing temperature and load trends; compare against SOP limits."
                        ),
                        score=0.5,
                        document_type="FALLBACK_GUIDANCE",
                        source="phase9_orchestrator",
                    )
                ],
                vector_hits=1,
                fallback_used=True,
            )

    async def predict(self, payload: PredictionInput) -> InferenceResponse:
        from app.predictive.prediction_service import get_prediction_service
        service = get_prediction_service()
        return await service.infer(
            InferenceRequest(
                asset_id=payload.asset_id,
                component_id=payload.component_id,
                history=payload.history,
                horizon_hours=payload.horizon_hours,
            )
        )

    async def explain(self, payload: ExplanationInput) -> ExplanationResponse:
        from app.predictive.xai_service import get_xai_service
        service = get_xai_service()
        return await service.explain(
            ExplanationRequest(asset_id=payload.asset_id, explanation_id=payload.explanation_id),
            payload.history,
        )

    async def decide(self, payload: DecisionInput) -> RecommendationResponse:
        from app.decision.decision_service import get_decision_service
        service = get_decision_service()
        return await service.recommend(
            RecommendationRequest(
                asset_id=payload.asset_id,
                component_id=payload.component_id,
                risk_horizon_days=payload.risk_horizon_days,
                max_recommendations=payload.max_recommendations,
            )
        )


def fallback_history(asset_id: str) -> List[TelemetryReading]:
    from app.predictive.telemetry_simulator import generate_episode
    return generate_episode(asset_id=asset_id).frames[:24]
