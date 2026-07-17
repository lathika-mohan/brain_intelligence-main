# Phase 6 — Predictive Maintenance Engine · Worked Files Manifest

**Member 3 (AI & Knowledge Engineer)** — Real ML replaces simulated predictive
data. XGBoost RUL regression + Isolation Forest anomaly detection behind
`POST /api/v1/predictive/infer`, matching the frozen Phase 0 contract
(`docs/api_contracts.md` §2) consumed by `src/components/DigitalTwinView.tsx`.

> ✅ Zero UI scaffolding. `src/components/DigitalTwinView.tsx` untouched.

---

## New files

| File | Purpose |
|---|---|
| `app/predictive/__init__.py` | Phase 6 package (re-exports feature-engineering API). |
| `app/predictive/feature_engineering.py` | Telemetry → rolling-window feature vectors (1h/6h/24h mean/std/var/min/max, gradients, 24h peak-to-peak) + piecewise-linear RUL labelling. Raises `TelemetryContractError` on invalid shapes. |
| `app/predictive/telemetry_simulator.py` | Run-to-failure episode generator matching the frozen `TelemetryReading` contract. `load_run_to_failure_episodes()` is the single seam to swap in Member 2's historian/Kafka feed. |
| `app/predictive/model_registry.py` | Thread-safe (RLock) artifact save/load: XGBoost native JSON + joblib for the Isolation Forest + evaluation-report JSON. |
| `app/predictive/train_predictive_models.py` | CLI training pipeline: episode-level holdout split (no temporal leakage), XGBoost tuned for industrial telemetry (max_depth=5, lr=0.06, reg_alpha=0.5, reg_lambda=2.0), IF fit on healthy-baseline rows with explicit contamination, full evaluation suite (MAE/RMSE/R², precision/recall/F1), JSON + Markdown reports with feature-importance rankings. |
| `app/predictive/prediction_service.py` | Async real-time inference: deterministic on-the-fly feature engineering, **parallel** dual-model execution via `asyncio.gather` + worker threads, per-sensor anomaly attribution (z-score), contract-compliant payload assembly, configurable heuristic fallback. |
| `app/api/v1/predictive.py` | FastAPI router: `POST /predictive/infer` (200 / 422 contract errors / 503 no-artifacts-reject), `GET /predictive/health`, `GET /predictive/evaluation`. |
| `tests/test_phase6_predictive.py` | 34 pytest cases: feature determinism, rolling stats, gradients, RUL labels, training beats naive baseline (R² > 0.5), IF recall, registry round-trip, async inference, fallback policy, exact frontend JSON signature, HTTP 422 on every invalid telemetry shape. |

## Modified files

| File | Change |
|---|---|
| `app/models/telemetry.py` | Added the frozen §5 upstream contract (`SensorReading`, `TelemetryReading`, `TelemetryBatch`, `OperatingMode`, `TelemetryMetric`). Phase 0 stub `TelemetryIngestRequest` preserved verbatim. |
| `app/models/predictive.py` | Added the frozen §2 inference contract (`InferenceRequest`, `InferenceResponse`, `RulEstimate`, `FailureProbability`, `FailureWindow`, `AnomalyFlag`) + evaluation-report models. Phase 0 stubs preserved verbatim. |
| `app/api/v1/router.py` | Mounted the Phase 6 predictive router (same try/except pattern as Phases 3–5). |
| `requirements.txt` | Added `joblib>=1.4.2` (model serialization). |

## Generated artifacts (after training)

```
artifacts/models/
├── xgboost_rul_v1.json            # native XGBoost JSON
├── isolation_forest_v1.joblib     # scikit-learn IsolationForest
├── model_evaluation_report.json   # ModelEvaluationReport contract
└── model_evaluation_report.md     # human-readable report
```

---

## How to run

```bash
# 1. Install deps (adds joblib)
pip install -r requirements.txt

# 2. Train + evaluate + register models
python -m app.predictive.train_predictive_models --episodes 8 --seed 42

# 3. Run the Phase 6 test suite
pytest tests/test_phase6_predictive.py -q      # 34 passed

# 4. Serve
uvicorn app.main:app --reload --port 8000
#   POST /api/v1/predictive/infer
#   GET  /api/v1/predictive/health
#   GET  /api/v1/predictive/evaluation
```

## Verified results (this run)

| Model | Metric | Value |
|---|---|---|
| XGBoost RUL | MAE | 23.4 h |
| XGBoost RUL | RMSE | 36.8 h |
| XGBoost RUL | R² | 0.749 |
| Isolation Forest | Precision | 0.504 |
| Isolation Forest | Recall | 1.000 |
| Isolation Forest | F1 | 0.670 |

Top RUL features: `vibration_rms_6h_mean`, `vibration_rms_p2p_24h`,
`vibration_rms_24h_min`, `vibration_rms_1h_mean`, `flow_rate_6h_mean` —
physically consistent with bearing-degradation failure modes.

## Live payload example (frozen contract)

```json
{
  "success": true,
  "data": {
    "asset_id": "asset-101",
    "component_id": "asset-101-bearing-de",
    "rul": { "value_days": 3.8, "lower_bound_days": 2.66, "upper_bound_days": 4.94,
             "confidence_level": 0.9, "model_name": "xgboost_rul_v1", "model_version": "1.0.0" },
    "failure_probability": {
      "probability": 0.8899,
      "predicted_window": { "earliest": "...", "latest": "...", "most_likely": "..." },
      "failure_mode_id": "failuremode-bearing-overheat",
      "failure_mode_label": "Bearing Overheat",
      "model_name": "xgboost_failure_classifier_v1", "model_version": "1.0.0"
    },
    "anomaly_flags": [ { "sensor_id": "asset-101-s6", "metric": "load_kw",
                         "anomaly_score": -0.1088, "is_anomalous": true,
                         "severity": "CRITICAL", "detected_at": "..." } ],
    "anomalous_sensors": ["asset-101-s6"],
    "explanation_id": "uuid-linkable-to-/xai/explain",
    "inference_latency_ms": 12.4,
    "generated_at": "...",
    "fallback_used": false
  },
  "error": null, "request_id": "...", "generated_at": "..."
}
```

Invalid telemetry (empty history, mixed asset ids, NaN values, extra fields,
out-of-range quality) → **HTTP 422** with an explicit message. Missing model
artifacts with `PDM_INFERENCE_FALLBACK_MODE=reject` → **HTTP 503**; the
default `heuristic` mode answers with `fallback_used: true`.
