"""Central API router registrations."""
from fastapi import APIRouter

from app.api import ai_proxy

router = APIRouter()
router.include_router(ai_proxy.router, prefix="/ai", tags=["ai"])

__all__ = ["router"]
