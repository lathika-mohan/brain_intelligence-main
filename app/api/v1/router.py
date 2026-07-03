"""
Aggregated version-1 API router.

Wires the implemented Phase 0 stub routers (GraphRAG contract + XAI contract)
behind the single ``api_router`` consumed by ``app.main:app`` at
``settings.api_v1_prefix`` (default ``/api/v1``).

Note: endpoints owned by other team members (decision engine, predictive,
ingestion, health) are intentionally **not** defined here — those are separate
deliverables and must not be stubbed out as placeholders in Phase 2. The
GraphRAG/decision engine will later bind the ``app.graph`` services built in
Phase 2 into ``/graphrag`` once the fusion pipeline lands.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.graphrag import router as graphrag_router
from app.api.v1.xai import router as xai_router

api_router = APIRouter()
api_router.include_router(graphrag_router)
api_router.include_router(xai_router)
