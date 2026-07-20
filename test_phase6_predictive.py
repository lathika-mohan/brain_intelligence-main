"""
Phase 6 — Predictive Maintenance Engine test suite.

Covers (all offline — no Neo4j/Qdrant/Kafka required):

  1. Feature engineering — determinism, layout, rolling windows, gradients.
  2. Degradation labelling — piecewise-linear RUL targets.
  3. Training pipeline — XGBoost RUL + Isolation Forest + evaluation report.
  4. Model registry — thread-safe save/load round-trip.
  5. Prediction service — async dual-model inference, fallback policy.
  6. Contract enforcement — invalid telemetry shapes raise clear, predictable
     exceptions (HTTP 422 at the API edge); valid data returns the exact
     JSON signature consumed by DigitalTwinView.tsx.

Run:  pytest tests/test_phase6_predictive.py -q
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.predictive import InferenceRequest, InferenceResponse
from app.models.telemetry import SensorReading, TelemetryBatch, TelemetryReading
from app.predictive.feature_engineering import (
    CANONICAL_METRICS,
    TelemetryContractError,
    build_feature_matrix,
    build_rul_labels,
    feature_columns,
    frames_to_dataframe,
    latest_feature_vector,
)
from app.predictive.model_registry import ModelRegistry
from app.predictive.prediction_service import PredictionService
from app.predictive.telemetry_simulator import generate_episode, load_run_to_failure_episodes
from app.predictive.train_predictive_models import (
    episodes_to_dataset,
    evaluate_anomaly,
    evaluate_rul,
    run_training,
    split_episodes,
    train_anomaly_model,
    train_rul_model,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_frame(asset_id: str = "asset-101", ts: datetime | None = None, temp: float = 65.0) -> TelemetryReading:
    ts = ts or datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    return TelemetryReading(
        asset_id=asset_id,
        component_id=f"{asset_id}-bearing-de",
        timestamp=ts,
        readings=[
            SensorReading(sensor_id="s1", metric="bearing_temp", value=temp, unit="C"),
            SensorReading(sensor_id="s2", metric="vibration_rms", value=1.8, unit="mm/s"),
            SensorReading(sensor_id="s3", metric="pressure", value=8.2, unit="bar"),
            SensorReading(sensor_id="s4", metric="flow_rate", value=120.0, unit="m3/h"),
            SensorReading(sensor_id="s5", metric="rpm", value=2950.0, unit="rpm"),
            SensorReading(sensor_id="s6", metric="load_kw", value=185.0, unit="kW"),
        ],
    )


def make_history(n: int = 30, asset_id: str = "asset-101") -> list[TelemetryReading]:
    base = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    return [make_frame(asset_id, base + timedelta(minutes=10 * i), temp=65.0 + 0.05 * i) for i in range(n)]


@pytest.fixture(scope="module")
def trained_registry(tmp_path_factory) -> ModelRegistry:
    """Train a small but real model pair once for the whole module."""
    path = tmp_path_factory.mktemp("artifacts")
    run_training(n_episodes=4, registry_path=path, seed=7)
    return ModelRegistry(path)


# ===========================================================================
# 1. Feature engineering
# ===========================================================================

class TestFeatureEngineering:
    def test_frames_to_dataframe_wide_layout(self):
        df = frames_to_dataframe(make_history(10))
        assert list(df.columns) == CANONICAL_METRICS
        assert len(df) == 10
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.is_monotonic_increasing

    def test_feature_matrix_layout_matches_declared_columns(self):
        feats = build_feature_matrix(make_history(20))
        assert list(feats.columns) == feature_columns()
        assert not feats.isna().any().any()
        assert np.isfinite(feats.values).all()

    def test_feature_engineering_is_deterministic(self):
        history = make_history(25)
        a = build_feature_matrix(history)
        b = build_feature_matrix(history)
        pd.testing.assert_frame_equal(a, b)

    def test_rolling_stats_are_correct_for_constant_signal(self):
        history = make_history(12)
        for f in history:
            f.readings[0].value = 70.0  # constant bearing_temp
        feats = build_feature_matrix(history)
        last = feats.iloc[-1]
        assert last["bearing_temp_1h_mean"] == pytest.approx(70.0)
        assert last["bearing_temp_24h_std"] == pytest.approx(0.0, abs=1e-9)
        assert last["bearing_temp_p2p_24h"] == pytest.approx(0.0, abs=1e-9)

    def test_gradient_feature_captures_rate_of_change(self):
        base = datetime(2026, 6, 1, tzinfo=UTC)
        history = [make_frame(ts=base + timedelta(hours=i), temp=60.0 + 5.0 * i) for i in range(6)]
        feats = build_feature_matrix(history)
        # +5 °C per hour ramp → gradient ≈ 5
        assert feats.iloc[-1]["bearing_temp_grad_per_hr"] == pytest.approx(5.0, rel=1e-6)

    def test_latest_feature_vector_is_single_row(self):
        vec = latest_feature_vector(make_history(15))
        assert vec.shape == (1, len(feature_columns()))

    def test_unknown_metrics_ignored_and_missing_filled(self):
        frame = make_frame()
        frame.readings.append(SensorReading(sensor_id="sx", metric="exotic_metric", value=1.0))
        feats = build_feature_matrix([frame, make_frame(ts=frame.timestamp + timedelta(minutes=10))])
        assert "exotic_metric" not in feats.columns
        assert list(feats.columns) == feature_columns()


# ===========================================================================
# 2. Degradation labelling
# ===========================================================================

class TestRulLabels:
    def test_piecewise_linear_decay_and_cap(self):
        base = datetime(2026, 6, 1, tzinfo=UTC)
        idx = [base + timedelta(hours=h) for h in range(0, 100, 10)]
        failure = base + timedelta(hours=90)
        labels = build_rul_labels(idx, pd.Timestamp(failure), rul_cap_hours=50.0)
        assert labels.iloc[0] == pytest.approx(50.0)          # capped early life
        assert labels.iloc[-1] == pytest.approx(0.0)          # zero at failure
        assert labels.iloc[-2] == pytest.approx(10.0)         # linear decay
        assert (labels.diff().dropna() <= 0).all()            # monotone non-increasing

    def test_empty_index_raises_contract_error(self):
        with pytest.raises(TelemetryContractError):
            build_rul_labels([], pd.Timestamp("2026-06-01", tz="UTC"))


# ===========================================================================
# 3. Contract enforcement — invalid telemetry shapes
# ===========================================================================

class TestContractViolations:
    def test_empty_history_rejected(self):
        with pytest.raises(TelemetryContractError, match="empty"):
            frames_to_dataframe([])

    def test_mixed_assets_rejected(self):
        frames = [make_frame("asset-101"), make_frame("asset-202", ts=datetime(2026, 6, 1, 13, tzinfo=UTC))]
        with pytest.raises(TelemetryContractError, match="multiple assets"):
            frames_to_dataframe(frames)

    def test_non_finite_value_rejected(self):
        frame = make_frame()
        frame.readings[0].value = float("nan")
        with pytest.raises(TelemetryContractError, match="Non-finite"):
            frames_to_dataframe([frame])

    def test_pydantic_rejects_frame_without_readings(self):
        with pytest.raises(ValidationError):
            TelemetryReading(
                asset_id="asset-101",
                timestamp=datetime(2026, 6, 1, tzinfo=UTC),
                readings=[],
            )

    def test_pydantic_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            SensorReading(sensor_id="s1", metric="bearing_temp", value=1.0, bogus_field=1)

    def test_pydantic_rejects_out_of_range_quality(self):
        with pytest.raises(ValidationError):
            SensorReading(sensor_id="s1", metric="bearing_temp", value=1.0, quality=1.5)

    def test_telemetry_batch_contract_roundtrip(self):
        batch = TelemetryBatch(
            batch_id="batch-0001",
            produced_at=datetime(2026, 6, 1, tzinfo=UTC),
            readings=[make_frame()],
        )
        assert batch.readings[0].asset_id == "asset-101"


# ===========================================================================
# 4. Training pipeline + registry lifecycle
# ===========================================================================

class TestTrainingPipeline:
    def test_episode_dataset_alignment(self):
        eps = load_run_to_failure_episodes(n_episodes=2, duration_hours=48, seed=3)
        X, y, groups = episodes_to_dataset(eps)
        assert len(X) == len(y) == len(groups)
        assert list(X.columns) == feature_columns()
        assert (y >= 0).all()

    def test_episode_holdout_split_never_empty(self):
        eps = load_run_to_failure_episodes(n_episodes=4, duration_hours=24, seed=3)
        train, val = split_episodes(eps)
        assert len(train) >= 1 and len(val) >= 1
        assert {e.asset_id for e in train}.isdisjoint({e.asset_id for e in val})

    def test_rul_model_beats_naive_baseline(self):
        eps = load_run_to_failure_episodes(n_episodes=5, duration_hours=120, seed=11)
        train_eps, val_eps = split_episodes(eps)
        X_tr, y_tr, _ = episodes_to_dataset(train_eps)
        X_va, y_va, _ = episodes_to_dataset(val_eps)
        model = train_rul_model(X_tr, y_tr)
        metrics = evaluate_rul(model, X_va, y_va)
        naive_mae = float(np.mean(np.abs(y_va - y_tr.mean())))
        assert metrics.mae < naive_mae
        assert metrics.r2 > 0.5

    def test_isolation_forest_detects_degradation(self):
        eps = load_run_to_failure_episodes(n_episodes=5, duration_hours=120, seed=11)
        train_eps, val_eps = split_episodes(eps)
        X_tr, y_tr, _ = episodes_to_dataset(train_eps)
        X_va, y_va, _ = episodes_to_dataset(val_eps)
        model = train_anomaly_model(X_tr[y_tr > 24.0 * 2], contamination=0.02, seed=11)
        y_true = (y_va < 24.0).astype(int).values
        metrics = evaluate_anomaly(model, X_va, y_true, 0.02)
        assert metrics.recall > 0.5  # catches most end-of-life frames
        assert 0.0 <= metrics.f1 <= 1.0

    def test_run_training_writes_all_artifacts(self, trained_registry: ModelRegistry):
        assert trained_registry.artifacts_available()
        assert trained_registry.report_path.exists()
        assert (trained_registry.path / "model_evaluation_report.md").exists()
        report = trained_registry.load_report()
        assert report is not None
        assert report.rul_metrics.n_samples > 0
        assert len(report.feature_importance) > 0
        assert report.feature_columns == feature_columns()

    def test_registry_reload_roundtrip(self, trained_registry: ModelRegistry):
        fresh = ModelRegistry(trained_registry.path)
        rul = fresh.load_rul_model()
        iso = fresh.load_anomaly_model()
        vec = latest_feature_vector(make_history(20))
        assert np.isfinite(float(rul.predict(vec)[0]))
        assert iso.predict(vec.values)[0] in (-1, 1)
        fresh.reload()
        assert fresh.load_rul_model() is not None


# ===========================================================================
# 5. Prediction service (async dual-model inference)
# ===========================================================================

class TestPredictionService:
    @pytest.mark.asyncio
    async def test_valid_inference_returns_frozen_contract(self, trained_registry: ModelRegistry):
        service = PredictionService(registry=trained_registry)
        request = InferenceRequest(asset_id="asset-101", history=make_history(60), horizon_hours=24)
        response = await service.infer(request)

        assert isinstance(response, InferenceResponse)
        assert response.asset_id == "asset-101"
        assert response.fallback_used is False
        # RUL block with bounds
        assert response.rul.lower_bound_days <= response.rul.value_days <= response.rul.upper_bound_days
        # Normalised failure probability
        assert 0.0 <= response.failure_probability.probability <= 1.0
        w = response.failure_probability.predicted_window
        assert w.earliest <= w.most_likely <= w.latest
        # Per-sensor anomaly flags for every canonical metric present
        assert {f.metric for f in response.anomaly_flags} == set(CANONICAL_METRICS)
        assert response.explanation_id  # linkable to /xai/explain
        assert response.inference_latency_ms >= 0.0

    @pytest.mark.asyncio
    async def test_degraded_asset_scores_worse_than_healthy(self, trained_registry: ModelRegistry):
        service = PredictionService(registry=trained_registry)
        healthy_ep = generate_episode("asset-101", duration_hours=48, healthy_only=True, seed=5)
        failing_ep = generate_episode("asset-101", duration_hours=200, degradation_onset=0.3, seed=5)

        healthy = await service.infer(InferenceRequest(asset_id="asset-101", history=healthy_ep.frames[-72:]))
        failing = await service.infer(InferenceRequest(asset_id="asset-101", history=failing_ep.frames[-72:]))

        assert failing.rul.value_days < healthy.rul.value_days
        assert failing.failure_probability.probability > healthy.failure_probability.probability

    @pytest.mark.asyncio
    async def test_mismatched_asset_id_raises_contract_error(self, trained_registry: ModelRegistry):
        service = PredictionService(registry=trained_registry)
        request = InferenceRequest(asset_id="asset-999", history=make_history(10, asset_id="asset-101"))
        with pytest.raises(TelemetryContractError, match="does not match"):
            await service.infer(request)

    @pytest.mark.asyncio
    async def test_fallback_used_when_artifacts_missing(self, tmp_path):
        service = PredictionService(registry=ModelRegistry(tmp_path / "empty"))
        response = await service.infer(InferenceRequest(asset_id="asset-101", history=make_history(20)))
        assert response.fallback_used is True
        assert 0.0 <= response.failure_probability.probability <= 1.0

    def test_response_json_signature_expected_by_frontend(self, trained_registry: ModelRegistry):
        """The serialised payload must carry the exact keys DigitalTwinView tracks."""
        import asyncio

        service = PredictionService(registry=trained_registry)
        request = InferenceRequest(asset_id="asset-101", history=make_history(40))
        payload = asyncio.run(service.infer(request)).model_dump(mode="json")

        assert set(payload.keys()) == {
            "asset_id", "component_id", "rul", "failure_probability",
            "anomaly_flags", "anomalous_sensors", "explanation_id",
            "inference_latency_ms", "generated_at", "fallback_used",
        }
        assert set(payload["rul"].keys()) == {
            "value_days", "lower_bound_days", "upper_bound_days",
            "confidence_level", "model_name", "model_version",
        }
        assert set(payload["failure_probability"].keys()) == {
            "probability", "predicted_window", "failure_mode_id",
            "failure_mode_label", "model_name", "model_version",
        }
        assert set(payload["failure_probability"]["predicted_window"].keys()) == {
            "earliest", "latest", "most_likely",
        }
        for flag in payload["anomaly_flags"]:
            assert set(flag.keys()) == {
                "sensor_id", "metric", "anomaly_score",
                "is_anomalous", "severity", "detected_at",
            }


# ===========================================================================
# 6. API endpoint contract (FastAPI edge)
# ===========================================================================

class TestPredictiveApi:
    @pytest.fixture()
    def client(self, trained_registry: ModelRegistry, monkeypatch) -> TestClient:
        # Point the API-layer singletons at the trained per-test registry.
        import app.predictive.model_registry as mr
        import app.predictive.prediction_service as ps

        monkeypatch.setattr(mr, "_registry", trained_registry)
        monkeypatch.setattr(ps, "_service", PredictionService(registry=trained_registry))
        from app.main import app as fastapi_app

        return TestClient(fastapi_app)

    def _body(self, n: int = 40) -> dict:
        return InferenceRequest(asset_id="asset-101", history=make_history(n)).model_dump(mode="json")

    def test_infer_returns_wrapped_contract_payload(self, client: TestClient):
        res = client.post("/api/v1/predictive/infer", json=self._body())
        assert res.status_code == 200
        envelope = res.json()
        assert envelope["success"] is True
        assert envelope["error"] is None
        data = envelope["data"]
        assert data["asset_id"] == "asset-101"
        assert "rul" in data and "failure_probability" in data and "anomaly_flags" in data
        assert 0.0 <= data["failure_probability"]["probability"] <= 1.0

    def test_invalid_shape_missing_history_is_422(self, client: TestClient):
        res = client.post("/api/v1/predictive/infer", json={"asset_id": "asset-101"})
        assert res.status_code == 422

    def test_invalid_shape_empty_history_is_422(self, client: TestClient):
        res = client.post("/api/v1/predictive/infer", json={"asset_id": "asset-101", "history": []})
        assert res.status_code == 422

    def test_invalid_shape_extra_field_is_422(self, client: TestClient):
        body = self._body(5)
        body["hacker_field"] = "x"
        res = client.post("/api/v1/predictive/infer", json=body)
        assert res.status_code == 422

    def test_mixed_asset_contract_violation_is_422_with_message(self, client: TestClient):
        body = self._body(5)
        body["asset_id"] = "asset-999"
        res = client.post("/api/v1/predictive/infer", json=body)
        assert res.status_code == 422
        assert "does not match" in str(res.json()["message"])

    def test_health_endpoint_reports_ready(self, client: TestClient):
        res = client.get("/api/v1/predictive/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"

    def test_evaluation_endpoint_returns_report(self, client: TestClient):
        res = client.get("/api/v1/predictive/evaluation")
        assert res.status_code == 200
        body = res.json()
        assert "rul_metrics" in body and "anomaly_metrics" in body
        assert body["feature_columns"] == feature_columns()
