"""
FastAPI application entrypoint for the IOB AI Intelligence Platform.

Run locally:
    uvicorn app.main:app --reload --port 8000

Mounts the versioned API router at `settings.api_v1_prefix` (default
`/api/v1`), matching the frontend's existing `NEXT_PUBLIC_API_URL`
convention documented in the repo root `.env.example`
(`https://api.iob.enterprise.internal/v1`).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.ai_service.exceptions import install_ai_exception_handlers
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Industrial Operating Brain (IOB) — AI Intelligence Platform. "
        "Phase 0: frozen API contracts. Phase 1: industrial knowledge ontology "
        "for GraphRAG, Predictive Maintenance, XAI, and Decision support."
    ),
    debug=settings.debug,
)

install_ai_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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
        "docs": "/docs",
        "api_prefix": settings.api_v1_prefix,
    }
