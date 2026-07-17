"""Phase 11 — Chat / agent-streaming event adapter.

Wraps the Phase 10 :class:`AgentState` stream and the Phase 9 LangGraph
runtime internals into clean, frontend-ready NDJSON event blocks.

Why a dedicated adapter? The component that renders the multi-agent
chat panel walks:

* a *timeline strip*   — one chip per state transition
* a *tool execution list* — one row per tool invocation
* a *source-chip tray*   — one chip per citation
* a *side graph panel*   — incremental sub-graph updates

The Phase 10 :class:`AgentState` exposes a ``state / message / payload``
triple, but the panel needs the additional ``tools / citations /
subgraph`` data sliced out of the payload. Doing the slicing here keeps
the runtime simple and the wire contract stable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from app.ai_service.integration.schemas.chat_event_schemas import (
    AgentStreamEvent,
    CitationRef,
    DiagnosticLogEntry,
    StreamEventType,
    SubgraphUpdatePacket,
    ToolExecutionEvent,
)

# ---------------------------------------------------------------------------
# State-name → event-type mapping
# ---------------------------------------------------------------------------
_STATE_TO_EVENT_TYPE = {
    "received": StreamEventType.STATE,
    "triaged": StreamEventType.STATE,
    "graphrag_retrieved": StreamEventType.STATE,
    "decision_evaluated": StreamEventType.STATE,
    "final": StreamEventType.FINAL,
    "error": StreamEventType.ERROR,
}


def _safe_iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Citation extraction
# ---------------------------------------------------------------------------
def _extract_citations(payload: Dict[str, Any]) -> List[CitationRef]:
    """Pull a ``citations`` list out of an :class:`AgentState` payload."""

    raw = payload.get("citations") or payload.get("vector_citations") or []
    out: List[CitationRef] = []
    for idx, c in enumerate(raw):
        if hasattr(c, "model_dump"):
            data = c.model_dump(mode="json")
        elif isinstance(c, dict):
            data = dict(c)
        else:
            data = {"citationId": f"cit-{idx}", "claimSpan": str(c)}
        out.append(
            CitationRef(
                citationId=str(
                    data.get("citation_id") or data.get("citationId") or f"cit-{uuid.uuid4().hex[:8]}"
                ),
                claimSpan=str(data.get("claim_span") or data.get("claimSpan") or ""),
                sourceDocument=data.get("source_document") or data.get("sourceDocument"),
                sourceType=data.get("source_type") or data.get("sourceType"),
                confidenceScore=float(data.get("confidence_score") or data.get("confidenceScore") or 0.0),
                pageNumber=data.get("page_number") or data.get("pageNumber"),
                url=data.get("url"),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Tool execution extraction
# ---------------------------------------------------------------------------
_TOOL_BY_STATE = {
    "graphrag_retrieved": "vector_search",
    "decision_evaluated": "decision_eval",
    "triaged": "graph_traversal",
}


def _extract_tools(state_name: str, payload: Dict[str, Any]) -> List[ToolExecutionEvent]:
    """Synthesise a tool-execution event from an :class:`AgentState` payload."""

    name = _TOOL_BY_STATE.get(state_name)
    if name is None:
        return []
    duration = float(payload.get("latency_ms") or payload.get("latencyMs") or 0.0)
    status = "degraded" if payload.get("degraded") else "succeeded"
    summary = (
        f"{name} completed in {duration:.1f} ms"
        if status == "succeeded"
        else f"{name} degraded ({payload.get('reason', 'unknown')})"
    )
    return [
        ToolExecutionEvent(
            toolName=name,  # type: ignore[arg-type]
            durationMs=duration,
            status=status,  # type: ignore[arg-type]
            summary=summary,
            resultCount=int(payload.get("vector_hits") or payload.get("recommendations") or 0),
        )
    ]


# ---------------------------------------------------------------------------
# Sub-graph update extraction
# ---------------------------------------------------------------------------
def _extract_subgraph(state_name: str, payload: Dict[str, Any]) -> Optional[SubgraphUpdatePacket]:
    """Pull a sub-graph update packet from a ``graphrag_retrieved`` state."""

    if state_name != "graphrag_retrieved" or payload.get("degraded"):
        return None
    nodes = payload.get("subgraph_nodes") or payload.get("graph_nodes") or []
    edges = payload.get("subgraph_edges") or payload.get("graph_edges") or []
    return SubgraphUpdatePacket(
        operation="add_node" if nodes else "add_edge",
        nodes=list(nodes) if isinstance(nodes, list) else [],
        edges=list(edges) if isinstance(edges, list) else [],
        highlightNodeIds=[str(n.get("id") if isinstance(n, dict) else n) for n in nodes]
        if isinstance(nodes, list)
        else [],
        highlightEdgeIds=[],
        narrative="Sub-graph context for the current diagnostic turn.",
    )


# ---------------------------------------------------------------------------
# Logs extraction
# ---------------------------------------------------------------------------
def _extract_logs(state_name: str, payload: Dict[str, Any]) -> List[DiagnosticLogEntry]:
    """One log entry per state transition for the panel's diagnostic strip."""

    msg = str(payload.get("message") or state_name)
    level = "error" if state_name == "error" else "info"
    return [DiagnosticLogEntry(level=level, message=msg, context={"state": state_name})]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def to_chat_event_block(
    state: Any,
    *,
    session_id: str,
    asset_id: Optional[str],
    sequence: int,
) -> Dict[str, Any]:
    """Convert a single :class:`AgentState` into one :class:`AgentStreamEvent` block."""

    state_name = str(getattr(state, "state", "received"))
    payload = dict(getattr(state, "payload", {}) or {})
    is_final = state_name == "final"
    is_error = state_name == "error"
    event = AgentStreamEvent(
        sessionId=session_id,
        assetId=asset_id,
        sequence=sequence,
        eventType=_STATE_TO_EVENT_TYPE.get(state_name, StreamEventType.STATE),
        state=state_name,
        message=str(getattr(state, "message", state_name)),
        payload=payload,
        tools=_extract_tools(state_name, payload),
        citations=_extract_citations(payload),
        subgraph=_extract_subgraph(state_name, payload),
        logs=_extract_logs(state_name, payload),
        isFinal=is_final,
        isError=is_error,
    )
    return event.model_dump(mode="json", by_alias=False)


async def to_chat_event_stream(
    states: List[Any],
    *,
    session_id: str,
    asset_id: Optional[str],
) -> AsyncIterator[Dict[str, Any]]:
    """Yield one event dict per :class:`AgentState` in input order.

    Emits a leading ``heartbeat`` event so the frontend's loading
    indicator can fire *immediately* on first byte, and appends a
    final ``final`` event so the panel knows to collapse the timeline
    strip even if the upstream runtime forgot to emit one.
    """

    # Initial heartbeat — gives the panel a deterministic first frame.
    yield AgentStreamEvent(
        sessionId=session_id,
        assetId=asset_id,
        sequence=0,
        eventType=StreamEventType.HEARTBEAT,
        message="Agent runtime connected.",
    ).model_dump(mode="json", by_alias=False)

    saw_final = False
    for idx, state in enumerate(states, start=1):
        block = to_chat_event_block(
            state,
            session_id=session_id,
            asset_id=asset_id,
            sequence=idx,
        )
        if block.get("isFinal"):
            saw_final = True
        yield block

    if not saw_final:
        yield AgentStreamEvent(
            sessionId=session_id,
            assetId=asset_id,
            sequence=len(states) + 1,
            eventType=StreamEventType.FINAL,
            state="final",
            message="Diagnostic turn completed (synthesised final event).",
            isFinal=True,
        ).model_dump(mode="json", by_alias=False)


def to_ui_chat_message(
    agent_response: Any,
    *,
    sender: str = "AI_ENGINE",
    fallback_message: str = "",
) -> Dict[str, Any]:
    """Convert an :class:`AgentChatResponse` into a Section 11 ``UIChat`` shape.

    The frontend's ``chat.service.ts`` writes messages of the form
    ``{ messageId, sender, payload, timestamp }``; this adapter
    surfaces the agent's ``final_answer`` as ``payload`` and uses the
    ``session_id`` to derive a deterministic messageId so reload-and-
    dedupe works on the client.
    """

    session_id = str(getattr(agent_response, "session_id", uuid.uuid4()))
    final = str(getattr(agent_response, "final_answer", "") or fallback_message)
    ts = getattr(agent_response, "generated_at", None)
    return {
        "messageId": f"msg-{session_id}",
        "sender": sender,
        "payload": final,
        "timestamp": _safe_iso(ts),
    }
