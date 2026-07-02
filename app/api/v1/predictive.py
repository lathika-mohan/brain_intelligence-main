"""
Predictive Maintenance router — powers `DigitalTwinView.tsx`.

Phase 0 scope: frozen contract behind a runnable stub endpoint. The real
XGBoost RUL/failure models and the Isolation Forest anomaly detector are
implemented in a later phase.
"""
from __future__ import annotations

import time
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter

from app.models.common import APIResponse, utc_now
from app.models.predictive import (
    AnomalyFlag,
    AnomalySeverity,
    FailureProbability,
    FailureWindow,
    InferenceRequest,
    InferenceResponse,
    RULEstimate,
)

router = APIRouter(prefix="/predictive", tags=["predictive-maintenance"])


@router.post("/infer", response_model=APIResponse[InferenceResponse])
def infer(payload: InferenceRequest) -> APIResponse[InferenceResponse]:
    """Contract-frozen stub — see module docstring."""
    started = time.perf_counter()
    now = utc_now()

    rul = RULEstimate(
        value_days=42.5,
        lower_bound_days=30.0,
        upper_bound_days=55.0,
        confidence_level=0.9,
        model_name="xgboost_rul_v1",
    )
    failure_probability = FailureProbability(
        probability=0.23,
        predicted_window=FailureWindow(
            earliest=now + timedelta(days=30),
            latest=now + timedelta(days=55),
            most_likely=now + timedelta(days=42),
        ),
        failure_mode_id="failuremode-stub-1",
        failure_mode_label="Bearing Overheat",
        model_name="xgboost_failure_classifier_v1",
    )
    anomaly_flags = [
        AnomalyFlag(
            sensor_id=payload.telemetry_window[-1].readings[0].sensor_id,
            metric=payload.telemetry_window[-1].readings[0].metric,
            anomaly_score=-0.12,
            is_anomalous=False,
            severity=AnomalySeverity.LOW,
        )
    ]

    response = InferenceResponse(
        asset_id=payload.asset_id,
        component_id=payload.component_id,
        rul=rul,
        failure_probability=failure_probability,
        anomaly_flags=anomaly_flags,
        explanation_id=str(uuid4()) if payload.include_explanation_hint else None,
        inference_latency_ms=round((time.perf_counter() - started) * 1000, 2),
        fallback_used=False,
    )
    return APIResponse[InferenceResponse](data=response)
