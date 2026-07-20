"""Phase 11 — Pure data transformers (backend → frontend JSON).

Each function in this module takes one or more Phase 0–10 Pydantic models
and returns a JSON-ready ``dict`` (or one of the :mod:`ui_schemas` models)
that **byte-for-byte** matches the shape consumed by a specific React
component or service hook in ``src/``.

Contract invariants (enforced in the test suite):

* ``adapt_inference_to_prediction``     →  :class:`UIPrediction`         (section 11)
* ``adapt_graphrag_payload``            →  :class:`UIGraphRAGPayload`    (GraphRagPanel)
* ``adapt_digital_twin_payload``        →  :class:`UIDigitalTwinPayload` (DigitalTwinView)
* ``adapt_explainability_payload``      →  :class:`UIShapExplanation`    (ShapExplainability)
* ``adapt_recommendations_to_actions``  →  ``List[UIRecommendationAction]`` (action card panel)
* ``build_telemetry_chart_series``      →  ``List[UIHistoryPoint]``      (Recharts/Chart.js)
* ``to_ui_api_envelope``                →  :class:`UIAPIResponse[T]`     (section 11)
* ``api_error_to_ui_error``             →  :class:`UIAPIError`           (section 11)

These functions are pure, deterministic, side-effect free, and never touch
the network. They can be called from any FastAPI handler, background task,
or unit test with full confidence.
"""
from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.ai_service.integration.schemas.ui_schemas import (
    UIActionPriority,
    UIAPIError,
    UIAPIResponse,
    UIAsset,
    UIAssetStatus,
    UIGraphEdge,
    UIGraphNode,
    UIGraphNodeType,
    UIGraphRAGPayload,
    UIHistoryFrame,
    UIHistoryPoint,
    UIDigitalTwinPayload,
    UIRecommendationAction,
    UISeverityTier,
    UIShapExplanation,
    UIShapFeature,
    UISopLinkage,
    UITelemetry,
    UITelemetryStatus,
)

# ---------------------------------------------------------------------------
# Anomaly → telemetry.status vocabulary mapping
# ---------------------------------------------------------------------------
# DigitalTwinView's branch on ``telemetry.status`` requires the lowercase
# vocabulary ``ok | warning | critical | offline``. We map from the richer
# backend signals (anomaly severity, asset status, RUL band) down to that
# tiny enum.

_WARN_ANOMALIES = {"MEDIUM", "WARNING"}
_CRIT_ANOMALIES = {"HIGH", "CRITICAL", "FATAL"}


def _telemetry_status(
    *,
    asset_status: Optional[str],
    highest_severity: Optional[str],
    rul_days: Optional[float],
) -> UITelemetryStatus:
    """Map backend asset/anomaly signals → DigitalTwinView's ``telemetry.status``."""

    if asset_status and asset_status.upper() in {"OFFLINE", "FAULT", "MAINTENANCE"}:
        return UITelemetryStatus.OFFLINE
    if asset_status and asset_status.upper() == "CRITICAL":
        return UITelemetryStatus.CRITICAL
    if (highest_severity or "").upper() in _CRIT_ANOMALIES:
        return UITelemetryStatus.CRITICAL
    if (highest_severity or "").upper() in _WARN_ANOMALIES:
        return UITelemetryStatus.WARNING
    if rul_days is not None and rul_days < 7:
        return UITelemetryStatus.CRITICAL
    if rul_days is not None and rul_days < 14:
        return UITelemetryStatus.WARNING
    return UITelemetryStatus.OK


def _dominant_anomaly_token(
    *,
    failure_mode_id: Optional[str],
    failure_mode_label: Optional[str],
    anomalous_sensors: Sequence[str],
) -> Optional[str]:
    """Translate the dominant anomaly into the token the panel branches on.

    The component checks against tokens like ``"bearing-wear"``,
    ``"compressor-surge"``, ``"electrical-trip"``, ``"leakage"`` and
    falls back to a generic "warning" path. We do the same fuzzy match
    so the same back-end payload drives the same component branch.
    """

    label = (failure_mode_label or failure_mode_id or "").lower()
    if "bearing" in label or "wear" in label:
        return "bearing-wear"
    if "surge" in label or "compressor-surge" in label:
        return "compressor-surge"
    if "trip" in label or "electrical" in label or "breaker" in label:
        return "electrical-trip"
    if "leak" in label or "seal" in label:
        return "leakage"
    sensor_blob = " ".join(anomalous_sensors).lower()
    if "vib" in sensor_blob or "bearing" in sensor_blob:
        return "bearing-wear"
    if "press" in sensor_blob:
        return "compressor-surge"
    if "flow" in sensor_blob:
        return "leakage"
    return None


# ---------------------------------------------------------------------------
# Severity / priority mappings
# ---------------------------------------------------------------------------
_PRIORITY_MAP = {
    "LOW": UIActionPriority.LOW,
    "MEDIUM": UIActionPriority.MEDIUM,
    "HIGH": UIActionPriority.HIGH,
    "CRITICAL": UIActionPriority.CRITICAL,
}

_TIER_MAP = {
    "IMMINENT": UISeverityTier.IMMINENT,
    "SCHEDULED": UISeverityTier.SCHEDULED,
    "MONITOR": UISeverityTier.MONITOR,
}


# ===========================================================================
# 1. Prediction adapter — InferenceResponse → UIPrediction
# ===========================================================================
def adapt_inference_to_prediction(
    inference: Any,
    *,
    asset_lookup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert a Phase 6 :class:`InferenceResponse` to a Section 11 ``Prediction``.

    Maps the frozen RUL/FP/anomaly fields onto the
    ``id / assetId / remainingUsefulLifeDays / failureProbability /
    inferredFaultMechanism`` shape used by ``prediction.service.ts``
    and the dashboard prediction list.
    """

    rul = getattr(inference, "rul", None)
    fp = getattr(inference, "failure_probability", None)
    pred_id = getattr(inference, "explanation_id", None) or getattr(
        inference, "inference_id", None
    )
    if not pred_id:
        pred_id = f"pred-{uuid.uuid4().hex[:10]}"

    fault = ""
    if fp is not None:
        fault = getattr(fp, "failure_mode_label", None) or getattr(
            fp, "failure_mode_id", None
        ) or ""
    if not fault:
        # Fall back to the highest-ranked anomaly
        flags = list(getattr(inference, "anomaly_flags", []) or [])
        flags.sort(key=lambda f: abs(getattr(f, "anomaly_score", 0.0)), reverse=True)
        if flags:
            fault = f"Anomalous {flags[0].metric}"

    return {
        "id": pred_id,
        "assetId": getattr(inference, "asset_id", ""),
        "remainingUsefulLifeDays": float(getattr(rul, "value_days", 0.0) or 0.0),
        "failureProbability": float(getattr(fp, "probability", 0.0) or 0.0),
        "inferredFaultMechanism": fault or "Unknown",
    }


# ===========================================================================
# 2. GraphRAG adapter — GraphRagQueryResponse → UIGraphRAGPayload
# ===========================================================================
_NODE_TYPE_VOCAB = {
    "asset": UIGraphNodeType.ASSET,
    "component": UIGraphNodeType.COMPONENT,
    "anomaly": UIGraphNodeType.ANOMALY,
    "failure_mode": UIGraphNodeType.ANOMALY,
    "failuremode": UIGraphNodeType.ANOMALY,  # Phase 1 ontology uses "FailureMode"
    "fault": UIGraphNodeType.ANOMALY,
    "failure": UIGraphNodeType.ANOMALY,
    "procedure": UIGraphNodeType.PROCEDURE,
    "sop": UIGraphNodeType.PROCEDURE,
    "record": UIGraphNodeType.RECORD,
    "incident": UIGraphNodeType.RECORD,
    "workorder": UIGraphNodeType.RECORD,
    "work_order": UIGraphNodeType.RECORD,
    "event": UIGraphNodeType.RECORD,
}


def _project_graph_layout(
    nodes: Sequence[Any],
    edges: Sequence[Any],
) -> Dict[str, Tuple[float, float]]:
    """Deterministic layered layout (left-to-right) for nodes missing x/y.

    The frontend's GraphRagPanel uses an absolutely positioned SVG
    canvas with hand-set ``x``/``y`` for every node. When the upstream
    graph traversal returns nodes without positions we project a
    stable 2-D layout: a left column for assets, a middle column for
    components/anomalies, and a right column for procedures/records.
    The position depends only on the node id, so the layout is stable
    across re-renders.
    """

    positions: Dict[str, Tuple[float, float]] = {}
    if not nodes:
        return positions

    bins: Dict[UIGraphNodeType, List[Any]] = {
        UIGraphNodeType.ASSET: [],
        UIGraphNodeType.COMPONENT: [],
        UIGraphNodeType.ANOMALY: [],
        UIGraphNodeType.PROCEDURE: [],
        UIGraphNodeType.RECORD: [],
    }
    for node in nodes:
        vocab = _NODE_TYPE_VOCAB.get(str(node.type).lower(), UIGraphNodeType.COMPONENT)
        bins[vocab].append(node)

    column_x = {
        UIGraphNodeType.ASSET: 60,
        UIGraphNodeType.COMPONENT: 200,
        UIGraphNodeType.ANOMALY: 320,
        UIGraphNodeType.PROCEDURE: 440,
        UIGraphNodeType.RECORD: 540,
    }
    for vocab, members in bins.items():
        members.sort(key=lambda n: str(n.id))
        for idx, node in enumerate(members):
            y = 60 + idx * 80
            positions[str(node.id)] = (float(column_x[vocab]), float(y))
    return positions


def adapt_graphrag_payload(
    response: Any,
    *,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert a :class:`GraphRagQueryResponse` into the GraphRagPanel shape.

    The component does:

    * iterate ``data.nodes`` and bind ``id/label/type/x/y/details`` for SVG
    * iterate ``data.edges`` and bind ``source/target/label/highlighted``
    * walk ``data.logs`` to render the "loading logs" timeline
    * set the final ``data.answer`` text
    * highlight nodes/edges by id from ``data.highlightedNodes`` /
      ``data.highlightedEdges``

    The adapter derives a chronology of "log" strings from the response
    metadata so the panel's animation strip is non-empty even when the
    backend doesn't surface them explicitly.
    """

    raw_nodes = list(getattr(response, "graph_nodes", []) or [])
    raw_edges = list(getattr(response, "graph_edges", []) or [])
    layout = _project_graph_layout(raw_nodes, raw_edges)

    nodes: List[Dict[str, Any]] = []
    for node in raw_nodes:
        vocab = _NODE_TYPE_VOCAB.get(str(node.type).lower(), UIGraphNodeType.COMPONENT)
        # Pre-existing x/y from the backend take precedence; otherwise use layout.
        x = getattr(node, "x", None)
        y = getattr(node, "y", None)
        if x is None or y is None:
            lx, ly = layout.get(str(node.id), (60.0, 60.0))
        else:
            lx, ly = float(x), float(y)
        details = getattr(node, "label", str(node.id))
        # Promote a few common properties into a one-liner
        props = dict(getattr(node, "properties", {}) or {})
        if "description" in props:
            details = f"{details} — {props['description']}"
        elif "status" in props:
            details = f"{details} (status: {props['status']})"
        nodes.append(
            {
                "id": str(node.id),
                "label": str(getattr(node, "label", node.id)),
                "type": vocab.value,
                "x": lx,
                "y": ly,
                "details": details,
            }
        )

    edges: List[Dict[str, Any]] = []
    for edge in raw_edges:
        edges.append(
            {
                "source": str(getattr(edge, "source", "")),
                "target": str(getattr(edge, "target", "")),
                "label": str(getattr(edge, "relationship", "")),
                "highlighted": False,
            }
        )

    # Derive highlighted node/edge ids from the citation graph (citations
    # referencing nodes/edges) plus a deterministic hash of the query
    # so the highlight pattern is stable across reloads.
    citations = list(getattr(response, "citations", []) or [])
    hl_nodes: List[str] = []
    hl_edges: List[str] = []
    for c in citations:
        node_id = getattr(c, "source_node_id", None)
        if node_id and node_id not in hl_nodes:
            hl_nodes.append(str(node_id))
    # Mark an edge highlighted when both endpoints are highlighted
    for edge in edges:
        if edge["source"] in hl_nodes and edge["target"] in hl_nodes:
            edge["highlighted"] = True
            edge_id = f"{edge['source']}-{edge['target']}"
            if edge_id not in hl_edges:
                hl_edges.append(edge_id)

    # Build a chronological logs block so the panel's animation strip is populated.
    logs: List[str] = []
    vector_hits = int(getattr(response, "vector_hits", 0) or 0)
    if query:
        logs.append(f"Vector search initiated: '{query}'")
    else:
        logs.append("Vector search initiated")
    if vector_hits:
        logs.append(f"Vector hits: {vector_hits} chunks")
    for idx, c in enumerate(citations[:5]):
        label = getattr(c, "source_type", None) or getattr(c, "source_document", None) or "citation"
        logs.append(f"Citation {idx + 1}: {label} (confidence={getattr(c, 'confidence_score', 0.0):.2f})")
    if nodes:
        logs.append(f"Sub-graph projected: {len(nodes)} nodes / {len(edges)} edges")
    if getattr(response, "answer", None):
        logs.append("Synthesizing response context via LLM...")
    else:
        logs.append("Awaiting LLM synthesis…")

    return {
        "answer": getattr(response, "answer", "") or "",
        "logs": logs,
        "nodes": nodes,
        "edges": edges,
        "highlightedNodes": hl_nodes,
        "highlightedEdges": hl_edges,
        "citations": [
            (c.model_dump(mode="json") if hasattr(c, "model_dump")
             else dict(c) if isinstance(c, dict)
             else c.__dict__)
            for c in citations
        ],
        "vectorHits": vector_hits,
        "confidence": float(getattr(response, "overall_confidence", 0.0) or 0.0),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# 3. Digital Twin adapter — InferenceResponse + history → UIDigitalTwinPayload
# ===========================================================================
def _enum_value(value: Any) -> str:
    """Best-effort string conversion for an enum (or string) value.

    ``str(UIAssetStatus.OPERATIONAL)`` is ``'UIAssetStatus.OPERATIONAL'`` on
    Python 3.13, so we explicitly pull ``.value`` for enums and fall back
    to ``str(...)`` for plain strings.
    """

    value_ = getattr(value, "value", None)
    if isinstance(value_, str):
        return value_
    if isinstance(value, str):
        return value
    return str(value)


def _safe_metric(reading_map: Dict[str, float], key: str, default: float = 0.0) -> float:
    """Best-effort float coercion with NaN/inf guards (chart libraries crash on these)."""

    try:
        val = reading_map.get(key, default)
        f = float(val)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return f


def _frame_to_telemetry(frame: Any) -> UITelemetry:
    """Convert a single ``TelemetryReading`` (Phase 6 frozen) to a ``UITelemetry``."""

    reading_map: Dict[str, float] = {}
    for reading in getattr(frame, "readings", []) or []:
        metric = getattr(reading, "metric", "")
        try:
            reading_map[metric] = float(getattr(reading, "value", 0.0))
        except (TypeError, ValueError):
            continue

    return UITelemetry(
        speed=_safe_metric(reading_map, "rpm", 0.0),
        vibration=_safe_metric(reading_map, "vibration_rms", 0.0),
        pressure=_safe_metric(reading_map, "pressure", 0.0),
        temperature=_safe_metric(reading_map, "bearing_temp", 0.0),
        flowRate=_safe_metric(reading_map, "flow_rate", 0.0),
        load=_safe_metric(reading_map, "load_kw", 0.0),
        riskScore=0.0,  # Filled in by the caller from the InferenceResponse
        status=UITelemetryStatus.OK,  # Filled in by the caller
    )


def build_telemetry_chart_series(
    history: Sequence[Any],
    *,
    metric_key: str,
) -> List[Dict[str, Any]]:
    """Build a Recharts/Chart.js ``{x, y}`` series for one metric.

    DigitalTwinView's mini SVG charts use the same data layout, so the
    same shape feeds both libraries.
    """

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
        points.append(
            UIHistoryPoint(
                x=ts_str,
                y=_safe_metric(reading_map, metric_key, 0.0),
            ).model_dump(mode="json")
        )
    return points


def adapt_digital_twin_payload(
    *,
    asset: Any,
    inference: Optional[Any] = None,
    history: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Build the full DigitalTwinView payload from an asset + optional inference.

    Parameters
    ----------
    asset
        A :class:`UIAsset`-like object (or any object exposing
        ``id/name/type/status/parentId``).
    inference
        Optional :class:`InferenceResponse`. When supplied the panel's
        AI Risk Index, ``telemetry.status``, and ``activeAnomaly`` token
        are derived from it.
    history
        Optional list of :class:`TelemetryReading` frames for the mini
        charts. Must be in chronological order (oldest → newest).
    """

    history = list(history or [])
    latest_frame = history[-1] if history else None
    telemetry = _frame_to_telemetry(latest_frame) if latest_frame else UITelemetry()

    # Section 11 asset shape
    ui_asset = UIAsset(
        id=str(getattr(asset, "id", "")),
        name=str(getattr(asset, "name", getattr(asset, "id", ""))),
        type=str(getattr(asset, "type", "GENERIC")),
        status=UIAssetStatus(_enum_value(getattr(asset, "status", "OPERATIONAL"))),
        parentId=getattr(asset, "parentId", None) or getattr(asset, "parent_id", None),
    )

    rul_value: Optional[float] = None
    highest_severity: Optional[str] = None
    anomalous_sensors: List[str] = []
    failure_mode_id: Optional[str] = None
    failure_mode_label: Optional[str] = None

    if inference is not None:
        rul = getattr(inference, "rul", None)
        if rul is not None:
            rul_value = float(getattr(rul, "value_days", 0.0) or 0.0)
        fp = getattr(inference, "failure_probability", None)
        if fp is not None:
            failure_mode_id = getattr(fp, "failure_mode_id", None)
            failure_mode_label = getattr(fp, "failure_mode_label", None)
        flags = list(getattr(inference, "anomaly_flags", []) or [])
        anomalous_sensors = [
            str(getattr(f, "sensor_id", "")) for f in flags if getattr(f, "is_anomalous", False)
        ]
        # Highest severity among flagged anomalies
        severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        if flags:
            highest = max(
                flags,
                key=lambda f: severity_order.get(str(getattr(f, "severity", "LOW")).upper(), 0),
            )
            highest_severity = str(getattr(highest, "severity", ""))

        # Drive the AI Risk Index 0..100 from failure probability
        if fp is not None:
            telemetry = telemetry.model_copy(
                update={"riskScore": round(float(fp.probability) * 100.0, 2)}
            )

    telemetry = telemetry.model_copy(
        update={
            "status": _telemetry_status(
                asset_status=ui_asset.status.value,
                highest_severity=highest_severity,
                rul_days=rul_value,
            )
        }
    )

    frames: List[Dict[str, Any]] = []
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
        frame_status = _telemetry_status(
            asset_status=ui_asset.status.value,
            highest_severity=None,
            rul_days=None,
        )
        frames.append(
            UIHistoryFrame(
                timestamp=ts_str,
                speed=_safe_metric(reading_map, "rpm", 0.0),
                vibration=_safe_metric(reading_map, "vibration_rms", 0.0),
                pressure=_safe_metric(reading_map, "pressure", 0.0),
                temperature=_safe_metric(reading_map, "bearing_temp", 0.0),
                flowRate=_safe_metric(reading_map, "flow_rate", 0.0),
                load=_safe_metric(reading_map, "load_kw", 0.0),
                riskScore=telemetry.riskScore,
                status=frame_status,
            ).model_dump(mode="json")
        )

    active_anomaly = _dominant_anomaly_token(
        failure_mode_id=failure_mode_id,
        failure_mode_label=failure_mode_label,
        anomalous_sensors=anomalous_sensors,
    )

    payload = UIDigitalTwinPayload(
        asset=ui_asset,
        telemetry=telemetry,
        history=frames,
        activeAnomaly=active_anomaly,
    )
    return payload.model_dump(mode="json", by_alias=False)


# ===========================================================================
# 4. SHAP / LIME adapter — ExplanationResponse → UIShapExplanation
# ===========================================================================
def adapt_explainability_payload(
    *,
    explanation: Any,
    prediction_id: str,
    asset_id: str,
) -> Dict[str, Any]:
    """Convert a :class:`ExplanationResponse` into the ShapExplainability shape.

    The component expects ``features`` **already sorted by |shapValue| desc**
    (it does its own sort too, but the upstream sort keeps the waterfall
    layout deterministic and reduces re-render churn). Description
    strings are enriched with engineering units when present in
    ``properties`` so the panel's tooltip text is informative.
    """

    impacts = list(getattr(explanation, "local_feature_importance", []) or [])
    # Sort desc by |impact_weight| — the panel renders top-to-bottom.
    impacts.sort(key=lambda fi: abs(float(getattr(fi, "impact_weight", 0.0))), reverse=True)

    features: List[Dict[str, Any]] = []
    for fi in impacts:
        name = str(getattr(fi, "feature_name", "feature"))
        value = float(getattr(fi, "feature_value", 0.0))
        shap_value = float(getattr(fi, "impact_weight", 0.0))
        # Human-readable units lookup
        unit_map = {
            "vibration_rms": "mm/s",
            "bearing_temp": "°C",
            "rpm": "RPM",
            "pressure": "bar",
            "flow_rate": "L/m",
            "load_kw": "kW",
        }
        unit = unit_map.get(name, "")
        if math.isnan(value) or math.isinf(value):
            value = 0.0
        sign = "+" if shap_value >= 0 else ""
        desc = (
            f"SHAP contribution {sign}{shap_value:.2f} "
            f"(rank {getattr(fi, 'rank', 0)}, observed {value:g}{unit})"
        )
        features.append(
            UIShapFeature(
                name=name,
                value=f"{value:g}{unit}",
                shapValue=shap_value,
                desc=desc,
            ).model_dump(mode="json")
        )

    root_cause = getattr(explanation, "root_cause", None)
    rc_dict: Dict[str, Any] = {}
    if root_cause is not None:
        rc_dict = {
            "headline": str(getattr(root_cause, "headline", "")),
            "narrative": str(getattr(root_cause, "narrative", "")),
            "contributingFailureModes": list(
                getattr(root_cause, "contributing_failure_modes", []) or []
            ),
        }

    confidence_matrix = []
    for entry in list(getattr(explanation, "confidence_matrix", []) or []):
        if hasattr(entry, "model_dump"):
            confidence_matrix.append(entry.model_dump(mode="json"))
        else:
            confidence_matrix.append(
                {
                    "label": str(getattr(entry, "label", "")),
                    "confidence": float(getattr(entry, "confidence", 0.0)),
                }
            )

    method_val = getattr(explanation, "method", "SHAP")
    method_str = method_val.value if hasattr(method_val, "value") else str(method_val)
    scope_val = getattr(explanation, "scope", "LOCAL")
    scope_str = scope_val.value if hasattr(scope_val, "value") else str(scope_val)

    payload = UIShapExplanation(
        predictionId=prediction_id,
        assetId=asset_id,
        method=method_str,
        scope=scope_str,
        baseValue=float(getattr(explanation, "base_value", 0.0) or 0.0),
        predictionValue=float(getattr(explanation, "predicted_value", 0.0) or 0.0),
        features=features,
        confidenceMatrix=confidence_matrix,
        rootCause=rc_dict,
    )
    return payload.model_dump(mode="json", by_alias=False)


# ===========================================================================
# 5. Recommendation adapter — RecommendationResponse → List[UIRecommendationAction]
# ===========================================================================
def adapt_recommendations_to_actions(response: Any) -> List[Dict[str, Any]]:
    """Convert a Phase 8 :class:`RecommendationResponse` into action cards.

    The prescriptive-action panel renders one card per recommendation.
    The adapter flattens the rich Phase 8 model (decision log, cost
    estimate, RPN breakdown) into a card-friendly subset.
    """

    actions: List[Dict[str, Any]] = []
    for rec in list(getattr(response, "recommendations", []) or []):
        sop = None
        sop_link = getattr(rec, "sop_linkage", None)
        if sop_link is not None:
            sop = UISopLinkage(
                sopId=str(getattr(sop_link, "sop_id", "")),
                title=str(getattr(sop_link, "title", "")),
                revision=getattr(sop_link, "revision", None),
                effectiveness=float(getattr(sop_link, "effectiveness", 0.75) or 0.75),
            ).model_dump(mode="json")

        completion = getattr(rec, "recommended_completion_by", None)
        completion_str = (
            completion.isoformat()
            if hasattr(completion, "isoformat")
            else str(completion or "")
        )

        priority = _PRIORITY_MAP.get(
            str(getattr(rec, "priority", "MEDIUM")).upper(), UIActionPriority.MEDIUM
        )
        tier = _TIER_MAP.get(
            str(getattr(rec, "severity_tier", "MONITOR")).upper(), UISeverityTier.MONITOR
        )

        action_id_val = str(getattr(rec, "action_id", uuid.uuid4().hex[:10]))
        action_type_val = str(getattr(rec, "action_type", "INSPECT"))
        risk_score_val = float(getattr(rec, "risk_score_if_ignored", 0.0) or 0.0)
        cost_avoidance_val = float(getattr(rec, "estimated_cost_avoidance_usd", 0.0) or 0.0)

        actions.append(
            UIRecommendationAction(
                actionId=action_id_val,
                actionType=action_type_val,
                description=str(getattr(rec, "description", "")),
                priority=priority,
                severityTier=tier,
                riskScoreIfIgnored=risk_score_val,
                estimatedCostAvoidanceUsd=cost_avoidance_val,
                recommendedCompletionBy=completion_str,
                sop=sop,
                rank=int(getattr(rec, "rank", 1) or 1),
                
                # Phase 3 compatibility fields
                actionCardId=action_id_val,
                title=f"{action_type_val.title()} Recommendation" if action_type_val else "Recommendation",
                costAvoidance=cost_avoidance_val,
                riskScore=risk_score_val,
                completionDate=completion_str,
            ).model_dump(mode="json")
        )
    return actions


# ===========================================================================
# 6. Envelope normaliser — APIResponse[T] (backend) → UIAPIResponse[T] (frontend)
# ===========================================================================
def api_error_to_ui_error(
    *,
    error_code: str,
    message: str,
    details: Any = None,
) -> Dict[str, Any]:
    """Build a Section 11 ``UIAPIError`` (object form) from any backend error."""

    return UIAPIError(code=error_code, message=message, details=details).model_dump(
        mode="json"
    )


def to_ui_api_envelope(
    *,
    success: bool,
    data: Any,
    request_id: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Wrap any payload in the Section 11 :class:`UIAPIResponse` envelope.

    Backend :class:`app.models.common.APIResponse` uses a *string* error
    field, the frontend Section 11 contract uses an *object* error
    field. This normaliser bridges the two so the React side gets the
    exact shape the type system expects.
    """

    payload = {
        "success": bool(success),
        "data": data,
        "requestId": request_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if error is not None:
        # Coerce legacy string error into the object form
        if isinstance(error, str):
            payload["error"] = {"code": "AI_SERVICE_ERROR", "message": error, "details": None}
        else:
            payload["error"] = error
    else:
        payload["error"] = None
    return payload


# ===========================================================================
# 7. Asset / alert helpers (used by the dedicated UI endpoints)
# ===========================================================================
def adapt_asset(asset: Any) -> Dict[str, Any]:
    """Coerce any asset-like object into the Section 11 ``UIAsset`` shape."""

    # Fall back to id if name is missing *or* None
    name = getattr(asset, "name", None)
    if not name:
        name = getattr(asset, "id", "")
    return UIAsset(
        id=str(getattr(asset, "id", "")),
        name=str(name),
        type=str(getattr(asset, "type", "GENERIC")),
        status=UIAssetStatus(_enum_value(getattr(asset, "status", "OPERATIONAL"))),
        parentId=getattr(asset, "parentId", None) or getattr(asset, "parent_id", None),
    ).model_dump(mode="json")


def adapt_alert(alert: Any) -> Dict[str, Any]:
    """Coerce any alert-like object into the Section 11 ``UIAlert`` shape."""

    ts = getattr(alert, "timestamp", None)
    return {
        "id": str(getattr(alert, "id", uuid.uuid4().hex[:10])),
        "assetId": str(getattr(alert, "assetId", getattr(alert, "asset_id", ""))),
        "severity": str(getattr(alert, "severity", "INFO")),
        "message": str(getattr(alert, "message", getattr(alert, "description", ""))),
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "acknowledged": bool(getattr(alert, "acknowledged", False)),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _stable_id_hash(value: str) -> str:
    """Stable short hash used for deterministic UI ids when missing."""

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
