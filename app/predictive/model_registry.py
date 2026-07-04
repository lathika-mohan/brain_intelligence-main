"""
Phase 6 — Model Serialization Lifecycle.

Thread-safe registration, storage and low-overhead deserialization of the
predictive-maintenance model artifacts:

    artifacts/models/
      ├── xgboost_rul_v1.json           (native XGBoost JSON — portable, fast)
      ├── isolation_forest_v1.joblib    (scikit-learn IsolationForest)
      └── model_evaluation_report.json  (ModelEvaluationReport contract)

The registry is a process-wide singleton guarded by an ``RLock`` so the
FastAPI worker threads can hot-load / swap artifacts without races. Loaded
models are cached; ``reload()`` invalidates the cache after retraining.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

import joblib
import xgboost as xgb
from sklearn.ensemble import IsolationForest

from app.core.config import get_settings
from app.models.predictive import ModelEvaluationReport

logger = logging.getLogger(__name__)

RUL_MODEL_FILE = "xgboost_rul_v1.json"
ANOMALY_MODEL_FILE = "isolation_forest_v1.joblib"
EVAL_REPORT_FILE = "model_evaluation_report.json"


class ModelRegistry:
    """Thread-safe artifact store for the Phase 6 model lifecycle."""

    def __init__(self, registry_path: str | Path | None = None) -> None:
        settings = get_settings()
        self._path = Path(registry_path or settings.pdm_model_registry_path)
        self._lock = threading.RLock()
        self._rul_model: Optional[xgb.XGBRegressor] = None
        self._anomaly_model: Optional[IsolationForest] = None
        self._report: Optional[ModelEvaluationReport] = None

    # -- paths -------------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path

    @property
    def rul_model_path(self) -> Path:
        return self._path / RUL_MODEL_FILE

    @property
    def anomaly_model_path(self) -> Path:
        return self._path / ANOMALY_MODEL_FILE

    @property
    def report_path(self) -> Path:
        return self._path / EVAL_REPORT_FILE

    # -- save --------------------------------------------------------------
    def save(
        self,
        rul_model: xgb.XGBRegressor,
        anomaly_model: IsolationForest,
        report: ModelEvaluationReport,
    ) -> None:
        """Atomically persist all three artifacts and refresh the cache."""
        with self._lock:
            self._path.mkdir(parents=True, exist_ok=True)
            rul_model.save_model(self.rul_model_path)  # native XGBoost JSON
            joblib.dump(anomaly_model, self.anomaly_model_path)
            self.report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            self._rul_model = rul_model
            self._anomaly_model = anomaly_model
            self._report = report
            logger.info("Model artifacts registered at %s", self._path.resolve())

    # -- load --------------------------------------------------------------
    def artifacts_available(self) -> bool:
        return self.rul_model_path.exists() and self.anomaly_model_path.exists()

    def load_rul_model(self) -> xgb.XGBRegressor:
        with self._lock:
            if self._rul_model is None:
                if not self.rul_model_path.exists():
                    raise FileNotFoundError(
                        f"RUL model artifact missing: {self.rul_model_path}. "
                        "Run `python -m app.predictive.train_predictive_models` first."
                    )
                model = xgb.XGBRegressor()
                model.load_model(self.rul_model_path)
                self._rul_model = model
                logger.info("Loaded RUL model from %s", self.rul_model_path)
            return self._rul_model

    def load_anomaly_model(self) -> IsolationForest:
        with self._lock:
            if self._anomaly_model is None:
                if not self.anomaly_model_path.exists():
                    raise FileNotFoundError(
                        f"Anomaly model artifact missing: {self.anomaly_model_path}. "
                        "Run `python -m app.predictive.train_predictive_models` first."
                    )
                self._anomaly_model = joblib.load(self.anomaly_model_path)
                logger.info("Loaded Isolation Forest from %s", self.anomaly_model_path)
            return self._anomaly_model

    def load_report(self) -> Optional[ModelEvaluationReport]:
        with self._lock:
            if self._report is None and self.report_path.exists():
                payload = json.loads(self.report_path.read_text(encoding="utf-8"))
                self._report = ModelEvaluationReport.model_validate(payload)
            return self._report

    def reload(self) -> None:
        """Drop the in-memory cache (call after retraining)."""
        with self._lock:
            self._rul_model = None
            self._anomaly_model = None
            self._report = None


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------

_registry_lock = threading.Lock()
_registry: Optional[ModelRegistry] = None


def get_model_registry(registry_path: str | Path | None = None) -> ModelRegistry:
    """Return the shared registry (or a bespoke one when a path is given)."""
    global _registry
    if registry_path is not None:
        return ModelRegistry(registry_path)
    with _registry_lock:
        if _registry is None:
            _registry = ModelRegistry()
        return _registry
