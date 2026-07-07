"""Phase 11 — Unit tests for chart-ready payload formatters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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
    format_time_series_points,
    format_vis_network_elements,
)

NOW = datetime(2026, 7, 7, 7, 15, tzinfo=timezone.utc)


@pytest.fixture
def history() -> list:
    out = []
    for i in range(12):
        out.append(
            _Stub(
                timestamp=NOW + timedelta(minutes=5 * i),
                readings=[
                    _Stub(metric="rpm", value=1480.0 + i * 5),
                    _Stub(metric="vibration_rms", value=4.0 + 0.2 * i),
                    _Stub(metric="bearing_temp", value=78.0 + 0.5 * i),
                    _Stub(metric="pressure", value=6.0 + 0.05 * i),
                    _Stub(metric="flow_rate", value=240.0 + 2 * i),
                    _Stub(metric="load_kw", value=300.0 + i),
                ],
            )
        )
    return out


class _Stub:
    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Confidence badge mappers
# ---------------------------------------------------------------------------
class TestConfidenceBadge:
    def test_very_high(self) -> None:
        assert confidence_to_badge(0.99) == ConfidenceBadge.VERY_HIGH

    def test_high(self) -> None:
        assert confidence_to_badge(0.82) == ConfidenceBadge.HIGH

    def test_medium(self) -> None:
        assert confidence_to_badge(0.65) == ConfidenceBadge.MEDIUM

    def test_low(self) -> None:
        assert confidence_to_badge(0.40) == ConfidenceBadge.LOW

    def test_very_low(self) -> None:
        assert confidence_to_badge(0.10) == ConfidenceBadge.VERY_LOW

    def test_clamps_to_range(self) -> None:
        assert confidence_to_badge(1.5) == ConfidenceBadge.VERY_HIGH
        assert confidence_to_badge(-0.1) == ConfidenceBadge.VERY_LOW

    def test_color_tuple(self) -> None:
        hex_color, text_class, bg_class = confidence_to_color(0.9)
        assert hex_color.startswith("#")
        assert text_class.startswith("text-")
        assert bg_class.startswith("bg-")

    def test_warning_level_high(self) -> None:
        assert confidence_to_warning_level(0.9) == "industrial-status-ok"

    def test_warning_level_medium(self) -> None:
        assert confidence_to_warning_level(0.65) == "industrial-status-warning"

    def test_warning_level_low(self) -> None:
        assert confidence_to_warning_level(0.1) == "industrial-status-critical"


# ---------------------------------------------------------------------------
# Recharts line series
# ---------------------------------------------------------------------------
class TestRechartsLineSeries:
    def test_returns_data_key_and_data_array(self, history: list) -> None:
        series = format_recharts_line_series(history, metric_key="vibration_rms")
        assert series["dataKey"] == "vibration_rms"
        assert series["name"] == "vibration_rms"
        assert isinstance(series["data"], list)
        assert len(series["data"]) == len(history)
        for point in series["data"]:
            assert "timestamp" in point
            assert "vibration_rms" in point

    def test_uses_display_name(self, history: list) -> None:
        series = format_recharts_line_series(
            history, metric_key="vibration_rms", display_name="Vibration (mm/s)"
        )
        assert series["name"] == "Vibration (mm/s)"


# ---------------------------------------------------------------------------
# Recharts radar series
# ---------------------------------------------------------------------------
class TestRechartsRadarSeries:
    def test_returns_metrics_with_normalised_values(self, history: list) -> None:
        frame = history[-1]
        radar = format_recharts_radar_series(frame)
        assert radar["subject"] == "asset_snapshot"
        names = {m["metric"] for m in radar["metrics"]}
        assert "Vibration" in names
        assert "Casing Temp" in names
        for m in radar["metrics"]:
            assert 0.0 <= m["normalised"] <= 1.0


# ---------------------------------------------------------------------------
# Time-series points
# ---------------------------------------------------------------------------
class TestTimeSeriesPoints:
    def test_xy_shape(self, history: list) -> None:
        pts = format_time_series_points(history, metric_key="rpm")
        assert len(pts) == len(history)
        for p in pts:
            assert set(p.keys()) == {"x", "y"}


# ---------------------------------------------------------------------------
# SHAP waterfall
# ---------------------------------------------------------------------------
class TestShapWaterfall:
    def test_returns_bars_with_start_end_cumulative(self) -> None:
        features = [
            {"name": "vibration_rms", "value": "5.2", "shapValue": 0.42},
            {"name": "bearing_temp", "value": "82", "shapValue": 0.31},
            {"name": "rpm", "value": "1480", "shapValue": -0.05},
        ]
        out = format_shap_waterfall(features, base_value=0.3)
        assert out["baseValue"] == 0.3
        assert len(out["bars"]) == 3
        for bar in out["bars"]:
            assert {"feature", "value", "delta", "start", "end", "cumulative", "direction"} <= set(bar.keys())

    def test_bars_sorted_by_abs_shap_desc(self) -> None:
        features = [
            {"name": "rpm", "value": "1480", "shapValue": -0.05},
            {"name": "vibration_rms", "value": "5.2", "shapValue": 0.42},
            {"name": "bearing_temp", "value": "82", "shapValue": 0.31},
        ]
        out = format_shap_waterfall(features, base_value=0.0)
        names = [bar["feature"] for bar in out["bars"]]
        assert names[0] == "vibration_rms"

    def test_cumulative_math(self) -> None:
        features = [
            {"name": "a", "value": "1", "shapValue": 0.5},
            {"name": "b", "value": "2", "shapValue": -0.2},
        ]
        out = format_shap_waterfall(features, base_value=0.3)
        assert out["bars"][0]["start"] == 0.3
        assert out["bars"][0]["end"] == 0.8
        assert out["bars"][1]["start"] == 0.8
        assert out["bars"][1]["end"] == pytest.approx(0.6, abs=1e-9)
        assert out["finalValue"] == pytest.approx(0.6, abs=1e-9)


# ---------------------------------------------------------------------------
# SHAP force plot
# ---------------------------------------------------------------------------
class TestShapForcePlot:
    def test_splits_positive_and_negative(self) -> None:
        features = [
            {"name": "vibration_rms", "value": "5.2", "shapValue": 0.42},
            {"name": "rpm", "value": "1480", "shapValue": -0.10},
        ]
        out = format_shap_force_plot(features, base_value=0.3, prediction_value=0.62)
        assert out["baseValue"] == 0.3
        assert out["predictionValue"] == 0.62
        assert any(f["feature"] == "vibration_rms" for f in out["positive"])
        assert any(f["feature"] == "rpm" for f in out["negative"])


# ---------------------------------------------------------------------------
# vis-network elements
# ---------------------------------------------------------------------------
class TestVisNetworkElements:
    def test_translates_nodes_and_edges(self) -> None:
        nodes = [
            {"id": "a", "label": "Asset A", "type": "asset", "x": 60, "y": 60, "details": "running"},
            {"id": "b", "label": "SOP B", "type": "procedure", "x": 200, "y": 60, "details": "guide"},
        ]
        edges = [
            {"id": "e1", "source": "a", "target": "b", "label": "guided_by", "highlighted": False},
        ]
        out = format_vis_network_elements(nodes, edges)
        assert out["nodes"][0]["id"] == "a"
        assert out["edges"][0]["from"] == "a"
        assert out["edges"][0]["to"] == "b"

    def test_highlighted_node_gets_thick_border(self) -> None:
        nodes = [{"id": "a", "label": "A", "type": "asset", "x": 0, "y": 0, "details": ""}]
        out = format_vis_network_elements(nodes, [], highlight_node_ids=["a"])
        assert out["nodes"][0]["borderWidth"] == 3

    def test_synthesises_edge_id(self) -> None:
        nodes = []
        edges = [{"source": "a", "target": "b", "label": "x"}]
        out = format_vis_network_elements(nodes, edges)
        assert out["edges"][0]["id"].startswith("edge-")
        assert out["edges"][0]["from"] == "a"


# ---------------------------------------------------------------------------
# Subgraph update packet
# ---------------------------------------------------------------------------
class TestSubgraphUpdatePacket:
    def test_packet_includes_operation_and_narrative(self) -> None:
        pkt = format_subgraph_update_packet(
            operation="add_node",
            nodes=[{"id": "x", "label": "X"}],
            narrative="added from retrieval",
        )
        assert pkt["operation"] == "add_node"
        assert pkt["narrative"] == "added from retrieval"
        assert pkt["nodes"] == [{"id": "x", "label": "X"}]
        assert pkt["packetId"].startswith("sg-")
        assert "generatedAt" in pkt
