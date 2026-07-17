"""
Phase 6 — Real-Time Prediction Service.

Async inference pipeline behind ``POST /api/v1/predictive/infer``:

  1. Validate + align incoming ``TelemetryReading`` frames (frozen contract).
  2. Apply the *exact same* deterministic feature-engineering rules used at
     training time (``app.predictive.feature_engineering``).
  3. Execute both engines in parallel worker threads (XGBoost RUL +
     Isolation Forest anomaly) via ``asyncio.gather`` — the event loop is
     never blocked by model math.
  4. Assemble the frozen ``InferenceResponse`` consumed by
     ``DigitalTwinView.tsx`` (RUL + bounds, failure probability + window,
     per-sensor anomaly flags).

Fallback policy follows ``Settings.pdm_inference_fallback_mode``:
  * ``heuristic``      → physics-based rough estimate, ``fallback_used=True``
  * ``reject``         → raise (router maps to HTTP 503)
  * ``last_known_good``→ heuristic (until a prediction cache lands in Phase 7)
"""
from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
import uuid
from datetime import timedelta
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.models.predictive import (
    AnomalyFlag,
    AnomalySeverity,
    FailureProbability,
    FailureWindow,
    InferenceRequest,
    InferenceResponse,
    RulEstimate,
)
from app.models.telemetry import TelemetryReading
from app.predictive.feature_engineering import (
    CANONICAL_METRICS,
    TelemetryContractError,
    latest_feature_vector,
)
from app.predictive.model_registry import ModelRegistry, get_model_registry

logger = logging.getLogger(__name__)

#: Sigmoid steepness for RUL → failure-probability mapping.
_PROB_SCALE_HOURS = 72.0

#: Uncertainty band applied to the point RUL (until quantile heads land).
_RUL_BOUND_FRACTION = 0.30


class PredictionServiceUnavailable(RuntimeError):
    """Raised when models are missing and fallback mode is 'reject'."""


class BatchPredictionResult(NamedTuple):
    rul_days: float
    anomaly_score: float


class PredictionService:
    """Thread-safe, async-friendly dual-model inference engine."""

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self._settings = get_settings()
        self._registry = registry or get_model_registry()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        """Run the full async inference pipeline for one asset."""
        started = time.perf_counter()

        # 1) Contract validation & feature engineering (deterministic).
        self._validate_request(request)
        features = latest_feature_vector(request.history)

        # 2) Parallel dual-model inference in worker threads.
        if self._registry.artifacts_available():
            rul_hours, anomaly_result = await asyncio.gather(
                asyncio.to_thread(self._predict_rul, features),
                asyncio.to_thread(self._score_anomaly, features, request.history[-1]),
            )
            fallback_used = False
        else:
            mode = self._settings.pdm_inference_fallback_mode
            if mode == "reject":
                raise PredictionServiceUnavailable(
                    "Predictive model artifacts are not available and fallback mode is 'reject'. "
                    "Train models via `python -m app.predictive.train_predictive_models`."
                )
            logger.warning("Model artifacts missing — using heuristic fallback (%s).", mode)
            rul_hours = self._heuristic_rul(features)
            anomaly_result = self._heuristic_anomaly(features, request.history[-1])
            fallback_used = True

        # 3) Assemble the frozen contract payload.
        response = self._build_response(
            request=request,
            rul_hours=rul_hours,
            anomaly_result=anomaly_result,
            fallback_used=fallback_used,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
        return response

    def predict_batch(self, features: pd.DataFrame) -> List[BatchPredictionResult]:
        """Run batch inference across rows of a DataFrame."""
        if not self._registry.artifacts_available():
            raise FileNotFoundError("Models not trained yet in this environment.")
        results = []
        for idx in range(len(features)):
            row_df = features.iloc[[idx]]
            rul_hours = self._predict_rul(row_df)
            try:
                model = self._registry.load_anomaly_model()
                score = float(model.decision_function(row_df)[0]) if hasattr(model, "decision_function") else float(model.predict(row_df)[0])
            except Exception:
                score = 0.0
            if math.isnan(rul_hours) or math.isinf(rul_hours):
                rul_hours = 500.0
            if math.isnan(score) or math.isinf(score):
                score = 0.0
            results.append(BatchPredictionResult(rul_days=max(0.0, float(rul_hours) / 24.0), anomaly_score=float(score)))
        return results

    # ------------------------------------------------------------------ #
    # Validation                                                          #
    # ------------------------------------------------------------------ #

    def _validate_request(self, request: InferenceRequest) -> None:
        if not request.history:
            raise TelemetryContractError("InferenceRequest.history must contain at least one frame.")
        for frame in request.history:
            if frame.asset_id != request.asset_id:
                raise TelemetryContractError(
                    f"Frame asset_id '{frame.asset_id}' does not match request asset_id "
                    f"'{request.asset_id}'."
                )

    # ------------------------------------------------------------------ #
    # Model execution (runs inside worker threads)                        #
    # ------------------------------------------------------------------ #

    def _predict_rul(self, features: pd.DataFrame) -> float:
        model = self._registry.load_rul_model()
        pred = float(model.predict(features)[0])
        return max(pred, 0.0)

    def _score_anomaly(
        self, features: pd.DataFrame, latest_frame: TelemetryReading
    ) -> Tuple[float, bool, List[AnomalyFlag]]:
        """Global IF score + per-sensor attribution flags."""
        model = self._registry.load_anomaly_model()
        score = float(model.decision_function(features.values)[0])
        is_anomalous = bool(model.predict(features.values)[0] == -1)
        flags = self._per_sensor_flags(features, latest_frame, score, is_anomalous)
        return score, is_anomalous, flags

    def _per_sensor_flags(
        self,
        features: pd.DataFrame,
        latest_frame: TelemetryReading,
        global_score: float,
        global_anomalous: bool,
    ) -> List[AnomalyFlag]:
        """Attribute the global anomaly verdict to individual sensors.

        A sensor is implicated when its instantaneous value deviates from
        its own 24 h rolling mean by more than 2× the rolling std
        (z-score attribution — cheap, deterministic and explainable).
        When the global verdict is anomalous but no sensor crosses the
        threshold, the strongest-deviation sensor is attributed so the
        frontend alert always names at least one offending channel.
        """
        row = features.iloc[0]
        sensor_by_metric: Dict[str, str] = {
            r.metric: r.sensor_id for r in latest_frame.readings if r.metric in CANONICAL_METRICS
        }
        z_by_metric: Dict[str, float] = {}
        for metric in CANONICAL_METRICS:
            if metric not in sensor_by_metric:
                continue
            mean24 = float(row.get(f"{metric}_24h_mean", 0.0))
            std24 = float(row.get(f"{metric}_24h_std", 0.0))
            value = float(row.get(metric, 0.0))
            z_by_metric[metric] = abs(value - mean24) / std24 if std24 > 1e-9 else 0.0

        implicated = {m for m, z in z_by_metric.items() if z >= 2.0} if global_anomalous else set()
        if global_anomalous and not implicated and z_by_metric:
            implicated = {max(z_by_metric, key=z_by_metric.get)}

        flags: List[AnomalyFlag] = []
        for metric, z in z_by_metric.items():
            sensor_anomalous = metric in implicated
            flags.append(
                AnomalyFlag(
                    sensor_id=sensor_by_metric[metric],
                    metric=metric,
                    anomaly_score=round(global_score, 6),
                    is_anomalous=sensor_anomalous,
                    severity=self._severity(global_score, z, sensor_anomalous),
                )
            )
        return flags

    @staticmethod
    def _severity(score: float, z: float, anomalous: bool) -> AnomalySeverity:
        if not anomalous:
            return AnomalySeverity.LOW
        if score < -0.15 or z >= 4.0:
            return AnomalySeverity.CRITICAL
        if score < -0.05 or z >= 3.0:
            return AnomalySeverity.HIGH
        return AnomalySeverity.MEDIUM

    # ------------------------------------------------------------------ #
    # Heuristic fallback (no artifacts)                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _heuristic_rul(features: pd.DataFrame) -> float:
        """Physics-flavoured estimate: hotter + shakier → shorter life."""
        row = features.iloc[0]
        temp = float(row.get("bearing_temp", 65.0))
        vib = float(row.get("vibration_rms", 1.8))
        temp_stress = max(temp - 60.0, 0.0) / 40.0     # 0..1 over 60→100 °C
        vib_stress = max(vib - 1.5, 0.0) / 6.0         # 0..1 over 1.5→7.5 mm/s
        stress = min(max(temp_stress, vib_stress), 1.0)
        return float((1.0 - stress) * 24.0 * 60.0)      # up to 60 days

    def _heuristic_anomaly(
        self, features: pd.DataFrame, latest_frame: TelemetryReading
    ) -> Tuple[float, bool, List[AnomalyFlag]]:
        row = features.iloc[0]
        temp_grad = float(row.get("bearing_temp_grad_per_hr", 0.0))
        vib_p2p = float(row.get("vibration_rms_p2p_24h", 0.0))
        anomalous = bool(temp_grad > 2.0 or vib_p2p > 2.5)
        score = -0.05 if anomalous else 0.1
        flags = self._per_sensor_flags(features, latest_frame, score, anomalous)
        return score, anomalous, flags

    # ------------------------------------------------------------------ #
    # Payload assembly                                                    #
    # ------------------------------------------------------------------ #

    def _build_response(
        self,
        request: InferenceRequest,
        rul_hours: float,
        anomaly_result: Tuple[float, bool, List[AnomalyFlag]],
        fallback_used: bool,
        latency_ms: float,
    ) -> InferenceResponse:
        score, is_anomalous, flags = anomaly_result
        settings = self._settings
        report = self._registry.load_report() if self._registry.artifacts_available() else None

        rul_days = rul_hours / 24.0
        rul = RulEstimate(
            value_days=round(rul_days, 2),
            lower_bound_days=round(max(rul_days * (1.0 - _RUL_BOUND_FRACTION), 0.0), 2),
            upper_bound_days=round(rul_days * (1.0 + _RUL_BOUND_FRACTION), 2),
            confidence_level=0.9,
            model_name=settings.pdm_rul_model_name,
            model_version=report.rul_model_version if report else "1.0.0",
        )

        # RUL → probability of failure inside the requested horizon.
        # Sigmoid centred on the horizon; anomaly presence lifts the floor.
        horizon = float(request.horizon_hours)
        base_p = 1.0 / (1.0 + np.exp((rul_hours - horizon) / _PROB_SCALE_HOURS))
        if is_anomalous:
            base_p = max(base_p, min(0.5 + abs(score) * 2.0, 0.95))
        probability = float(np.clip(base_p, 0.0, 1.0))

        latest_ts = request.history[-1].timestamp
        most_likely = latest_ts + timedelta(hours=rul_hours)
        window = FailureWindow(
            earliest=latest_ts + timedelta(hours=rul_hours * (1.0 - _RUL_BOUND_FRACTION)),
            latest=latest_ts + timedelta(hours=rul_hours * (1.0 + _RUL_BOUND_FRACTION)),
            most_likely=most_likely,
        )

        failure = FailureProbability(
            probability=round(probability, 4),
            predicted_window=window,
            failure_mode_id="failuremode-bearing-overheat" if is_anomalous else None,
            failure_mode_label="Bearing Overheat" if is_anomalous else None,
            model_name=settings.pdm_failure_model_name,
        )

        return InferenceResponse(
            asset_id=request.asset_id,
            component_id=request.component_id or request.history[-1].component_id,
            rul=rul,
            failure_probability=failure,
            anomaly_flags=flags,
            anomalous_sensors=[f.sensor_id for f in flags if f.is_anomalous],
            explanation_id=str(uuid.uuid4()),
            inference_latency_ms=round(latency_ms, 2),
            fallback_used=fallback_used,
        )


# ---------------------------------------------------------------------------
# Singleton accessor (mirrors get_graphrag_service pattern)
# ---------------------------------------------------------------------------

_service_lock = threading.Lock()
_service: Optional[PredictionService] = None


def get_prediction_service() -> PredictionService:
    global _service
    with _service_lock:
        if _service is None:
            _service = PredictionService()
        return _service
