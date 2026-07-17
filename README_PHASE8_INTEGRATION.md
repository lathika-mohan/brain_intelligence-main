# Phase 8 — AI Decision Engine — Integration Package

This archive contains **only the new and modified files** for Phase 8,
laid out with the exact same relative paths as your `brain_intelligence-main`
repository. Drop the contents straight into your project root (merging
folders) and the Decision Engine wires itself into the existing app
automatically — no other files need to change.

```
brain_intelligence-main/
├── app/
│   ├── api/v1/
│   │   ├── decision.py        ← NEW  (POST /api/v1/decision/recommend, GET /decision/health)
│   │   ├── router.py          ← MODIFIED (mounts the new decision router)
│   │   └── xai.py             ← MODIFIED (bug fix: broken TelemetrySimulator import
│   │                              that was silently disabling /api/v1/xai/explain)
│   ├── core/
│   │   └── config.py          ← MODIFIED (adds Decision Engine tunables)
│   ├── decision/               ← NEW PACKAGE
│   │   ├── __init__.py
│   │   ├── rule_engine.py      (severity classification + asset criticality)
│   │   ├── risk_scorer.py      (RPN = P x S x D + cost-of-inaction)
│   │   ├── sop_matcher.py      (graph-driven SOP retrieval + offline fallback)
│   │   └── decision_service.py (end-to-end orchestrator)
│   └── models/
│       └── decision.py        ← MODIFIED (frozen §4 contract + Phase 8 audit models)
├── tests/
│   └── test_phase8_decision.py ← NEW (54 pytest cases)
└── PHASE8_WORKED_FILES_MANIFEST.md ← NEW (full change log / design notes)
```

## Install & run

```bash
# From your repo root, after copying these files in:
cd brain_intelligence-main

# 1. Make sure the Phase 6 predictive models exist (the Decision Engine
#    calls the real XGBoost/Isolation Forest predictor under the hood):
python -m app.predictive.train_predictive_models --episodes 6 --seed 42

# 2. Run the new Phase 8 test suite
pytest tests/test_phase8_decision.py -q
#   -> 54 passed

# 3. (Optional) Run the full regression suite
pytest tests/ -q

# 4. Serve
uvicorn app.main:app --reload --port 8000
```

Then call:

```bash
curl -X POST http://localhost:8000/api/v1/decision/recommend \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "asset-101", "risk_horizon_days": 14, "max_recommendations": 3}'

curl http://localhost:8000/api/v1/decision/health
```

## Why the `app/api/v1/xai.py` fix is included

While wiring Phase 8 into the existing Phase 7 XAI service
(`DecisionService` calls `XaiService.explain()` for root-cause sensors), we
found `app/api/v1/xai.py` imported a class, `TelemetrySimulator`, that does
not exist in `app/predictive/telemetry_simulator.py` (only the functions
`generate_episode` / `load_run_to_failure_episodes` are exported there —
the same functions your own `tests/test_phase7_xai.py` already uses). This
silently broke the `/api/v1/xai/explain` router mount at startup (caught
and logged as a warning by the router aggregator's try/except, so it never
surfaced as a hard error). It's a one-line fix and is included here so the
Decision Engine's dependency on the XAI endpoint is fully functional, not
just internally correct.

## No frontend / UI changes

Nothing under `src/` is touched. This is a pure backend service-layer
delivery per the Phase 8 brief.
