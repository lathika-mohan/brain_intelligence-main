"""
Phase 6 — Feature Engineering & Dataset Preparation.

Transforms raw time-series telemetry frames (the frozen upstream contract from
Member 2, ``app.models.telemetry.TelemetryReading``) into deterministic,
reproducible ML feature vectors consumed by *both* the training pipeline and
the live inference service. The same code path runs offline and on-the-fly so
train/serve skew is impossible.

Design
------
1. **Upstream Telemetry Alignment** — ``frames_to_dataframe`` pivots the
   nested ``TelemetryReading.readings`` list into a wide, time-indexed
   DataFrame with one column per canonical metric (bearing_temp,
   vibration_rms, pressure, flow_rate, rpm, load_kw).

2. **Rolling-Window Statistics** — ``compute_rolling_features`` derives
   mean / std / var / min / max over 1 h, 6 h and 24 h windows plus
   rate-of-change (gradient) channels for the critical degradation
   indicators (bearing temperature, peak-to-peak vibration velocity).

3. **Degradation Labelling** — ``build_rul_labels`` constructs a piecewise-
   linear RUL target from run-to-failure records: RUL is capped at
   ``rul_cap_hours`` during healthy early life and decays linearly to zero
   at the failure timestamp (the standard NASA C-MAPSS style labelling).

Contract safety
---------------
Malformed telemetry raises ``TelemetryContractError`` (a ``ValueError``
subclass) with an explicit message, which the API layer maps to HTTP 422.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

import numpy as np
import pandas as pd

from app.models.telemetry import TelemetryReading

# --------------------------------------------------------------------------
# Canonical schema
# --------------------------------------------------------------------------

#: Canonical metric channels (order matters — it defines the feature layout).
CANONICAL_METRICS: List[str] = [
    "bearing_temp",
    "vibration_rms",
    "pressure",
    "flow_rate",
    "rpm",
    "load_kw",
]

#: Rolling windows required by the phase spec.
ROLLING_WINDOWS: dict[str, str] = {"1h": "1h", "6h": "6h", "24h": "24h"}

#: Statistics computed per (metric, window).
ROLLING_STATS: List[str] = ["mean", "std", "var", "min", "max"]

#: Metrics that additionally get rate-of-change (gradient) features.
GRADIENT_METRICS: List[str] = ["bearing_temp", "vibration_rms"]


class TelemetryContractError(ValueError):
    """Raised when incoming telemetry violates the frozen Phase 0 schema."""


# --------------------------------------------------------------------------
# 1. Upstream telemetry alignment
# --------------------------------------------------------------------------

def _validate_frames(frames: Sequence[TelemetryReading]) -> None:
    if not frames:
        raise TelemetryContractError(
            "Telemetry history is empty: at least one TelemetryReading frame is required."
        )
    asset_ids = {f.asset_id for f in frames}
    if len(asset_ids) > 1:
        raise TelemetryContractError(
            f"Telemetry history mixes multiple assets {sorted(asset_ids)}; "
            "one InferenceRequest must reference exactly one asset."
        )
    for f in frames:
        if not f.readings:
            raise TelemetryContractError(
                f"TelemetryReading at {f.timestamp.isoformat()} contains no sensor readings."
            )
        for r in f.readings:
            if not np.isfinite(r.value):
                raise TelemetryContractError(
                    f"Non-finite value for metric '{r.metric}' (sensor '{r.sensor_id}') "
                    f"at {f.timestamp.isoformat()}."
                )


def frames_to_dataframe(frames: Sequence[TelemetryReading]) -> pd.DataFrame:
    """Pivot nested telemetry frames into a wide, time-indexed DataFrame.

    Returns a DataFrame indexed by UTC timestamp with one column per
    canonical metric. Unknown metrics are ignored (forward-compatible);
    missing canonical metrics are forward/backward-filled then defaulted
    to 0.0 so the downstream feature layout is always identical.
    """
    _validate_frames(frames)

    rows: list[dict] = []
    for frame in frames:
        row: dict = {"timestamp": pd.Timestamp(frame.timestamp)}
        for reading in frame.readings:
            if reading.metric in CANONICAL_METRICS:
                row[reading.metric] = float(reading.value)
        rows.append(row)

    df = pd.DataFrame(rows).set_index("timestamp").sort_index()
    # De-duplicate identical timestamps (keep the latest observation).
    df = df[~df.index.duplicated(keep="last")]

    for metric in CANONICAL_METRICS:
        if metric not in df.columns:
            df[metric] = np.nan
    df = df[CANONICAL_METRICS]
    df = df.ffill().bfill().fillna(0.0)
    return df


# --------------------------------------------------------------------------
# 2. Rolling-window feature computation
# --------------------------------------------------------------------------

def feature_columns() -> List[str]:
    """Deterministic list of engineered feature names (defines model input layout)."""
    cols: List[str] = []
    for metric in CANONICAL_METRICS:
        cols.append(metric)  # instantaneous value
        for wname in ROLLING_WINDOWS:
            for stat in ROLLING_STATS:
                cols.append(f"{metric}_{wname}_{stat}")
    for metric in GRADIENT_METRICS:
        cols.append(f"{metric}_grad_per_hr")
        cols.append(f"{metric}_p2p_24h")
    return cols


def compute_rolling_features(wide: pd.DataFrame) -> pd.DataFrame:
    """Compute the full rolling-window feature matrix from a wide telemetry frame.

    Deterministic: identical input always yields identical output. Missing
    early-history windows fall back to expanding statistics (std/var → 0).
    """
    if wide.empty:
        raise TelemetryContractError("Cannot compute features on an empty telemetry frame.")
    if not isinstance(wide.index, pd.DatetimeIndex):
        raise TelemetryContractError("Telemetry frame must be indexed by timestamp.")

    feats = pd.DataFrame(index=wide.index)

    for metric in CANONICAL_METRICS:
        series = wide[metric].astype(float)
        feats[metric] = series
        for wname, offset in ROLLING_WINDOWS.items():
            roll = series.rolling(offset, min_periods=1)
            feats[f"{metric}_{wname}_mean"] = roll.mean()
            feats[f"{metric}_{wname}_std"] = roll.std().fillna(0.0)
            feats[f"{metric}_{wname}_var"] = roll.var().fillna(0.0)
            feats[f"{metric}_{wname}_min"] = roll.min()
            feats[f"{metric}_{wname}_max"] = roll.max()

    # Rate-of-change (per hour) + 24 h peak-to-peak for critical channels.
    elapsed_hr = (
        wide.index.to_series().diff().dt.total_seconds().div(3600.0).replace(0.0, np.nan)
    )
    for metric in GRADIENT_METRICS:
        series = wide[metric].astype(float)
        grad = series.diff().div(elapsed_hr)
        feats[f"{metric}_grad_per_hr"] = grad.replace([np.inf, -np.inf], 0.0).fillna(0.0)
        roll24 = series.rolling("24h", min_periods=1)
        feats[f"{metric}_p2p_24h"] = roll24.max() - roll24.min()

    feats = feats[feature_columns()]
    feats = feats.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return feats


def build_feature_matrix(frames: Sequence[TelemetryReading]) -> pd.DataFrame:
    """End-to-end: telemetry frames → engineered feature matrix (all rows)."""
    return compute_rolling_features(frames_to_dataframe(frames))


def latest_feature_vector(frames: Sequence[TelemetryReading]) -> pd.DataFrame:
    """Single-row feature vector for the newest frame (live inference path)."""
    feats = build_feature_matrix(frames)
    return feats.iloc[[-1]]


# --------------------------------------------------------------------------
# 3. Degradation labelling — RUL target vector
# --------------------------------------------------------------------------

def build_rul_labels(
    timestamps: Iterable[pd.Timestamp],
    failure_time: pd.Timestamp,
    rul_cap_hours: float = 24.0 * 60.0,
) -> pd.Series:
    """Piecewise-linear RUL labels for one run-to-failure episode.

    RUL(t) = min(rul_cap_hours, failure_time - t) expressed in **hours**,
    clipped at zero after the failure event. The cap emulates the standard
    'healthy plateau' used in C-MAPSS-style RUL regression so the model is
    not penalised for early-life uncertainty.
    """
    idx = pd.DatetimeIndex(list(timestamps))
    if len(idx) == 0:
        raise TelemetryContractError("Cannot build RUL labels for an empty timestamp index.")
    failure_ts = pd.Timestamp(failure_time)
    remaining_hr = (failure_ts - idx).total_seconds() / 3600.0
    rul = np.clip(remaining_hr, 0.0, float(rul_cap_hours))
    return pd.Series(rul, index=idx, name="rul_hours")
