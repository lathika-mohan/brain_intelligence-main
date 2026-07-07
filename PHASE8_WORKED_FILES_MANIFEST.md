# Phase 8 — AI Decision Engine · Worked Files Manifest

**Member 3 (AI & Knowledge Engineer)** — Deterministic prescriptive-action
layer that converts raw Phase 6 (Predictive Maintenance) predictions and
Phase 7 (XAI) root-cause explanations into prioritized, risk-managed,
SOP-backed operational recommendations behind
`POST /api/v1/decision/recommend`, matching the frozen Phase 0 contract
(`docs/api_contracts.md` §4).

> ✅ Zero UI scaffolding. No files under `src/` were touched. Strictly
> backend Python service layer (`app/decision/`, `app/api/v1/decision.py`,
> `app/models/decision.py`).

---

## New files

| File | Purpose |
|---|---|
| `app/decision/__init__.py` | Phase 8 package — re-exports the public rule engine / risk scorer / SOP matcher / decision service API. |
| `app/decision/rule_engine.py` | Multi-criteria rule processor. `PredictionSignal` normalises Phase 6 (RUL, failure probability, anomaly) + Phase 7 (root-cause sensors) inputs. `classify_severity()` runs an 8-rule deterministic classification matrix → `IMMINENT` / `SCHEDULED` / `MONITOR`, recording every rule (fired or not) for audit. `asset_criticality_weight()` maps a Neo4j `Asset.criticality` tier (A/B/C) to a numeric weight so a bottleneck asset outranks an identical failure profile on a redundant backup unit. `RuleEngine.prioritize()` ranks multiple simultaneous alerts by tier then criticality-weighted escalation score. |
| `app/decision/risk_scorer.py` | Quantitative risk scoring: `RiskScorer.score()` implements the standard **RPN = P(Failure) × S(Severity) × D(Detectability)** equation on the classic 1–10 FMEA scale (max 1000, matching `FailureMode.risk_priority_number` in the Phase 1 ontology). `P` comes from the Phase 6 failure-probability output; `S` is pulled from the graph's `FailureMode.severity_tier` (with a legacy RPN-hint fallback); `D` is calculated **inversely proportional** to the Isolation Forest anomaly confidence. `RiskScorer.estimate_cost()` implements the cost-of-inaction model (unplanned downtime vs. planned maintenance cost avoidance). |
| `app/decision/sop_matcher.py` | Graph-driven SOP retrieval. `build_sop_lookup_query()` is a pure, unit-testable Cypher builder that traverses `(:FailureMode)-[:MITIGATED_BY]->(:SOP)-[:HAS_STEP]->(:SOPStep)` plus `REQUIRES_TOOL` / `HAS_HAZARD` per the Phase 1 ontology edge catalogue. `records_to_sop_bundle()` maps raw records into `SOPLinkage` / `SOPStepDetail` payloads sorted by `MITIGATED_BY.effectiveness` (economic/operational efficiency). `SopMatcher` uses the same fast-bypass pattern as `xai_service.py` (only attempts a live Neo4j call when a driver is already initialised) and falls back to a small deterministic offline SOP catalogue (bearing-overheat + general-diagnostic procedures, complete with safety hazards / PPE / hold points) so the engine never returns an empty recommendation. |
| `app/decision/decision_service.py` | Orchestrator (`DecisionService.recommend()`). Pulls live Phase 6 inference (`PredictionService.infer`) + Phase 7 explanation (`XaiService.explain`) — degrading gracefully to conservative defaults if either fails — enriches with graph-sourced asset criticality / failure-mode severity, runs the rule engine + risk scorer + SOP matcher, and assembles the frozen `RecommendationResponse` contract plus the additive `sop_steps` and auditable `decision_log`. |
| `app/api/v1/decision.py` | FastAPI router: `POST /decision/recommend` (200 / 500 with graceful degradation logging), `GET /decision/health` (active rule thresholds + criticality weights + FMEA severity scale, for ops visibility). |
| `tests/test_phase8_decision.py` | 54 pytest cases across 5 suites: severity-classification edge cases (negative/zero RUL, probability force-escalation, simultaneous multi-sensor failures, ontology CRITICAL floor), asset-criticality weighting + prioritization (bottleneck-over-backup), RPN equation correctness + detectability inverse-proportionality + cost modelling, SOP query-builder purity + record mapping + offline-fallback completeness, end-to-end `DecisionService` orchestration, and exact frontend/API JSON contract conformance via `TestClient`. |
| `PHASE8_WORKED_FILES_MANIFEST.md` | This file. |

## Modified files

| File | Change |
|---|---|
| `app/models/decision.py` | Replaced the 4-field Phase 0 stub with the frozen §4 contract (`RecommendationRequest`, `Recommendation`, `SOPLinkage`, `RecommendationResponse`) plus Phase 8 additive audit models (`SOPStepDetail`, `TriggeredRule`, `RiskFactorBreakdown`, `CostEstimate`, `DecisionLogEntry`, `SeverityTier`, `PriorityLevel`, `MaintenanceActionType`). The original Phase 0 stub classes (`DecisionRecommendRequest` / `DecisionRecommendation` / `DecisionRecommendResponse`) are preserved verbatim for backward compatibility, matching the pattern already used in `app/models/predictive.py` and `app/models/xai.py`. |
| `app/core/config.py` | Added Phase 8 tunables under "Decision Engine": severity-classification RUL/probability thresholds, default asset-criticality weight, cost-of-inaction defaults (downtime rate, repair hours, planned-maintenance discount), and the RPN normalisation ceiling. |
| `app/api/v1/router.py` | Mounted the Phase 8 decision router at `/decision` (same try/except degrade-gracefully pattern as Phases 3–6). Updated the module docstring — the Decision Engine is no longer listed as "owned by another team member" now that Phase 8 implements it. |
| `app/api/v1/xai.py` | **Bug fix (integration wiring):** the router imported a non-existent `TelemetrySimulator` class from `app.predictive.telemetry_simulator` (that module only exports the `generate_episode` / `load_run_to_failure_episodes` functions used elsewhere in the codebase, e.g. `tests/test_phase7_xai.py`). This silently broke `xai_router` import at startup (caught by the router aggregator's try/except and logged as a warning), meaning `/api/v1/xai/explain` was never actually mounted. Fixed to call `generate_episode(asset_id=...)` directly — the same call already used by the Phase 7 test suite — restoring the XAI endpoint the Phase 8 Decision Engine depends on for root-cause sensor input. |

---

## How it fits together (data flow)

```
POST /api/v1/decision/recommend
        │
        ▼
DecisionService.recommend()
        │
        ├─► PredictionService.infer()      (Phase 6: RUL, P(failure), anomaly flags)
        ├─► XaiService.explain()           (Phase 7: top root-cause sensors, narrative)
        ├─► Neo4j Asset.criticality        (Phase 2: A/B/C weight lookup)
        ├─► Neo4j FailureMode.severity_tier(Phase 2: CRITICAL/DEGRADED/INCIPIENT)
        │
        ▼
RuleEngine.classify()                       → IMMINENT / SCHEDULED / MONITOR + 8 audited rules
        │
        ▼
RiskScorer.score() + estimate_cost()        → RPN = P × S × D, cost-of-inaction USD
        │
        ▼
SopMatcher.find_sops_for_failure_mode()     → SOP steps, tools, hazards, PPE (graph or fallback)
        │
        ▼
RecommendationResponse                      → recommendations[] + sop_steps[] + decision_log[]
```

## How to run

```bash
# 1. Ensure Phase 6 model artifacts exist (Decision Engine calls the live predictor)
python -m app.predictive.train_predictive_models --episodes 6 --seed 42

# 2. Run the Phase 8 test suite
pytest tests/test_phase8_decision.py -q      # 54 passed

# 3. Run the full backend regression suite (Neo4j-dependent tests skip cleanly offline)
pytest tests/ -q --ignore=tests/test_phase1_ontology.py   # pre-existing broken import, unrelated to Phase 8

# 4. Serve
uvicorn app.main:app --reload --port 8000
#   POST /api/v1/decision/recommend
#   GET  /api/v1/decision/health
```

## Sample payload (live run against `asset-101`)

```json
{
  "success": true,
  "data": {
    "asset_id": "asset-101",
    "component_id": "asset-101-bearing-de",
    "recommendations": [
      {
        "action_id": "a93c8208-...",
        "action_type": "ISOLATE",
        "description": "Immediate action required on asset 'asset-101' — root cause implicates bearing_temp, vibration_rms (RUL 7.3d, P(failure)=0.90) per SOP-114: Bearing Lubrication & Thermal Overload Response.",
        "priority": "CRITICAL",
        "risk_score_if_ignored": 0.4522,
        "estimated_cost_avoidance_usd": 18816.0,
        "recommended_completion_by": "2026-07-05T08:50:23.566337Z",
        "sop_linkage": { "sop_id": "sop:SOP-114:REV-C", "title": "SOP-114: Bearing Lubrication & Thermal Overload Response", "revision": "Rev. C", "effectiveness": 0.82 },
        "severity_tier": "IMMINENT",
        "rank": 1
      }
    ],
    "sop_steps": [ /* 4 structured steps: LOTO isolation, inspection, re-lubrication, verification — with hazards/PPE/hold-points */ ],
    "decision_log": [ { "decision_id": "...", "triggered_rules": [ /* 8 audited rules */ ], "risk_breakdown": { "risk_priority_number": 452.2, "..." : "..." }, "cost_estimate": { "..." : "..." }, "rationale": "Classified as IMMINENT ..." } ],
    "overall_risk_score": 0.4522
  }
}
```

## Verified results (this run)

* `pytest tests/test_phase8_decision.py -q` → **54 passed**
* `pytest tests/ -q` (excluding the pre-existing broken `test_phase1_ontology.py` import and the heavy-dependency Phase 4 embedding/benchmark suites) → **147 passed, 7 skipped** (skips are Neo4j-integration tests that cleanly skip without a live database, unchanged from before this phase).
* Live end-to-end smoke test via `TestClient` against `/api/v1/decision/recommend` confirmed the full pipeline (real XGBoost RUL + Isolation Forest inference → SHAP/LIME root-cause → rule classification → RPN scoring → offline SOP fallback) produces a fully-formed, contract-compliant JSON payload.
