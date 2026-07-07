"""Phase 11 — Chart-ready payload formatters.

These helpers emit JSON payloads shaped for direct binding into a
specific visualisation library. The frontend already has Recharts,
Chart.js, vis-network, and d3-force wired up — we don't want Member 4
to re-shape data on the client, so each function returns a payload that
matches a known library's data contract.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 1. Recharts line series
# ---------------------------------------------------------------------------
def format_recharts_line_series(
    history: Sequence[Any],
    *,
    metric_key: str,
    display_name: Optional[str] = None,
    color_token: str = "industrial",
) -> Dict[str, Any]:
    """Build a Recharts ``<LineChart data={...}>`` payload.

    Recharts wants ``data`` to be an array of objects whose keys are the
    accessors used by ``<XAxis dataKey="timestamp" />`` and
    ``<Line dataKey={metric_key} />``. We emit:

    .. code-block:: json

       {
         "dataKey": "vibration_rms",
         "name": "Vibration (mm/s)",
         "color": "industrial",
         "data": [
           {"timestamp": "2026-07-07T07:00:00Z", "vibration_rms": 1.2},
           ...
         ]
       }
    """

    data: List[Dict[str, Any]] = []
    for frame in history:
        reading_map: Dict[str, float] = {}
        for reading in getattr(frame, "readings", []) or []:
            try:
                reading_map[getattr(reading, "metric", "")] = float(
                    getattr(reading, "value", 0.0)
                )
            except (TypeError, ValueError):
                continue
        ts = getattr(frame, "timestamp", None)
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        y = reading_map.get(metric_key, 0.0)
        if math.isnan(y) or math.isinf(y):
            y = 0.0
        data.append({"timestamp": ts_str, metric_key: y})

    return {
        "dataKey": metric_key,
        "name": display_name or metric_key,
        "color": color_token,
        "data": data,
    }


# ---------------------------------------------------------------------------
# 2. Recharts radar series (snapshot across multiple metrics)
# ---------------------------------------------------------------------------
_METRIC_DISPLAY_NAMES = {
    "rpm": "Rotational Speed",
    "vibration_rms": "Vibration",
    "bearing_temp": "Casing Temp",
    "pressure": "Discharge Pressure",
    "flow_rate": "Flow Rate",
    "load_kw": "Electrical Load",
}


def format_recharts_radar_series(
    frame: Any,
    *,
    metrics: Sequence[str] = ("rpm", "vibration_rms", "bearing_temp", "pressure", "flow_rate", "load_kw"),
) -> Dict[str, Any]:
    """Build a Recharts ``<RadarChart data={...}>`` payload for one frame.

    Each metric is normalised to 0..1 against a sensible engineering
    ceiling so the radar shape is comparable across assets.
    """

    ceilings = {
        "rpm": 6000.0,
        "vibration_rms": 12.0,
        "bearing_temp": 120.0,
        "pressure": 80.0,
        "flow_rate": 5000.0,
        "load_kw": 1500.0,
    }
    reading_map: Dict[str, float] = {}
    for reading in getattr(frame, "readings", []) or []:
        try:
            reading_map[getattr(reading, "metric", "")] = float(
                getattr(reading, "value", 0.0)
            )
        except (TypeError, ValueError):
            continue

    data: List[Dict[str, Any]] = []
    for metric in metrics:
        raw = reading_map.get(metric, 0.0)
        ceiling = ceilings.get(metric, 1.0) or 1.0
        normalised = max(0.0, min(1.0, raw / ceiling))
        if math.isnan(normalised) or math.isinf(normalised):
            normalised = 0.0
        data.append(
            {
                "metric": _METRIC_DISPLAY_NAMES.get(metric, metric),
                "raw": raw,
                "normalised": round(normalised, 4),
            }
        )

    return {"subject": "asset_snapshot", "metrics": data}


# ---------------------------------------------------------------------------
# 3. Time-series points (generic {x, y} for Chart.js / SVG)
# ---------------------------------------------------------------------------
def format_time_series_points(
    history: Sequence[Any],
    *,
    metric_key: str,
) -> List[Dict[str, Any]]:
    """Build a ``[{x, y}, ...]`` series for Chart.js / SVG consumers."""

    points: List[Dict[str, Any]] = []
    for frame in history:
        reading_map: Dict[str, float] = {}
        for reading in getattr(frame, "readings", []) or []:
            try:
                reading_map[getattr(reading, "metric", "")] = float(
                    getattr(reading, "value", 0.0)
                )
            except (TypeError, ValueError):
                continue
        ts = getattr(frame, "timestamp", None)
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        y = reading_map.get(metric_key, 0.0)
        if math.isnan(y) or math.isinf(y):
            y = 0.0
        points.append({"x": ts_str, "y": y})
    return points


# ---------------------------------------------------------------------------
# 4. SHAP waterfall (cumulative bar chart)
# ---------------------------------------------------------------------------
def format_shap_waterfall(
    features: Sequence[Dict[str, Any]],
    *,
    base_value: float,
    max_steps: int = 10,
) -> Dict[str, Any]:
    """Build a SHAP waterfall payload for Recharts / d3.

    The output is a list of ``{ feature, start, end, delta, cumulative }``
    bars; the frontend renders a ``<BarChart>`` with the ``start`` and
    ``(end - start)`` dataKeys to draw floating bars in red/green.
    """

    sorted_feats = sorted(
        (dict(f) for f in features),
        key=lambda f: abs(float(f.get("shapValue", 0.0) or 0.0)),
        reverse=True,
    )[:max_steps]

    cumulative = float(base_value)
    bars: List[Dict[str, Any]] = []
    for f in sorted_feats:
        delta = float(f.get("shapValue", 0.0) or 0.0)
        start = cumulative
        cumulative = cumulative + delta
        bars.append(
            {
                "feature": str(f.get("name", "feature")),
                "value": str(f.get("value", "")),
                "delta": round(delta, 4),
                "start": round(start, 4),
                "end": round(cumulative, 4),
                "cumulative": round(cumulative, 4),
                "direction": "positive" if delta >= 0 else "negative",
            }
        )

    return {
        "baseValue": round(float(base_value), 4),
        "finalValue": round(cumulative, 4),
        "bars": bars,
    }


# ---------------------------------------------------------------------------
# 5. SHAP force plot (linear stacked bar)
# ---------------------------------------------------------------------------
def format_shap_force_plot(
    features: Sequence[Dict[str, Any]],
    *,
    base_value: float,
    prediction_value: float,
    max_steps: int = 10,
) -> Dict[str, Any]:
    """Build a SHAP force-plot payload.

    Produces two stacks (``positive`` / ``negative``) of feature arrows
    sized by ``|shapValue|``, plus the anchor ``baseValue`` and the
    final ``predictionValue`` for the d3 / SVG renderer.
    """

    sorted_feats = sorted(
        (dict(f) for f in features),
        key=lambda f: abs(float(f.get("shapValue", 0.0) or 0.0)),
        reverse=True,
    )[:max_steps]

    positive: List[Dict[str, Any]] = []
    negative: List[Dict[str, Any]] = []
    for f in sorted_feats:
        delta = float(f.get("shapValue", 0.0) or 0.0)
        bucket = positive if delta >= 0 else negative
        bucket.append(
            {
                "feature": str(f.get("name", "feature")),
                "value": str(f.get("value", "")),
                "weight": abs(round(delta, 4)),
                "direction": "positive" if delta >= 0 else "negative",
            }
        )

    return {
        "baseValue": round(float(base_value), 4),
        "predictionValue": round(float(prediction_value), 4),
        "positive": positive,
        "negative": negative,
    }


# ---------------------------------------------------------------------------
# 6. vis-network elements
# ---------------------------------------------------------------------------
def format_vis_network_elements(
    nodes: Sequence[Dict[str, Any]],
    edges: Sequence[Dict[str, Any]],
    *,
    highlight_node_ids: Optional[Sequence[str]] = None,
    highlight_edge_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Build a vis-network ``{ nodes, edges }`` payload.

    Translates the frontend's ``GraphNode`` / ``GraphEdge`` shapes
    into vis-network's vocabulary so the panel can switch libraries
    without re-shaping the upstream payload.
    """

    highlight_node_ids = set(highlight_node_ids or [])
    highlight_edge_ids = set(highlight_edge_ids or [])

    color_map = {
        "asset": {"background": "#22c55e", "border": "#0f172a"},
        "component": {"background": "#3b82f6", "border": "#0f172a"},
        "anomaly": {"background": "#ef4444", "border": "#0f172a"},
        "procedure": {"background": "#f59e0b", "border": "#0f172a"},
        "record": {"background": "#a855f7", "border": "#0f172a"},
    }

    vis_nodes: List[Dict[str, Any]] = []
    for n in nodes:
        nid = str(n.get("id", ""))
        ntype = str(n.get("type", "component")).lower()
        color = color_map.get(ntype, color_map["component"])
        vis_nodes.append(
            {
                "id": nid,
                "label": str(n.get("label", nid)),
                "x": n.get("x"),
                "y": n.get("y"),
                "title": str(n.get("details", "")),
                "color": color,
                "borderWidth": 3 if nid in highlight_node_ids else 1,
                "shape": "box" if ntype in {"procedure", "record"} else "ellipse",
            }
        )

    vis_edges: List[Dict[str, Any]] = []
    for idx, e in enumerate(edges):
        edge_id = str(e.get("id") or f"edge-{idx}-{e.get('source', '')}-{e.get('target', '')}")
        vis_edges.append(
            {
                "id": edge_id,
                "from": str(e.get("source", "")),
                "to": str(e.get("target", "")),
                "label": str(e.get("label", "")),
                "arrows": "to",
                "color": {"color": "#fbbf24" if edge_id in highlight_edge_ids else "#94a3b8"},
                "width": 3 if edge_id in highlight_edge_ids or e.get("highlighted") else 1,
            }
        )

    return {"nodes": vis_nodes, "edges": vis_edges}


# ---------------------------------------------------------------------------
# 7. Sub-graph update packet (used by the chat side panel)
# ---------------------------------------------------------------------------
def format_subgraph_update_packet(
    *,
    operation: str = "add_node",
    nodes: Optional[Sequence[Dict[str, Any]]] = None,
    edges: Optional[Sequence[Dict[str, Any]]] = None,
    highlight_node_ids: Optional[Sequence[str]] = None,
    highlight_edge_ids: Optional[Sequence[str]] = None,
    narrative: str = "",
) -> Dict[str, Any]:
    """Wrap a partial graph update in a packet the chat side panel can append."""

    import uuid as _uuid

    return {
        "packetId": f"sg-{_uuid.uuid4().hex[:8]}",
        "operation": operation,
        "nodes": list(nodes or []),
        "edges": list(edges or []),
        "highlightNodeIds": list(highlight_node_ids or []),
        "highlightEdgeIds": list(highlight_edge_ids or []),
        "narrative": narrative,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
