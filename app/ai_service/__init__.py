"""Phase 10 AI service integration package.

This package exposes the AI/knowledge engines behind an isolated FastAPI
router that can be mounted by Member 1 without coupling to UI or gateway auth.
"""
from app.ai_service.main_router import ai_router, create_ai_service_app

__all__ = ["ai_router", "create_ai_service_app"]
