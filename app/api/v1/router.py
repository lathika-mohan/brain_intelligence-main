"""
Aggregated version-1 API router — Phase 0 Frozen & Hardened.
Phase 0 Enforcement:
- Only AI capabilities are PRIMARY (predictive, graphrag, xai, decision, vector)
- Phase 5A compatibility shims (auth, dashboard, assets, alerts, test) are FLAGGED as Gateway-owned
  and will be removed in Phase 0.5 after gateway provides same contract.
- Single Gateway Architecture: brain_intelligence is internal-only, mounted at /api/v1, gateway proxies via /api/v1/ai/*

Wiring matches existing repo but adds explicit PHASE0 markings.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Phase 5 — GraphRAG Engine (primary endpoint powering GraphRagPanel.tsx)
try:
    from app.api.v1.graphrag import router as graphrag_router
    logger.info("GraphRAG router loaded (Phase 5 hybrid engine) — FROZEN Phase0")
except Exception as e:  # pragma: no cover
    logger.warning("graphrag router import failed: %s", e)
    graphrag_router = APIRouter()

# Phase 0/2 — XAI router
try:
    from app.api.v1.xai import router as xai_router
    logger.info("XAI router loaded — FROZEN Phase0")
except Exception as e:  # pragma: no cover
    logger.warning("xai router import failed: %s", e)
    xai_router = APIRouter()

api_router = APIRouter()
api_router.include_router(graphrag_router)
api_router.include_router(xai_router)

# Stage 1 — Member 3 AI gateway relay routes (/api/v1/ai/*)
# app.api owns the contract-required /ai prefix; this registration connects
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
    logger.info("Vector search router mounted at /vector — FROZEN Phase0")
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
    logger.info("Predictive maintenance router mounted at /predictive — FROZEN Phase0")
except Exception as e:  # pragma: no cover
    logger.warning("predictive router not mounted: %s", e)

# Phase 8 — AI Decision Engine (prescriptive recommendations)
try:
    from app.api.v1.decision import router as decision_router
    api_router.include_router(decision_router)
    logger.info("Decision engine router mounted at /decision — FROZEN Phase0")
except Exception as e:  # pragma: no cover
    logger.warning("decision router not mounted: %s", e)

# Phase 10 — Isolated AI Service Integration router (/api/v1/ai/*)
try:
    from app.ai_service.main_router import ai_router
    api_router.include_router(ai_router)
    logger.info("Phase 10 AI service router mounted at /ai — FROZEN")
except Exception as e:  # pragma: no cover
    logger.warning("Phase 10 AI service router not mounted: %s", e)

# ------------------------------------------------------------------
# PHASE0 FLAGGED — DEPRECATED COMPATIBILITY SHIMS (Gateway-owned)
# These allow AI service to pass Stage 1,2,5 even when run standalone (port 8002)
# In full docker-compose, external gateway (iob-integration/gateway_app) also provides these.
# PHASE0 ACTION: Document as Gateway-owned, plan removal in Phase 0.5
# DO NOT ADD NEW ROUTES HERE — only frozen AI routes above.
# ------------------------------------------------------------------
try:
    from app.api.v1.auth import router as auth_router
    api_router.include_router(auth_router)
    logger.warning("PHASE0 FLAGGED SHIM: Auth router mounted at /auth — OWNERSHIP: Gateway Member 2, to be removed in Phase 0.5")
except Exception as e:
    logger.warning("auth router not mounted: %s", e)

try:
    from app.api.v1.dashboard import router as dashboard_router
    api_router.include_router(dashboard_router)
    logger.warning("PHASE0 FLAGGED SHIM: Dashboard router mounted at /dashboard — OWNERSHIP: Gateway Member 2")
except Exception as e:
    logger.warning("dashboard router not mounted: %s", e)

try:
    from app.api.v1.assets_router import router as assets_router
    api_router.include_router(assets_router)
    logger.warning("PHASE0 FLAGGED SHIM: Assets router mounted at /assets — OWNERSHIP: Gateway Member 2")
except Exception as e:
    logger.warning("assets_router not mounted: %s", e)

try:
    from app.api.v1.alerts import router as alerts_router
    api_router.include_router(alerts_router)
    logger.warning("PHASE0 FLAGGED SHIM: Alerts router mounted at /alerts — OWNERSHIP: Gateway Member 2")
except Exception as e:
    logger.warning("alerts router not mounted: %s", e)

try:
    from app.api.v1.test_inject import router as test_router
    api_router.include_router(test_router)
    logger.warning("PHASE0 FLAGGED SHIM: Test inject router mounted at /test — OWNERSHIP: Gateway Member 2")
except Exception as e:
    logger.warning("test_inject router not mounted: %s", e)
