"""Pure data adapters — backend Pydantic models → frontend JSON shapes.

These functions never call engines and never perform I/O. They are designed to
be cheap, deterministic, and trivially unit-testable so Member 4 can rely on
the *exact* output byte-for-byte in their React components.
"""
from __future__ import annotations

from app.ai_service.integration.adapters.chat_event_adapter import (
    to_chat_event_block,
    to_chat_event_stream,
    to_ui_chat_message,
)
from app.ai_service.integration.adapters.frontend_adapters import (
    adapt_digital_twin_payload,
    adapt_explainability_payload,
    adapt_graphrag_payload,
    adapt_inference_to_prediction,
    adapt_recommendations_to_actions,
    build_telemetry_chart_series,
)

__all__ = [
    "adapt_digital_twin_payload",
    "adapt_explainability_payload",
    "adapt_graphrag_payload",
    "adapt_inference_to_prediction",
    "adapt_recommendations_to_actions",
    "build_telemetry_chart_series",
    "to_chat_event_block",
    "to_chat_event_stream",
    "to_ui_chat_message",
]
