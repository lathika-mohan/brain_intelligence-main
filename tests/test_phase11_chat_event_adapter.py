"""Phase 11 — Unit tests for the chat event adapter (multi-agent streaming)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from app.ai_service.integration.adapters.chat_event_adapter import (
    to_chat_event_block,
    to_chat_event_stream,
    to_ui_chat_message,
)


class _Stub:
    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def states() -> List[_Stub]:
    return [
        _Stub(
            state="received",
            message="Accepted diagnostic chat turn.",
            payload={"messages": 1},
        ),
        _Stub(
            state="triaged",
            message="Identified asset and selected GraphRAG/decision tools.",
            payload={"asset_id": "P-101A"},
        ),
        _Stub(
            state="graphrag_retrieved",
            message="Retrieved fused vector/graph context.",
            payload={
                "vector_hits": 4,
                "graph_nodes": 5,
                "citations": [
                    {"citation_id": "c1", "source_document": "sop.pdf", "confidence_score": 0.9}
                ],
            },
        ),
        _Stub(
            state="decision_evaluated",
            message="Evaluated risk-ranked maintenance actions.",
            payload={"recommendations": 2, "overall_risk_score": 0.78},
        ),
        _Stub(
            state="final",
            message="Diagnostic turn completed.",
            payload={"response_length": 240},
        ),
    ]


class TestToChatEventBlock:
    def test_extracts_state_message_payload(self, states: List[_Stub]) -> None:
        block = to_chat_event_block(
            states[0], session_id="sess-1", asset_id="P-101A", sequence=1
        )
        assert block["sessionId"] == "sess-1"
        assert block["assetId"] == "P-101A"
        assert block["sequence"] == 1
        assert block["state"] == "received"
        assert block["message"] == "Accepted diagnostic chat turn."

    def test_graphrag_state_includes_citations_and_tools(self, states: List[_Stub]) -> None:
        block = to_chat_event_block(
            states[2], session_id="sess-1", asset_id="P-101A", sequence=3
        )
        assert block["eventType"] == "state"
        assert len(block["citations"]) == 1
        assert block["citations"][0]["citationId"] == "c1"
        assert len(block["tools"]) == 1
        assert block["tools"][0]["toolName"] == "vector_search"
        assert block["tools"][0]["resultCount"] == 4
        assert block["subgraph"] is not None
        assert block["subgraph"]["operation"] in {"add_node", "add_edge"}

    def test_decision_state_emits_decision_eval_tool(self, states: List[_Stub]) -> None:
        block = to_chat_event_block(
            states[3], session_id="sess-1", asset_id="P-101A", sequence=4
        )
        tools = block["tools"]
        assert any(t["toolName"] == "decision_eval" for t in tools)

    def test_final_state_marks_is_final(self, states: List[_Stub]) -> None:
        block = to_chat_event_block(
            states[-1], session_id="sess-1", asset_id="P-101A", sequence=5
        )
        assert block["isFinal"] is True
        assert block["eventType"] == "final"


class TestToChatEventStream:
    @pytest.mark.asyncio
    async def test_emits_heartbeat_first(self, states: List[_Stub]) -> None:
        events: list = []
        async for block in to_chat_event_stream(
            states, session_id="sess-1", asset_id="P-101A"
        ):
            events.append(block)
        assert events[0]["eventType"] == "heartbeat"
        assert events[0]["sequence"] == 0

    @pytest.mark.asyncio
    async def test_emits_one_block_per_state(self, states: List[_Stub]) -> None:
        events: list = []
        async for block in to_chat_event_stream(
            states, session_id="sess-1", asset_id="P-101A"
        ):
            events.append(block)
        # 1 heartbeat + len(states) state events
        assert len(events) == 1 + len(states)

    @pytest.mark.asyncio
    async def test_sequences_are_monotonic(self, states: List[_Stub]) -> None:
        events: list = []
        async for block in to_chat_event_stream(
            states, session_id="sess-1", asset_id="P-101A"
        ):
            events.append(block)
        sequences = [e["sequence"] for e in events]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)

    @pytest.mark.asyncio
    async def test_synthesises_final_event_when_missing(self) -> None:
        events: list = []
        async for block in to_chat_event_stream(
            [_Stub(state="received", message="x", payload={})],
            session_id="sess-1",
            asset_id="P-101A",
        ):
            events.append(block)
        # heartbeat + received + synthesised final
        assert events[-1]["isFinal"] is True


class TestToUiChatMessage:
    def test_section_11_chat_envelope(self) -> None:
        response = _Stub(
            session_id="sess-1",
            final_answer="P-101A shows bearing wear signature.",
            generated_at=datetime.now(timezone.utc),
        )
        chat = to_ui_chat_message(response)
        assert set(chat.keys()) == {"messageId", "sender", "payload", "timestamp"}
        assert chat["sender"] == "AI_ENGINE"
        assert "bearing wear" in chat["payload"]

    def test_message_id_is_deterministic(self) -> None:
        response = _Stub(session_id="sess-X", final_answer="y", generated_at=datetime.now(timezone.utc))
        chat_a = to_ui_chat_message(response)
        chat_b = to_ui_chat_message(response)
        assert chat_a["messageId"] == chat_b["messageId"]
