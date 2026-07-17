"""Chat-streaming wire schemas.

The Phase 9 LangGraph diagnostic agent emits a sequence of structured
state transitions. Phase 11 normalises those into clean NDJSON event
blocks that the Next.js multi-agent chat panel can render directly:

* ``state``     — semantic state name (received / triaged / graphrag_retrieved
                  / decision_evaluated / final / error)
* ``message``   — human-readable progress text shown in the timeline strip
* ``payload``   — structured context for the panel's expandable sub-views
* ``tools``     — list of tool-execution events (vector_search, graph_traversal,
                  decision_eval, llm_synthesis, sop_lookup)
* ``citations`` — flattened list of citation references rendered in the
                  source-chip tray
* ``subgraph``  — incremental sub-graph update packet for the side panel

These schemas are deliberately additive over the Phase 10
:class:`AgentState` model — the upstream agent runtime still emits the
exact same state vocabulary, and the chat_event_adapter wraps each
state with a deterministic event_id, monotonic sequence, and the
extra tool/citation metadata Member 4 wants.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StreamEventType(str, Enum):
    """High-level event kind rendered as a coloured chip in the chat timeline."""

    STATE = "state"
    TOOL = "tool"
    CITATION = "citation"
    SUBGRAPH = "subgraph"
    FINAL = "final"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class CitationRef(BaseModel):
    """A single citation surfaced in the source-chip tray."""

    model_config = ConfigDict(extra="forbid")

    citationId: str
    claimSpan: str = ""
    sourceDocument: Optional[str] = None
    sourceType: Optional[str] = None
    confidenceScore: float = 0.0
    pageNumber: Optional[int] = None
    url: Optional[str] = None


class ToolExecutionEvent(BaseModel):
    """One tool invocation the agent performed during a turn."""

    model_config = ConfigDict(extra="forbid")

    toolId: str = Field(default_factory=lambda: f"tool-{uuid.uuid4().hex[:8]}")
    toolName: str  # one of: vector_search, graph_traversal, decision_eval, llm_synthesis, sop_lookup, telemetry_fetch, xai_explain
    startedAt: datetime = Field(default_factory=datetime.utcnow)
    durationMs: float = 0.0
    status: str = "succeeded"  # started | succeeded | degraded | failed
    summary: str = ""
    resultCount: int = 0


class SubgraphUpdatePacket(BaseModel):
    """Incremental graph update consumed by the side panel.

    The chat panel keeps an in-memory copy of the *active sub-graph* and
    appends/replaces nodes + edges on every ``subgraph`` event, so the
    graph renderer can animate them as the agent reasons.
    """

    model_config = ConfigDict(extra="forbid")

    packetId: str = Field(default_factory=lambda: f"sg-{uuid.uuid4().hex[:8]}")
    operation: str = "add_node"  # add_node | add_edge | highlight | clear
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    highlightNodeIds: List[str] = Field(default_factory=list)
    highlightEdgeIds: List[str] = Field(default_factory=list)
    narrative: str = ""


class DiagnosticLogEntry(BaseModel):
    """One ``logs`` line as rendered by ``GraphRagPanel.tsx``.

    The GraphRagPanel walks an array of plain strings with
    ``setLoadingLogs((prev) => [...prev, data.logs[currentStep]])``
    so we always emit the textual variant. The structured extras stay
    on the parent event for the diagnostic expansion panel.
    """

    model_config = ConfigDict(extra="forbid")

    logId: str = Field(default_factory=lambda: f"log-{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str = "info"  # info | warn | error | debug
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentStreamEvent(BaseModel):
    """One NDJSON line on the ``/api/v1/ai/agent/chat?stream=true`` response."""

    model_config = ConfigDict(extra="forbid")

    eventId: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:10]}")
    sequence: int = Field(default=0, ge=0, description="Monotonic within one session.")
    sessionId: str
    assetId: Optional[str] = None
    eventType: StreamEventType = StreamEventType.STATE
    state: Optional[str] = Field(
        default=None,
        description="Mirrors AgentStateName: received / triaged / graphrag_retrieved / ...",
    )
    message: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    tools: List[ToolExecutionEvent] = Field(default_factory=list)
    citations: List[CitationRef] = Field(default_factory=list)
    subgraph: Optional[SubgraphUpdatePacket] = None
    logs: List[DiagnosticLogEntry] = Field(default_factory=list)
    generatedAt: datetime = Field(default_factory=datetime.utcnow)
    isFinal: bool = False
    isError: bool = False
