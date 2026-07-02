"""Aggregates every v1 sub-router into a single APIRouter mounted by app.main."""
from fastapi import APIRouter

from app.api.v1 import decision, graphrag, health, ingestion, predictive, xai

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(graphrag.router)
api_router.include_router(predictive.router)
api_router.include_router(xai.router)
api_router.include_router(decision.router)
