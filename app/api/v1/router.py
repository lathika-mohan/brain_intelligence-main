"""
Aggregated version-1 API router.

Wires the implemented Phase 0/5 routers (GraphRAG engine + XAI contract)
behind the single ``api_router`` consumed by ``app.main:app`` at
``settings.api_v1_prefix`` (default ``/api/v1``).

Note: endpoints owned by other team members (decision engine, telemetry
ingestion, health) are intentionally **not** defined here — those are separate
deliverables and must not be stubbed out as placeholders. The GraphRAG
engine (Phase 5) binds the full hybrid pipeline into ``/graphrag``; the
Phase 6 Predictive Maintenance engine binds into ``/predictive``.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Phase 5 — GraphRAG Engine (primary endpoint powering GraphRagPanel.tsx)
try:
    from app.api.v1.graphrag import router as graphrag_router
    logger.info("GraphRAG router loaded (Phase 5 hybrid engine)")
except Exception as e:  # pragma: no cover
    logger.warning("graphrag router import failed: %s", e)
    graphrag_router = APIRouter()

# Phase 0/2 — XAI router
try:
    from app.api.v1.xai import router as xai_router
except Exception as e:  # pragma: no cover
    logger.warning("xai router import failed: %s", e)
    xai_router = APIRouter()

api_router = APIRouter()
api_router.include_router(graphrag_router)
api_router.include_router(xai_router)

# Phase 4 — Vector Search Service
try:
    from app.api.v1.vector_search import router as vector_search_router
    api_router.include_router(vector_search_router)
    logger.info("Vector search router mounted at /vector")
except Exception as e:  # pragma: no cover
    logger.warning("vector_search router not mounted: %s", e)

# Phase 3 — Document ingestion (optional, backend-ready)
try:
    from app.api.v1.document_ingestion import router as document_ingestion_router  # type: ignore
    api_router.include_router(document_ingestion_router)
    logger.info("Document ingestion router mounted")
except Exception:
    pass

# Phase 6 — Predictive Maintenance Engine (powers DigitalTwinView.tsx)
try:
    from app.api.v1.predictive import router as predictive_router
    api_router.include_router(predictive_router)
    logger.info("Predictive maintenance router mounted at /predictive")
except Exception as e:  # pragma: no cover
    logger.warning("predictive router not mounted: %s", e)
