# Phase 7 — Explainable AI (XAI) Engine · Worked Files Manifest

**Member 3 (AI & Knowledge Engineer)** — Real SHAP + LIME feature attribution
and root-cause synthesis replace the Phase 0 XAI stub, behind the frozen
`POST /api/v1/xai/explain` contract (`docs/api_contracts.md` §3) consumed by
`src/components/ShapExplainability.tsx`.

> ✅ Zero UI scaffolding. `src/components/ShapExplainability.tsx` untouched.
> ✅ Frozen §3 `ExplanationResponse` wire shape satisfied verbatim.
> ✅ Feeds Phase 8 Decision Engine (root-cause sensors) — see
> `app/decision/decision_service.py`.

> **Backfill note:** This manifest was reconstructed during the Phase 3
> Solo-Safe consistency pass — it was flagged absent in the repo gap list even
> though the Phase 7 XAI code, tests, and downstream Phase 8 wiring were all
> already present and shipping. No source files were changed to produce this
> document; it records the XAI files exactly as they exist in the repo.

---

## New files

| File | Purpose |
|---|---|
| `app/predictive/shap_engine.py` | `ShapExplanationEngine` — SHAP TreeExplainer wrapper for the XGBoost RUL/failure models. Produces signed local feature attributions (`base_value`, `predicted_value`, per-feature `impact_weight`) ranked by absolute impact, aligned to `feature_columns()` from the Phase 6 feature pipeline. Fast-path guard on explainer initialization to keep the endpoint under the latency budget. |
| `app/predictive/lime_engine.py` | `LimeExplanationEngine` — LIME `LimeTabularExplainer` wrapper that builds a localized surrogate around the instance and emits human-readable `generate_logical_rules()` used in the root-cause narrative. |
| `app/predictive/xai_service.py` | `XaiService` unified orchestrator (`explain()`), coordinating SHAP + LIME + knowledge-graph enrichment into a single contract-compliant `ExplanationResponse`. Assembles `local_feature_importance`, `root_cause` (`RootCauseSummary`), and `confidence_matrix`. Exposes `get_xai_service()` for FastAPI dependency injection. Raises `ValueError` on empty telemetry history. |
| `app/api/v1/xai.py` | FastAPI router: `POST /xai/explain` (200 / 400 on invalid params / 500 on compute failure). Pulls the required 24-frame telemetry window via `generate_episode(asset_id=...)` for feature engineering. |
| `tests/test_phase7_xai.py` | Contract-conformance + latency boundary suite: verifies local explanation shape matches the frozen §3 schema and computes within the < 200 ms warm-path budget. |

## Modified / depended-on files (not owned by Phase 7, listed for traceability)

| File | Relationship |
|---|---|
| `app/models/xai.py` | Frozen §3 contract vocabulary (`ExplanationRequest`, `ExplanationResponse`, `FeatureImpact`, `ConfidenceMatrixEntry`, `RootCauseSummary`, `ExplanationMethod`, `ExplanationScope`). Reconstructed in Phase 2; **not modified** in Phase 7. |
| `app/predictive/feature_engineering.py` | Reused for `latest_feature_vector()`, `build_feature_matrix()`, `feature_columns()`, `CANONICAL_METRICS` — SHAP/LIME operate on the exact same Phase 6 feature space (no drift between prediction and explanation). |
| `app/predictive/model_registry.py` | `get_model_registry()` supplies the trained XGBoost artifact the explainers attribute over. |
| `app/predictive/telemetry_simulator.py` | `generate_episode()` supplies the 24-frame history seam (swap-in point for Member 2's live historian). |
| `app/api/v1/router.py` | Mounts `xai_router` under `/api/v1/xai` via the shared try/except aggregator pattern. |

---

## Contract surface (frozen — `docs/api_contracts.md` §3)

`POST /api/v1/xai/explain` → `data: ExplanationResponse`

```json
{
  "explanation_id": "...",
  "asset_id": "asset-101",
  "method": "SHAP",
  "scope": "LOCAL",
  "base_value": 0.15,
  "predicted_value": 0.23,
  "global_feature_importance": null,
  "local_feature_importance": [
    { "feature_name": "bearing_temp_c", "impact_weight": 0.34, "feature_value": 78.2, "rank": 1 }
  ],
  "root_cause": { "headline": "...", "narrative": "...", "contributing_failure_modes": ["failuremode-stub-1"] },
  "confidence_matrix": [ { "label": "Bearing Overheat", "confidence": 0.82 } ],
  "model_name": "xgboost_failure_classifier_v1",
  "model_version": "1.0.0",
  "generated_at": "..."
}
```

The `ExplanationResponse` model uses `extra="forbid"` — no undeclared fields
can leak onto the frozen wire shape.

---

## How to run

```bash
# 1. Install deps (SHAP + LIME pinned in requirements.txt)
pip install -r requirements.txt

# 2. Ensure Phase 6 models are trained (XAI attributes over them)
python -m app.predictive.train_predictive_models --episodes 8 --seed 42

# 3. Run the Phase 7 test suite
pytest tests/test_phase7_xai.py -q

# 4. Serve
uvicorn app.main:app --reload --port 8000
#   POST /api/v1/xai/explain
```

## Integration note (downstream)

Phase 8's `DecisionService.recommend()` calls `XaiService.explain()` to pull
top root-cause sensors into the prescriptive recommendation. The `xai.py`
router import bug that previously left `/xai/explain` unmounted was fixed in
Phase 8 — see `PHASE8_WORKED_FILES_MANIFEST.md` (the `app/api/v1/xai.py` entry)
and `README_PHASE8_INTEGRATION.md`.
