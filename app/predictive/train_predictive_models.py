"""
Phase 6 — Training & Evaluation Pipeline (CLI entry point).

Trains the dual-model predictive-maintenance framework:

  • **XGBoost RUL regressor** (``xgboost_rul_v1``) — supervised
    time-to-failure forecasting on rolling-window telemetry features with
    piecewise-linear RUL labels. Hyperparameters tuned for industrial
    telemetry: shallow-ish trees, conservative learning rate, and L1/L2
    regularisation (alpha/lambda) to avoid overfitting to individual
    sensor nodes.

  • **Isolation Forest** (``isolation_forest_v1``) — unsupervised anomaly
    detection fit on *healthy-baseline* operation only, with an explicit
    contamination factor from ``Settings.pdm_anomaly_contamination``.

Evaluation (Section 3 deliverables):
  • RUL:   MAE, RMSE, R² on a held-out episode split (never random rows —
           whole episodes are held out to avoid temporal leakage).
  • IF:    precision / recall / F1 against verified degradation labels.
  • Report: ``ModelEvaluationReport`` JSON + Markdown summary + feature
           importance rankings, persisted next to the artifacts.

Usage:
    python -m app.predictive.train_predictive_models \
        [--episodes 8] [--registry-path ./artifacts/models] [--seed 42]
"""
from __future__ import annotations

import argparse
import logging
import uuid
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)

from app.core.config import get_settings
from app.models.predictive import (
    AnomalyMetrics,
    FeatureImportanceEntry,
    ModelEvaluationReport,
    RegressionMetrics,
)
from app.predictive.feature_engineering import (
    build_feature_matrix,
    build_rul_labels,
    feature_columns,
)
from app.predictive.model_registry import ModelRegistry, get_model_registry
from app.predictive.telemetry_simulator import Episode, load_run_to_failure_episodes

logger = logging.getLogger(__name__)

RUL_CAP_HOURS = 24.0 * 60.0  # 60-day healthy plateau

#: XGBoost hyperparameters tuned for noisy industrial telemetry.
XGB_PARAMS: dict = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.06,
    "subsample": 0.85,
    "colsample_bytree": 0.8,
    "min_child_weight": 4,
    "reg_alpha": 0.5,   # L1 — sparse feature selection across sensor nodes
    "reg_lambda": 2.0,  # L2 — smooth weights, guards single-sensor overfit
    "objective": "reg:squarederror",
    "random_state": 42,
    "n_jobs": -1,
}


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------

def episodes_to_dataset(episodes: Sequence[Episode]) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Episodes → (X features, y RUL hours, episode ids) with aligned indices."""
    X_parts: List[pd.DataFrame] = []
    y_parts: List[pd.Series] = []
    grp_parts: List[pd.Series] = []
    for ep in episodes:
        feats = build_feature_matrix(ep.frames)
        labels = build_rul_labels(feats.index, pd.Timestamp(ep.failure_time), RUL_CAP_HOURS)
        X_parts.append(feats.reset_index(drop=True))
        y_parts.append(labels.reset_index(drop=True))
        grp_parts.append(pd.Series([ep.asset_id] * len(feats)))
    X = pd.concat(X_parts, ignore_index=True)
    y = pd.concat(y_parts, ignore_index=True)
    groups = pd.concat(grp_parts, ignore_index=True)
    return X, y, groups


def split_episodes(episodes: Sequence[Episode], holdout_fraction: float = 0.25) -> Tuple[List[Episode], List[Episode]]:
    """Hold out whole episodes for validation (prevents temporal leakage)."""
    n_holdout = max(1, int(round(len(episodes) * holdout_fraction)))
    return list(episodes[:-n_holdout]), list(episodes[-n_holdout:])


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_rul_model(X_train: pd.DataFrame, y_train: pd.Series) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X_train, y_train)
    return model


def train_anomaly_model(
    healthy_features: pd.DataFrame,
    contamination: float,
    seed: int = 42,
) -> IsolationForest:
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        max_samples="auto",
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(healthy_features.values)
    return model


# ---------------------------------------------------------------------------
# Evaluation suite
# ---------------------------------------------------------------------------

def evaluate_rul(model: xgb.XGBRegressor, X_val: pd.DataFrame, y_val: pd.Series) -> RegressionMetrics:
    preds = model.predict(X_val)
    return RegressionMetrics(
        mae=float(mean_absolute_error(y_val, preds)),
        rmse=float(np.sqrt(mean_squared_error(y_val, preds))),
        r2=float(r2_score(y_val, preds)),
        n_samples=int(len(y_val)),
    )


def evaluate_anomaly(
    model: IsolationForest,
    X_val: pd.DataFrame,
    y_true_anomalous: np.ndarray,
    contamination: float,
) -> AnomalyMetrics:
    """Precision/recall/F1 against verified degradation labels.

    ``y_true_anomalous`` is 1 where the frame lies inside the verified
    degradation window (RUL < 48 h before failure), 0 for healthy frames.
    """
    raw = model.predict(X_val.values)  # +1 normal, -1 anomalous
    y_pred = (raw == -1).astype(int)
    return AnomalyMetrics(
        precision=float(precision_score(y_true_anomalous, y_pred, zero_division=0)),
        recall=float(recall_score(y_true_anomalous, y_pred, zero_division=0)),
        f1=float(f1_score(y_true_anomalous, y_pred, zero_division=0)),
        n_samples=int(len(y_pred)),
        contamination=float(contamination),
    )


def rank_feature_importance(model: xgb.XGBRegressor, top_k: int = 20) -> List[FeatureImportanceEntry]:
    importances = model.feature_importances_
    order = np.argsort(importances)[::-1][:top_k]
    cols = feature_columns()
    return [
        FeatureImportanceEntry(feature_name=cols[i], importance=float(importances[i]), rank=r + 1)
        for r, i in enumerate(order)
    ]


def write_markdown_report(report: ModelEvaluationReport, path: Path) -> None:
    lines = [
        "# Phase 6 — Predictive Maintenance Model Evaluation Report",
        "",
        f"- **Report ID:** `{report.report_id}`",
        f"- **Trained at:** {report.trained_at.isoformat()}",
        "",
        "## XGBoost RUL Regressor (`" + report.rul_model_name + "`)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| MAE (hours) | {report.rul_metrics.mae:.2f} |",
        f"| RMSE (hours) | {report.rul_metrics.rmse:.2f} |",
        f"| R² | {report.rul_metrics.r2:.4f} |",
        f"| Validation samples | {report.rul_metrics.n_samples} |",
        "",
        "## Isolation Forest (`" + report.anomaly_model_name + "`)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Precision | {report.anomaly_metrics.precision:.4f} |",
        f"| Recall | {report.anomaly_metrics.recall:.4f} |",
        f"| F1 | {report.anomaly_metrics.f1:.4f} |",
        f"| Contamination | {report.anomaly_metrics.contamination} |",
        f"| Validation samples | {report.anomaly_metrics.n_samples} |",
        "",
        "## Top Feature Importances (XGBoost gain)",
        "",
        "| Rank | Feature | Importance |",
        "|---|---|---|",
    ]
    for fi in report.feature_importance:
        lines.append(f"| {fi.rank} | `{fi.feature_name}` | {fi.importance:.5f} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_training(
    n_episodes: int = 8,
    registry_path: str | Path | None = None,
    seed: int = 42,
) -> ModelEvaluationReport:
    """Full train → evaluate → register pipeline. Returns the eval report."""
    settings = get_settings()
    contamination = settings.pdm_anomaly_contamination

    logger.info("Loading %d run-to-failure episodes ...", n_episodes)
    episodes = load_run_to_failure_episodes(n_episodes=n_episodes, seed=seed)
    train_eps, val_eps = split_episodes(episodes)

    X_train, y_train, _ = episodes_to_dataset(train_eps)
    X_val, y_val, _ = episodes_to_dataset(val_eps)

    logger.info("Training XGBoost RUL regressor on %d rows ...", len(X_train))
    rul_model = train_rul_model(X_train, y_train)
    rul_metrics = evaluate_rul(rul_model, X_val, y_val)
    logger.info("RUL — MAE %.2fh RMSE %.2fh R² %.4f", rul_metrics.mae, rul_metrics.rmse, rul_metrics.r2)

    # Healthy baseline = frames with plenty of remaining life (> 7 days).
    healthy_mask = y_train > 24.0 * 7.0
    logger.info("Training Isolation Forest on %d healthy-baseline rows ...", int(healthy_mask.sum()))
    anomaly_model = train_anomaly_model(X_train[healthy_mask], contamination, seed)

    # Verified failure log labels: last 48 h before failure = anomalous.
    y_true_anom = (y_val < 48.0).astype(int).values
    anomaly_metrics = evaluate_anomaly(anomaly_model, X_val, y_true_anom, contamination)
    logger.info(
        "Anomaly — P %.3f R %.3f F1 %.3f",
        anomaly_metrics.precision, anomaly_metrics.recall, anomaly_metrics.f1,
    )

    report = ModelEvaluationReport(
        report_id=str(uuid.uuid4()),
        rul_metrics=rul_metrics,
        anomaly_metrics=anomaly_metrics,
        feature_importance=rank_feature_importance(rul_model),
        feature_columns=feature_columns(),
        training_config={
            "xgb_params": XGB_PARAMS,
            "n_episodes": n_episodes,
            "rul_cap_hours": RUL_CAP_HOURS,
            "contamination": contamination,
            "seed": seed,
            "holdout_episodes": [ep.asset_id for ep in val_eps],
        },
    )

    registry: ModelRegistry = get_model_registry(registry_path)
    # Save dataset hash placeholder for metadata
    import hashlib
    dataset_hash = hashlib.sha256(X_train.to_csv(index=False).encode()).hexdigest()
    registry.save(rul_model, anomaly_model, report, dataset_hash=dataset_hash)
    
    # Phase 12 - Generate baseline stats for Data Drift Check
    try:
        from app.predictive.data_drift_checker import DataDriftChecker
        drift_checker = DataDriftChecker(registry_path=str(registry.path))
        drift_checker.compute_and_save_baseline(X_train, feature_columns())
    except ImportError:
        logger.warning("DataDriftChecker not found, skipping baseline generation.")

    write_markdown_report(report, registry.path / "model_evaluation_report.md")
    logger.info("Artifacts + evaluation report written to %s", registry.path.resolve())
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 6 — train predictive-maintenance models")
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--registry-path", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = run_training(n_episodes=args.episodes, registry_path=args.registry_path, seed=args.seed)
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
