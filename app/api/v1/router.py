"""
Aggregated version-1 API router.

Phase 5A patched: includes gateway-compatible endpoints (Auth, Assets, Dashboard, Alerts, Test Inject)
so that AI service can be tested stand-alone or behind gateway.

Wires GraphRAG, XAI, Predictive, Decision, Vector Search, Document Ingestion, plus Phase 5A integration routers.

Note: For full integration, Member 1 gateway (iob-integration/gateway_app) provides same endpoints and proxies to this service.
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

# Stage 1 — Member 3 AI gateway relay routes (/api/v1/ai/*)
# app.api owns the contract-required `/ai` prefix; this registration connects
# it to the repository's existing versioned router without disturbing any
# previously mounted API modules.
try:
    from app.api import router as ai_gateway_router

    api_router.include_router(ai_gateway_router)
    logger.info("Stage 1 AI gateway router mounted at /ai")
except Exception as e:  # pragma: no cover
    logger.warning("Stage 1 AI gateway router not mounted: %s", e)

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

# Phase 8 — AI Decision Engine (prescriptive recommendations)
try:
    from app.api.v1.decision import router as decision_router
    api_router.include_router(decision_router)
    logger.info("Decision engine router mounted at /decision")
except Exception as e:  # pragma: no cover
    logger.warning("decision router not mounted: %s", e)

# Phase 10 — Isolated AI Service Integration router (/api/v1/ai/*)
try:
    from app.ai_service.main_router import ai_router
    api_router.include_router(ai_router)
    logger.info("Phase 10 AI service router mounted at /ai")
except Exception as e:  # pragma: no cover
    logger.warning("Phase 10 AI service router not mounted: %s", e)

# Phase 5A — Integration Gateway Compatibility Routers (Auth, Dashboard, Assets, Alerts, Test)
# These allow the AI service to pass Stage 1,2,5 even when run standalone (port 8002)
# In full docker-compose, the external gateway (iob-integration/gateway_app) also provides these.
try:
    from app.api.v1.auth import router as auth_router
    api_router.include_router(auth_router)
    logger.info("Phase 5A Auth router mounted at /auth")
except Exception as e:
    logger.warning("auth router not mounted: %s", e)

try:
    from app.api.v1.dashboard import router as dashboard_router
    api_router.include_router(dashboard_router)
    logger.info("Phase 5A Dashboard router mounted at /dashboard")
except Exception as e:
    logger.warning("dashboard router not mounted: %s", e)

try:
    from app.api.v1.assets_router import router as assets_router
    api_router.include_router(assets_router)
    logger.info("Phase 5A Assets router mounted at /assets")
except Exception as e:
    logger.warning("assets_router not mounted: %s", e)

try:
    from app.api.v1.alerts import router as alerts_router
    api_router.include_router(alerts_router)
    logger.info("Phase 5A Alerts router mounted at /alerts")
except Exception as e:
    logger.warning("alerts router not mounted: %s", e)

try:
    from app.api.v1.test_inject import router as test_router
    api_router.include_router(test_router)
    logger.info("Phase 5A Test inject router mounted at /test")
except Exception as e:
    logger.warning("test_inject router not mounted: %s", e)
