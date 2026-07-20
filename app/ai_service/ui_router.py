"""Phase 11 — UI router exposed at the package root.

This module re-exports the integration UI router so that consumers
importing ``app.ai_service.ui_router`` receive the canonical router
without reaching into ``integration`` subpackages.
"""
from __future__ import annotations

from app.ai_service.integration.ui_router import ui_router

__all__ = ["ui_router"]
