"""
FastAPI application entrypoint for the IOB AI Intelligence Platform.
Phase 0 Hardened — Internal-Only Microservice
Run locally: uvicorn app.main:app --reload --port 8002 (note: 8002 internal, 8080 gateway)

- Mounts versioned API router at settings.api_v1_prefix (/api/v1)
- Enforces internal-only guard via X-Internal-Service-Token middleware (Phase 0)
- CORS locked to gateway origin in production, dev allows localhost:3000 via env
"""
from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.ai_service.exceptions import install_ai_exception_handlers
from app.core.config import get_settings
from app.api.middleware.internal_only_guard import InternalOnlyGuardMiddleware

settings = get_settings()

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Industrial Operating Brain (IOB) — AI Intelligence Platform. "
        "Phase 0: frozen API contracts, internal-only. "
        "Single Gateway: Frontend -> Gateway -> brain_intelligence. "
        "Owns Predictive, GraphRAG, XAI, Decision, Vector."
    ),
    debug=settings.debug,
    docs_url="/docs" if settings.app_env != "production" else None,  # hide docs in prod if internal-only
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

install_ai_exception_handlers(app)

<<<<<<< HEAD
# Phase 0: Internal-only guard — validates X-Internal-Service-Token or JWT service token
# Bypass for health/docs in dev
app.add_middleware(InternalOnlyGuardMiddleware)

# CORS — Phase 0 locked: gateway only in production, localhost + gateway in dev
# Existing .env CORS_ALLOW_ORIGINS includes dev frontend, but in production
# gateway should be sole origin that talks to AI directly.
cors_origins = settings.cors_origins_list
if settings.app_env == "production":
    # In prod, only gateway origin allowed to call AI internal
    # Frontend never calls AI direct
    cors_origins = [o for o in cors_origins if "3000" not in o]
    if not cors_origins:
        cors_origins = ["http://gateway:8080", "https://api.iob.enterprise.internal"]
    logger.info(f"Production CORS locked to gateway-only: {cors_origins}")
else:
    logger.info(f"Dev CORS origins (includes frontend for standalone testing): {cors_origins}")

=======
>>>>>>> f853400ee01fb2edf09eced421ba1c168941d6ee
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "phase": "0-frozen",
        "mode": "internal-only microservice",
        "docs": "/docs" if settings.app_env != "production" else "disabled in prod",
        "api_prefix": settings.api_v1_prefix,
        "pipeline": "Frontend -> Gateway -> AI Platform (brain_intelligence)",
        "embedding_lock": "all-mpnet-base-v2 768d Cosine operational_knowledge_v4",
        "ownership": {
            "owns": ["predictive", "graphrag", "xai", "decision", "vector", "ingestion"],
            "does_not_own": ["auth", "frontend UI", "public gateway", "assets/dashboard/alerts persistence"]
        }
    }

@app.get("/health", tags=["root"])
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version, "phase": "0-frozen"}
