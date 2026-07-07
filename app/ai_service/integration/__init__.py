"""Phase 11 — Frontend Integration Support.

Acts as the programmatic bridge between the Phase 0–10 backend AI platform and
the Next.js / TypeScript frontend components in ``src/components/``.

This package is **strictly backend-only**. It contains:

* ``adapters``     — pure data transformers that reshape backend Pydantic
                     models into the exact JSON shapes consumed by the
                     pre-built React components (DigitalTwinView,
                     GraphRagPanel, ShapExplainability, Chat, etc.).
* ``formatters``   — chart-ready helpers for Recharts/Chart.js time series,
                     SHAP waterfall/force plots, confidence badge mapping,
                     and other visualisation primitives.
* ``schemas``      — Pydantic v2 models that mirror the Section 11 strict
                     TypeScript layouts and the additional component-level
                     contracts (``TelemetryFrame``, ``UIGraphNode``,
                     ``UIGraphEdge``, ``UISHAPFeature``).
* ``ui_router``    — FastAPI sub-router mounted at ``/api/v1/ai/ui/*`` that
                     exposes the UI-shaped projections of the same engines
                     that power the raw ``/api/v1/ai/*`` endpoints.
* ``cors_headers`` — explicit CORS / preflight probe helpers and a dedicated
                     ``/api/v1/ai/ui/options`` endpoint so Member 1 (gateway)
                     and Member 4 (frontend) can verify cross-origin wiring
                     in CI before the first browser request flies.

No React, TypeScript, or Next.js code is shipped from this package — the
contract flows strictly *backend → JSON → frontend* without any UI rewrite.
"""
from __future__ import annotations

from app.ai_service.integration import adapters, formatters, schemas
from app.ai_service.integration.cors_headers import (
    UI_ALLOWED_HEADERS,
    UI_ALLOWED_METHODS,
    UI_EXPOSED_HEADERS,
    build_ui_preflight_headers,
    verify_cors_configuration,
)
from app.ai_service.integration.ui_router import ui_router

__all__ = [
    "adapters",
    "formatters",
    "schemas",
    "ui_router",
    "UI_ALLOWED_HEADERS",
    "UI_ALLOWED_METHODS",
    "UI_EXPOSED_HEADERS",
    "build_ui_preflight_headers",
    "verify_cors_configuration",
]
