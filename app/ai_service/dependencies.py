"""FastAPI dependency providers for Phase 10 AI service routes."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Request

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AIRuntimeConfig:
    """Runtime knobs injected into endpoints via ``Depends``."""

    settings: Settings
    neo4j_driver: Optional[Any] = None
    qdrant_client: Optional[Any] = None


async def get_ai_runtime(request: Request) -> AIRuntimeConfig:
    """Return resources created by the AI router/app lifespan.

    The lifecycle is best-effort: if Neo4j or Qdrant is not reachable during
    startup, endpoints still mount and individual services can degrade or raise
    a sanitized ``AIDependencyUnavailable``.
    """

    state = request.app.state
    return AIRuntimeConfig(
        settings=get_settings(),
        neo4j_driver=getattr(state, "ai_neo4j_driver", None),
        qdrant_client=getattr(state, "ai_qdrant_client", None),
    )


def get_graphrag_engine():
    from app.graphrag.graph_rag_service import get_graphrag_service

    return get_graphrag_service()


def get_prediction_engine():
    from app.predictive.prediction_service import get_prediction_service

    return get_prediction_service()


def get_xai_engine():
    from app.predictive.xai_service import get_xai_service

    return get_xai_service()


def get_decision_engine():
    from app.decision.decision_service import get_decision_service

    return get_decision_service()
