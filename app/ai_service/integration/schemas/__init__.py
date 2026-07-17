"""Pydantic v2 models that mirror the Section 11 strict TypeScript layouts.

These models are the wire-level contract every Phase 11 UI projection
endpoint serialises through. Field names, types, and nullability are chosen
to be a 1-to-1 match with the TypeScript interfaces in
``src/types/index.ts`` and the inline component types declared in
``src/components/*.tsx`` — no camelCase translation, no nested renames.
"""
from __future__ import annotations

from app.ai_service.integration.schemas.chat_event_schemas import (
    AgentStreamEvent,
    CitationRef,
    DiagnosticLogEntry,
    StreamEventType,
    SubgraphUpdatePacket,
    ToolExecutionEvent,
)
from app.ai_service.integration.schemas.ui_schemas import (
    UIAlert,
    UIAPIResponse,
    UIAsset,
    UIChat,
    UIDigitalTwinPayload,
    UIGraphEdge,
    UIGraphNode,
    UIHistoryFrame,
    UIHistoryPoint,
    UIKnowledge,
    UIPrediction,
    UIRecommendationAction,
    UIShapExplanation,
    UIShapFeature,
    UITelemetry,
)

__all__ = [
    "UIAlert",
    "UIAPIResponse",
    "UIAsset",
    "UIChat",
    "UIDigitalTwinPayload",
    "UIGraphEdge",
    "UIGraphNode",
    "UIHistoryFrame",
    "UIHistoryPoint",
    "UIKnowledge",
    "UIPrediction",
    "UIRecommendationAction",
    "UIShapExplanation",
    "UIShapFeature",
    "UITelemetry",
    "AgentStreamEvent",
    "CitationRef",
    "DiagnosticLogEntry",
    "StreamEventType",
    "SubgraphUpdatePacket",
    "ToolExecutionEvent",
]
