"""Chart-ready payload formatters for the Next.js dashboard panels.

Each formatter is pure, side-effect free, and produces the JSON contract a
specific chart library (Recharts, Chart.js, vis-network, d3-force) expects
without forcing Member 4 to write any client-side parser code.
"""
from __future__ import annotations

from app.ai_service.integration.formatters.confidence_badge import (
    ConfidenceBadge,
    confidence_to_badge,
    confidence_to_color,
    confidence_to_warning_level,
)
from app.ai_service.integration.formatters.payload_formatters import (
    format_recharts_line_series,
    format_recharts_radar_series,
    format_shap_force_plot,
    format_shap_waterfall,
    format_subgraph_update_packet,
    format_vis_network_elements,
    format_time_series_points,
)

__all__ = [
    "format_recharts_line_series",
    "format_recharts_radar_series",
    "format_shap_force_plot",
    "format_shap_waterfall",
    "format_subgraph_update_packet",
    "format_vis_network_elements",
    "format_time_series_points",
    "ConfidenceBadge",
    "confidence_to_badge",
    "confidence_to_color",
    "confidence_to_warning_level",
]
