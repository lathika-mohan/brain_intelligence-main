import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from app.predictive.model_registry import get_model_registry
from app.predictive.prediction_service import PredictionService
from app.predictive.feature_engineering import compute_rolling_features


def _make_features(temp=75.0, vib=0.05, pres=120.0, flow=50.0, rpm_val=1500, load=200.0):
    """Generate a 25-row telemetry frame then compute rolling features."""
    times = pd.date_range("2025-01-01", periods=25, freq="h")
    rows = []
    for t in times:
        rows.append(
            {
                "bearing_temp": temp,
                "vibration_rms": vib,
                "pressure": pres,
                "flow_rate": flow,
                "rpm": rpm_val,
                "load_kw": load,
                "timestamp": t,
            }
        )
    df = pd.DataFrame(rows).set_index("timestamp")
    feats = compute_rolling_features(df)
    # Return the last row as a single-row DataFrame
    return feats.iloc[[-1]]


@pytest.fixture(scope="module")
def prediction_service():
    registry = get_model_registry()
    service = PredictionService(registry=registry)
    return service


def test_rul_prediction_bounds(prediction_service):
    """
    Assert that prediction outputs fall within mathematically acceptable bounds.
    E.g., RUL cannot be extremely negative or infinity.
    """
    try:
        features = _make_features()
        results = prediction_service.predict_batch(features)
        for res in results:
            assert res.rul_days >= 0, (
                "RUL prediction should not be negative under normal conditions."
            )
            assert -1.0 <= res.anomaly_score <= 1.0, (
                "Anomaly score out of bounds."
            )
    except FileNotFoundError:
        pytest.skip(
            "Models not trained yet in this environment. Skipping model validation tests."
        )


def test_out_of_bounds_telemetry_handling(prediction_service):
    """
    Check that models handle out-of-bounds telemetry values without returning NaN.
    """
    try:
        features = _make_features(temp=9999.0, vib=-999.0, pres=np.nan)
        results = prediction_service.predict_batch(features)
        for res in results:
            assert not np.isnan(res.rul_days), (
                "Model returned NaN for RUL on edge case data."
            )
            assert not np.isnan(res.anomaly_score), (
                "Model returned NaN for anomaly score."
            )
    except FileNotFoundError:
        pytest.skip("Models not trained yet in this environment.")


def test_monotonic_rul_degradation(prediction_service):
    """
    Verify that RUL predictions degrade monotonically as anomaly/stress scores spike.
    """
    try:
        ruls = []
        for i in range(1, 10):
            features = _make_features(temp=70.0 + (i * 10), vib=0.02 + (i * 0.1))
            res = prediction_service.predict_batch(features)
            ruls.append(res[0].rul_days)

        # Check if RUL generally goes down as machine stress goes up
        trend = np.polyfit(range(len(ruls)), ruls, 1)[0]
        assert trend <= 0, (
            f"RUL trend should be decreasing as stress increases. Trend: {trend}"
        )
    except FileNotFoundError:
        pytest.skip("Models not trained yet in this environment.")
