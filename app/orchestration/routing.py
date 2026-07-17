"""Deterministic routing and guardrails for the Phase 9 LangGraph supervisor."""
from __future__ import annotations

import re
from typing import List

from app.orchestration.state import AgentName, AgentState

_ASSET_PATTERNS = [
    re.compile(r"\b(?:asset|pump|compressor|motor|turbine|line)[\s\-_]*([A-Za-z0-9]+)\b", re.I),
    re.compile(r"\b([A-Za-z]+[-_][A-Za-z0-9]+)\b"),
]

_DIAGNOSTIC_WORDS = {"why", "diagnose", "diagnostic", "root cause", "cause", "high", "low", "anomaly", "fault", "risk", "report"}
_PREDICT_WORDS = {"predict", "rul", "remaining", "failure probability", "forecast", "anomaly"}
_DECISION_WORDS = {"recommend", "maintenance", "sop", "action", "risk report", "prioritize", "schedule"}
_KNOWLEDGE_WORDS = {"relationship", "ontology", "connected", "graph", "asset hierarchy", "component"}
_RETRIEVAL_WORDS = {"manual", "documentation", "procedure", "spec", "datasheet", "context"}


def extract_asset_id(query_text: str) -> str | None:
    for pattern in _ASSET_PATTERNS:
        match = pattern.search(query_text)
        if not match:
            continue
        value = match.group(1)
        # Preserve phrases like Pump-2 via full match when pattern one strips prefix.
        if "pump" in match.group(0).lower() and not value.lower().startswith("pump"):
            return f"Pump-{value}" if not value.startswith("-") else f"Pump{value}"
        if "compressor" in match.group(0).lower() and not value.lower().startswith("compressor"):
            return f"Compressor-{value}"
        return value
    return None


def plan_route(state: AgentState) -> List[AgentName]:
    q = state.query_text.lower()
    if not state.active_asset_id:
        state.active_asset_id = extract_asset_id(state.query_text)

    diagnostic = any(word in q for word in _DIAGNOSTIC_WORDS)
    wants_prediction = any(word in q for word in _PREDICT_WORDS)
    wants_decision = any(word in q for word in _DECISION_WORDS)
    wants_knowledge = any(word in q for word in _KNOWLEDGE_WORDS)
    wants_retrieval = any(word in q for word in _RETRIEVAL_WORDS)

    if diagnostic or (wants_prediction and wants_decision):
        return [
            AgentName.RETRIEVAL,
            AgentName.KNOWLEDGE,
            AgentName.PREDICTION,
            AgentName.EXPLANATION,
            AgentName.DECISION,
            AgentName.FINALIZER,
        ]
    if wants_decision:
        return [AgentName.PREDICTION, AgentName.EXPLANATION, AgentName.DECISION, AgentName.FINALIZER]
    if wants_prediction:
        return [AgentName.PREDICTION, AgentName.EXPLANATION, AgentName.FINALIZER]
    if wants_knowledge:
        return [AgentName.KNOWLEDGE, AgentName.RETRIEVAL, AgentName.FINALIZER]
    if wants_retrieval:
        return [AgentName.RETRIEVAL, AgentName.FINALIZER]
    return [AgentName.RETRIEVAL, AgentName.KNOWLEDGE, AgentName.FINALIZER]


def supervisor_next(state: AgentState) -> str:
    if state.terminal or state.transition_count >= state.max_transitions:
        state.terminal = True
        return AgentName.END.value
    if not state.route_plan:
        state.route_plan = plan_route(state)
    if not state.route_plan:
        return AgentName.FINALIZER.value
    nxt = state.route_plan.pop(0)
    state.active_agent = nxt
    return nxt.value


def next_after_agent(state: AgentState) -> str:
    if state.transition_count >= state.max_transitions:
        state.terminal = True
        return AgentName.FINALIZER.value
    return AgentName.SUPERVISOR.value
