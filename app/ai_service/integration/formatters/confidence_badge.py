"""Phase 11 — Confidence → UI badge / colour / warning-level mappers.

The frontend renders multiple "warning lights" — a green/amber/red badge
on the SHAP panel, a traffic-light dot on the digital twin status pill,
and a colour-coded confidence bar on the GraphRAG answer header.

We centralise the mapping here so a single tweak (e.g. lowering the
"high confidence" threshold from 0.85 → 0.80) is one-line.
"""
from __future__ import annotations

from enum import Enum
from typing import Tuple


class ConfidenceBadge(str, Enum):
    """Coarse confidence bucket consumed by the UI."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


_THRESHOLDS = [
    (0.95, ConfidenceBadge.VERY_HIGH),
    (0.80, ConfidenceBadge.HIGH),
    (0.60, ConfidenceBadge.MEDIUM),
    (0.30, ConfidenceBadge.LOW),
    (0.00, ConfidenceBadge.VERY_LOW),
]


def confidence_to_badge(confidence: float) -> ConfidenceBadge:
    """Bucket a 0..1 confidence value into a UI badge."""

    c = max(0.0, min(1.0, float(confidence)))
    for threshold, badge in _THRESHOLDS:
        if c >= threshold:
            return badge
    return ConfidenceBadge.VERY_LOW


_BADGE_TO_COLOR = {
    ConfidenceBadge.VERY_HIGH: ("#16a34a", "text-green-700", "bg-green-100"),  # green-600/700/100
    ConfidenceBadge.HIGH: ("#22c55e", "text-green-600", "bg-green-50"),
    ConfidenceBadge.MEDIUM: ("#f59e0b", "text-amber-600", "bg-amber-50"),
    ConfidenceBadge.LOW: ("#f97316", "text-orange-600", "bg-orange-50"),
    ConfidenceBadge.VERY_LOW: ("#ef4444", "text-red-600", "bg-red-50"),
}


def confidence_to_color(confidence: float) -> Tuple[str, str, str]:
    """Map confidence → ``(hex, tailwind_text_class, tailwind_bg_class)``."""

    return _BADGE_TO_COLOR[confidence_to_badge(confidence)]


def confidence_to_warning_level(confidence: float) -> str:
    """Map confidence to a single Tailwind class for the GraphRAG answer header."""

    badge = confidence_to_badge(confidence)
    if badge in {ConfidenceBadge.VERY_HIGH, ConfidenceBadge.HIGH}:
        return "industrial-status-ok"
    if badge == ConfidenceBadge.MEDIUM:
        return "industrial-status-warning"
    return "industrial-status-critical"
