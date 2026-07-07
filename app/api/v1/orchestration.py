"""Backend-only Phase 9 multi-agent orchestration API bridge."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.common import APIResponse
from app.orchestration.service import get_orchestration_service
from app.orchestration.state import OrchestratorRequest, OrchestratorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post("/execute", response_model=APIResponse[OrchestratorResponse])
async def orchestrator_execute(body: OrchestratorRequest) -> APIResponse[OrchestratorResponse]:
    """Execute the unified Phase 9 state graph with bounded recursion."""
    try:
        result = await get_orchestration_service().execute(body)
        return APIResponse(success=True, data=result, error=None, request_id=result.request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Phase 9 orchestrator failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
async def orchestrator_health() -> dict[str, object]:
    return {"status": "ok", "engine": "phase9_langgraph_orchestrator", "max_recursion_limit": 15}
