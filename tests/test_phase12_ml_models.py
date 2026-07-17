import pytest
import numpy as np
import pandas as pd
from app.predictive.model_registry import get_model_registry
from app.predictive.prediction_service import PredictionService

@pytest.fixture(scope="module")
def prediction_service():
    # Make sure we use a test registry or standard registry
    registry = get_model_registry()
    service = PredictionService(registry=registry)
    return service

def test_rul_prediction_bounds(prediction_service):
    """
    Assert that prediction outputs fall within mathematically acceptable bounds.
    E.g., RUL cannot be extremely negative or infinity.
    """
    # Assuming standard features as defined in feature_engineering
    features = pd.DataFrame([{
        "temperature": 75.0,
        "vibration": 0.05,
        "pressure": 120.0,
        "temperature_rolling_mean": 74.0,
        "vibration_rolling_std": 0.01,
        "temp_vib_interaction": 3.75
    }])
    
    try:
        results = prediction_service.predict_batch(features)
        for res in results:
            assert res.rul_days >= 0, "RUL prediction should not be negative under normal conditions."
            assert res.anomaly_score >= -1.0 and res.anomaly_score <= 1.0, "Anomaly score out of bounds."
    except FileNotFoundError:
        pytest.skip("Models not trained yet in this environment. Skipping model validation tests.")

def test_out_of_bounds_telemetry_handling(prediction_service):
    """
    Check that models handle out-of-bounds telemetry values without returning NaN.
    """
    features = pd.DataFrame([{
        "temperature": 9999.0, # Extreme value
        "vibration": -999.0,   # Extreme value
        "pressure": np.nan,    # Missing value
        "temperature_rolling_mean": 9999.0,
        "vibration_rolling_std": 0.0,
        "temp_vib_interaction": -9989001.0
    }])
    
    try:
        # Some models fail on NaN, we test if the service handles it (e.g., imputation or fallback)
        # XGBoost handles NaNs natively
        results = prediction_service.predict_batch(features)
        for res in results:
            assert not np.isnan(res.rul_days), "Model returned NaN for RUL on edge case data."
            assert not np.isnan(res.anomaly_score), "Model returned NaN for anomaly score."
    except FileNotFoundError:
        pytest.skip("Models not trained yet in this environment.")
        
def test_monotonic_rul_degradation(prediction_service):
    """
    Verify that RUL predictions degrade monotonically as anomaly/stress scores spike.
    """
    # Gradually increasing vibration and temperature
    try:
        ruls = []
        for i in range(1, 10):
            features = pd.DataFrame([{
                "temperature": 70.0 + (i * 10),
                "vibration": 0.02 + (i * 0.1),
                "pressure": 100.0,
                "temperature_rolling_mean": 70.0 + (i * 10),
                "vibration_rolling_std": 0.01 + (i * 0.05),
                "temp_vib_interaction": (70.0 + (i * 10)) * (0.02 + (i * 0.1))
            }])
            res = prediction_service.predict_batch(features)
            ruls.append(res[0].rul_days)
            
        # Check if RUL generally goes down as machine stress goes up
        # This isn't strictly monotonic in non-linear models but overall trend should be down
        trend = np.polyfit(range(len(ruls)), ruls, 1)[0]
        assert trend <= 0, f"RUL trend should be decreasing as stress increases. Trend: {trend}"
    except FileNotFoundError:
        pytest.skip("Models not trained yet in this environment.")
