"""Transparent FastAPI relay routes for the external AI platform."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter

from app.services.ai_client import call_ai

router = APIRouter()


@router.post("/predictive/infer")
async def predictive_infer(payload: dict[str, Any]) -> dict[str, Any]:
    """Relay predictive inference without modifying request or response fields."""
    return await call_ai("/api/v1/predictive/infer", payload=payload, method="POST")


@router.get("/predictive/{asset_id}/explain")
async def predictive_explain(asset_id: str) -> dict[str, Any]:
    """Relay an asset explainability request."""
    encoded_asset_id = quote(asset_id, safe="")
    return await call_ai(f"/api/v1/xai/explain?asset_id={encoded_asset_id}", method="GET")


@router.post("/graphrag/query")
async def graphrag_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Relay a GraphRAG query without transforming its JSON contract."""
    return await call_ai("/api/v1/graphrag/query", payload=payload, method="POST")


@router.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    """Relay an AI chat request without transforming its JSON contract."""
    return await call_ai("/api/v1/chat", payload=payload, method="POST")


@router.get("/knowledge/search")
async def knowledge_search(q: str) -> dict[str, Any]:
    """Relay a knowledge search query."""
    encoded_query = quote(q, safe="")
    return await call_ai(f"/api/v1/knowledge/search?q={encoded_query}", method="GET")


@router.get("/decision/{asset_id}/recommendation")
async def decision_recommendation(asset_id: str) -> dict[str, Any]:
    """Relay an asset recommendation request."""
    encoded_asset_id = quote(asset_id, safe="")
    return await call_ai(
        f"/api/v1/decision/{encoded_asset_id}/recommendation",
        method="GET",
    )
