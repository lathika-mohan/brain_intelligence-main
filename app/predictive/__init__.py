"""
Phase 6 — Predictive Maintenance Engine.

Modules
-------
feature_engineering   Telemetry → rolling-window ML feature vectors (deterministic).
telemetry_simulator   Run-to-failure telemetry generator for training/validation.
model_registry        Thread-safe artifact save/load (XGBoost JSON + joblib).
train_predictive_models  Training + evaluation pipeline (CLI entry point).
prediction_service    Async real-time inference service powering
                      POST /api/v1/predictive/infer → DigitalTwinView.tsx.
"""
from app.predictive.feature_engineering import (  # noqa: F401
    TelemetryContractError,
    feature_columns,
    frames_to_dataframe,
    compute_rolling_features,
    build_feature_matrix,
    latest_feature_vector,
    build_rul_labels,
)
