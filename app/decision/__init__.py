"""
Phase 8 — AI Decision Engine.

Converts raw Phase 6 (Predictive Maintenance) / Phase 7 (XAI) outputs into
prioritized, risk-managed, SOP-backed prescriptive actions behind
``POST /api/v1/decision/recommend`` (frozen contract — ``docs/api_contracts.md``
§4, ``app/models/decision.py``).

Modules
-------
rule_engine.py
    Multi-criteria severity classifier (IMMINENT / SCHEDULED / MONITOR) +
    asset-criticality prioritization.
risk_scorer.py
    Quantitative RPN = P x S x D risk scoring + cost-of-inaction modelling.
sop_matcher.py
    Graph-driven SOP retrieval keyed off Phase 7 root-cause failure modes,
    with a deterministic offline fallback catalog when Neo4j is unreachable.
decision_service.py
    Orchestrator: wires prediction + explainability + rules + risk + SOPs
    into the frozen ``RecommendationResponse`` contract, with a full
    ``decision_log`` audit trail.

No UI, dashboard, or frontend code lives here — this is the backend service
boundary consumed by ``app/api/v1/decision.py``.
"""
from __future__ import annotations

from app.decision.rule_engine import PredictionSignal, RuleEngine, SeverityClassification
from app.decision.risk_scorer import RiskScorer
from app.decision.sop_matcher import SopMatcher
from app.decision.decision_service import DecisionService, get_decision_service

__all__ = [
    "PredictionSignal",
    "RuleEngine",
    "SeverityClassification",
    "RiskScorer",
    "SopMatcher",
    "DecisionService",
    "get_decision_service",
]
