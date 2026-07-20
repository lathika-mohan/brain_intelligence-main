"""Phase 2 — Existing endpoint contract corrections (response shaping only).

This module is the single home for every *pure* response-shaping utility
used to align the existing Digital Twin, GraphRAG, and Explain (XAI)
endpoint payloads with the frontend specifications:

==================================  ==========================================
Correction area                     Utility
==================================  ==========================================
Digital Twin ``riskScore``          :func:`compute_top_level_risk_score`
Strict non-null arrays              :func:`sanitize_arrays`
camelCase-everywhere serialization  :func:`camelize_keys` / :func:`to_camel_case`
GraphRAG execution ``logs``         :func:`build_graphrag_execution_logs`
Node vocabulary alignment           :func:`normalize_node_id` / :func:`normalize_node_label` / :func:`normalize_relation_name`
Node type validation                :func:`validate_node_type`
XAI ``method`` query param          :func:`resolve_explain_method` / :class:`UnsupportedExplainMethodError`
==================================  ==========================================

Contract isolation guarantee: **nothing in this module touches the ML
algorithms, model inference, graph traversal, or business calculations.**
Every function operates on already-computed output dicts, right before
they are wrapped in the Phase 11 ``UIAPIResponse`` envelope.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


# ===========================================================================
# 1. camelCase serialization utilities
# ===========================================================================
_SNAKE_BOUNDARY = re.compile(r"_+([a-zA-Z0-9])")
_CAMEL_KEY = re.compile(r"^[a-z][A-Za-z0-9]*$")


def to_camel_case(name: str) -> str:
    """Convert a ``snake_case`` (or ``SCREAMING_SNAKE_CASE``) key to lower camelCase.

    Already-camelCase keys are returned unchanged. Leading underscores are
    preserved stripped-down (private keys are not expected on the wire).

    Examples
    --------
    >>> to_camel_case("shap_value")
    'shapValue'
    >>> to_camel_case("citation_id")
    'citationId'
    >>> to_camel_case("shapValue")
    'shapValue'
    """

    if not isinstance(name, str) or "_" not in name:
        return name
    head, _, tail = name.partition("_")
    head = head.lower()
    return head + _SNAKE_BOUNDARY.sub(lambda m: m.group(1).upper(), "_" + tail)


def camelize_keys(value: Any) -> Any:
    """Recursively rewrite every ``dict`` key in ``value`` to lower camelCase.

    Lists/tuples are traversed element-wise; scalars pass through
    untouched. This is the safety net that guarantees *no* snake_case key
    (e.g. a nested ``shap_value`` or ``citation_id`` leaked from a raw
    backend ``model_dump``) ever reaches the frontend contract.
    """

    if isinstance(value, Mapping):
        return {to_camel_case(str(k)): camelize_keys(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [camelize_keys(item) for item in value]
    return value


def find_non_camel_keys(value: Any, *, _path: str = "") -> List[str]:
    """Return the dotted paths of any key that is not lower camelCase.

    Used by the contract tests (and available at runtime for spot
    assertions) to prove the *camelCase everywhere* invariant.
    """

    offenders: List[str] = []
    if isinstance(value, Mapping):
        for key, sub in value.items():
            key_str = str(key)
            here = f"{_path}.{key_str}" if _path else key_str
            if not _CAMEL_KEY.match(key_str):
                offenders.append(here)
            offenders.extend(find_non_camel_keys(sub, _path=here))
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            offenders.extend(find_non_camel_keys(item, _path=f"{_path}[{idx}]"))
    return offenders


# ===========================================================================
# 2. Strict non-null array sanitizer
# ===========================================================================
# Keys that must always serialize as JSON arrays across the three endpoint
# domains. ``None`` instances of any of these are rewritten to ``[]``.
ARRAY_KEY_HINTS = frozenset(
    {
        # Digital twin
        "history", "frames", "metrics", "readings", "logs",
        # GraphRAG
        "nodes", "edges", "highlightedNodes", "highlightedEdges",
        "citations", "chunks", "supportingNodes", "supportingEdges",
        # XAI
        "features", "confidenceMatrix", "bars", "positive", "negative",
        "contributingFailureModes", "globalFeatureImportance",
        # Shared / misc
        "anomalyFlags", "anomalousSensors", "recommendations", "actions",
        "states", "events", "series", "points",
    }
)


def sanitize_arrays(value: Any, *, array_keys: Optional[Iterable[str]] = None) -> Any:
    """Recursively replace ``None`` array slots with ``[]`` before serialization.

    * Any key present in ``array_keys`` (default: :data:`ARRAY_KEY_HINTS`)
      whose value is ``None`` becomes ``[]``.
    * Any key whose value is a tuple is materialised as a list.
    * ``None`` elements *inside* a list are dropped (a list attribute must
      never evaluate to ``[null]`` either).

    Scalars that are not array-typed pass through untouched — the
    sanitizer never invents data, it only enforces the *non-null array*
    contract.
    """

    keys = frozenset(array_keys) if array_keys is not None else ARRAY_KEY_HINTS

    def _walk(node: Any, key: Optional[str]) -> Any:
        if node is None:
            return [] if (key in keys) else None
        if isinstance(node, Mapping):
            return {str(k): _walk(v, str(k)) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [_walk(item, None) for item in node if item is not None]
        return node

    return _walk(value, None)


# ===========================================================================
# 3. Digital Twin — top-level riskScore
# ===========================================================================
def clamp_risk_score(value: Any, *, default: float = 0.0) -> float:
    """Coerce any candidate risk value into a finite ``0..100`` float.

    NaN / ±inf / non-numeric candidates collapse to ``default`` so the
    frontend gauge never receives an unrenderable value.
    """

    try:
        val = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(val) or math.isinf(val):
        return float(default)
    return float(max(0.0, min(100.0, val)))


def compute_top_level_risk_score(
    *,
    inference: Optional[Any] = None,
    telemetry_risk_score: Optional[float] = None,
) -> float:
    """Compute the Digital Twin payload's *top-level* ``riskScore``.

    Domain-standard precedence (response-shaping only — no business logic
    is altered; we only *read* the already-computed inference outputs):

    1. ``inference.failure_probability.probability × 100`` — the AI Risk
       Index the predictive engine already produces.
    2. The telemetry card's ``riskScore`` (same derivation, kept for
       engines that populate telemetry directly).
    3. Safe default ``0.0`` — a populated numeric field, never ``null``.
    """

    if inference is not None:
        fp = getattr(inference, "failure_probability", None)
        probability = getattr(fp, "probability", None) if fp is not None else None
        if probability is not None:
            return clamp_risk_score(float(probability) * 100.0, default=0.0)
    if telemetry_risk_score is not None:
        return clamp_risk_score(telemetry_risk_score, default=0.0)
    return 0.0


# ===========================================================================
# 4. GraphRAG — node vocabulary alignment + node type validation
# ===========================================================================
# The recognized domain ontology exposed to the frontend panel. Any node
# type outside this closed set is *mapped* (preferred) or deterministically
# degraded to ``component`` — never leaked raw.
FRONTEND_NODE_TYPES = frozenset({"asset", "component", "anomaly", "procedure", "record"})

# Raw backend / Phase 1 ontology vocabulary → frontend vocabulary.
NODE_TYPE_SYNONYMS: Dict[str, str] = {
    "asset": "asset",
    "equipment": "asset",
    "machine": "asset",
    "system": "asset",
    "component": "component",
    "part": "component",
    "subassembly": "component",
    "sensor": "component",
    "bearing": "component",
    "anomaly": "anomaly",
    "failure_mode": "anomaly",
    "failuremode": "anomaly",
    "failure": "anomaly",
    "fault": "anomaly",
    "defect": "anomaly",
    "alert": "anomaly",
    "procedure": "procedure",
    "sop": "procedure",
    "standard_operating_procedure": "procedure",
    "workinstruction": "procedure",
    "work_instruction": "procedure",
    "record": "record",
    "incident": "record",
    "workorder": "record",
    "work_order": "record",
    "event": "record",
    "maintenance_record": "record",
    "document": "record",
}

DEFAULT_NODE_TYPE = "component"

# Canonical relation vocabulary for the panel's edge labels.
_CANONICAL_RELATIONS = {
    "HAS_COMPONENT", "HAS_FAILURE_MODE", "HAS_ANOMALY", "MITIGATED_BY",
    "DOCUMENTED_IN", "OCCURRED_ON", "OBSERVED_ON", "RELATED_TO",
    "CAUSED_BY", "RESOLVED_BY", "PART_OF", "MONITORS",
}
_RELATION_SYNONYMS = {
    "MITIGATES": "MITIGATED_BY",
    "FIXED_BY": "RESOLVED_BY",
    "HAS_FAULT": "HAS_FAILURE_MODE",
    "HAS_FAILURE": "HAS_FAILURE_MODE",
    "CHILD_OF": "PART_OF",
}


def validate_node_type(raw_type: Any) -> str:
    """Map a raw backend node *type* onto the closed frontend vocabulary.

    Returns one of ``asset | component | anomaly | procedure | record``.
    Unknown/raw ontology types are normalised (case/space/underscore
    insensitive) through :data:`NODE_TYPE_SYNONYMS` and degrade
    deterministically to ``component`` so no unrecognized type ever
    reaches the panel.
    """

    token = re.sub(r"[\s\-]+", "_", str(raw_type or "").strip().lower())
    mapped = NODE_TYPE_SYNONYMS.get(token) or NODE_TYPE_SYNONYMS.get(token.replace("_", ""))
    if mapped in FRONTEND_NODE_TYPES:
        return mapped
    return DEFAULT_NODE_TYPE


def normalize_node_id(raw_id: Any) -> str:
    """Standardise a node identifier (trimmed, single-spaced, string)."""

    return re.sub(r"\s+", " ", str(raw_id or "")).strip()


def normalize_node_label(raw_label: Any, *, node_id: str = "") -> str:
    """Standardise a node label; falls back to the id's local name.

    ``asset:P-101A`` with no label renders as ``P-101A`` — the fragment
    after the namespace separator — rather than a blank chip.
    """

    label = re.sub(r"\s+", " ", str(raw_label or "")).strip()
    if label:
        return label
    local = node_id.rsplit(":", 1)[-1] if ":" in node_id else node_id
    return local or "node"


def normalize_relation_name(raw_relationship: Any) -> str:
    """Standardise an edge relation name to the canonical UPPER_SNAKE set.

    Known display synonyms are folded onto the canonical spellings; any
    other free-text relation is normalized to ``UPPER_SNAKE_CASE`` (with
    ``RELATED_TO`` as the empty-string fallback) so the panel's edge
    labels stay consistent.
    """

    token = re.sub(r"[\s\-]+", "_", str(raw_relationship or "").strip().upper())
    token = re.sub(r"_+", "_", token).strip("_")
    token = _RELATION_SYNONYMS.get(token, token)
    if not token:
        return "RELATED_TO"
    return token


# ===========================================================================
# 5. GraphRAG — execution logs (retrieval / graph-traversal trace)
# ===========================================================================
def build_graphrag_execution_logs(
    *,
    query: Optional[str],
    vector_hits: int,
    node_count: int,
    edge_count: int,
    citation_count: int,
    answer_ready: bool,
    overall_confidence: Optional[float] = None,
    remapped_types: Optional[Sequence[str]] = None,
    citations: Optional[Sequence[Any]] = None,
    latency_ms: Optional[float] = None,
) -> List[str]:
    """Build the chronological execution-log trace for the GraphRAG panel.

    Entries are plain strings (the panel renders them verbatim into its
    "loading logs" timeline) and detail every retrieval / graph-traversal
    step in order: vector search → traversal → type validation → citation
    binding → LLM synthesis.
    """

    logs: List[str] = []
    step = 1

    def _emit(text: str) -> None:
        nonlocal step
        logs.append(f"STEP {step}: {text}")
        step += 1

    if query:
        _emit(f"vector_search: embedded query '{query}'")
    else:
        _emit("vector_search: embedded query")
    _emit(f"vector_search: {int(vector_hits)} chunk hit(s) retrieved")
    _emit(
        f"graph_traversal: expanded {int(node_count)} node(s) / "
        f"{int(edge_count)} edge(s) from seed hits"
    )
    if remapped_types:
        distinct = ", ".join(sorted(set(remapped_types)))
        _emit(f"node_type_validation: remapped raw ontology type(s) [{distinct}] into panel vocabulary")
    else:
        _emit("node_type_validation: all node types within panel vocabulary")
    _emit(f"citation_binding: attached {int(citation_count)} citation(s)")
    citations = list(citations or [])[:5]
    for idx, citation in enumerate(citations):
        label = (
            getattr(citation, "source_type", None)
            or getattr(citation, "source_document", None)
            or "citation"
        )
        confidence = getattr(citation, "confidence_score", 0.0) or 0.0
        _emit(f"citation_binding: [{idx + 1}] {label} (confidence={confidence:.2f})")
    if answer_ready:
        confidence_txt = (
            f", overall_confidence={overall_confidence:.2f}"
            if overall_confidence is not None
            else ""
        )
        _emit(f"llm_synthesis: answer drafted{confidence_txt}")
    else:
        _emit("llm_synthesis: awaiting response context")
    if latency_ms is not None:
        _emit(f"completed: total latency {float(latency_ms):.1f} ms")
    return logs


# ===========================================================================
# 6. XAI — method query-parameter resolution
# ===========================================================================
SUPPORTED_EXPLAIN_METHODS = ("SHAP", "LIME", "INTEGRATED_GRADIENTS", "PERMUTATION")

# Case-insensitive aliases the frontend may legitimately send
# (``?method=shap``, ``?method=lime``, ``?method=integrated_gradients``).
EXPLAIN_METHOD_ALIASES: Dict[str, str] = {
    "shap": "SHAP",
    "lime": "LIME",
    "integrated_gradients": "INTEGRATED_GRADIENTS",
    "integratedgradients": "INTEGRATED_GRADIENTS",
    "integrated-gradients": "INTEGRATED_GRADIENTS",
    "integrated gradients": "INTEGRATED_GRADIENTS",
    "ig": "INTEGRATED_GRADIENTS",
    "gradcam": "INTEGRATED_GRADIENTS",
    "permutation": "PERMUTATION",
    "permutation_importance": "PERMUTATION",
}


class UnsupportedExplainMethodError(ValueError):
    """Raised when ``?method=`` is not in the supported vocabulary.

    The route handler converts this into a deterministic **HTTP 400**
    validation error inside the ``UIAPIResponse`` envelope.
    """

    def __init__(self, method: Any) -> None:
        self.method = method
        super().__init__(
            f"Unsupported explainability method {method!r}. "
            f"Supported methods: {', '.join(SUPPORTED_EXPLAIN_METHODS)}."
        )


def resolve_explain_method(raw_method: Any) -> str:
    """Resolve a user-supplied ``method`` query value to its canonical enum name.

    Resolution is case-insensitive and alias-aware::

        ?method=shap                  → "SHAP"
        ?method=LIME                  → "LIME"
        ?method=integrated_gradients  → "INTEGRATED_GRADIENTS"

    Raises :class:`UnsupportedExplainMethodError` for anything else so the
    handler can emit a clear HTTP 400 — *not* a 422 or a silent fallback.
    """

    if raw_method is None or str(raw_method).strip() == "":
        return "SHAP"
    token = str(raw_method).strip().lower()
    canonical = EXPLAIN_METHOD_ALIASES.get(token) or EXPLAIN_METHOD_ALIASES.get(
        token.replace("_", "")
    )
    if canonical is None:
        raise UnsupportedExplainMethodError(raw_method)
    return canonical


# ===========================================================================
# 7. XAI — per-method payload tailoring (labels only; scores untouched)
# ===========================================================================
METHOD_DESCRIPTORS: Dict[str, str] = {
    "SHAP": "SHAP contribution",
    "LIME": "LIME local linear weight",
    "INTEGRATED_GRADIENTS": "Integrated-gradients attribution",
    "PERMUTATION": "Permutation importance",
}


def method_descriptor(canonical_method: str) -> str:
    """Human label for a contribution value under the requested method."""

    return METHOD_DESCRIPTORS.get(str(canonical_method).upper(), "Feature contribution")


# ===========================================================================
# 8. XAI — feature sorting by absolute contribution magnitude
# ===========================================================================
def sort_features_by_impact(features: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return ``features`` sorted desc by ``|shapValue|`` (stable, pure).

    Top drivers appear first so the waterfall / bar / force layouts can
    render in a single pass. NaN/inf contributions are treated as 0.0 so
    they sink to the bottom rather than crashing the comparator.
    """

    def _magnitude(feature: Mapping[str, Any]) -> float:
        try:
            value = abs(float(feature.get("shapValue", 0.0) or 0.0))
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return value

    return sorted((dict(f) for f in features), key=_magnitude, reverse=True)
