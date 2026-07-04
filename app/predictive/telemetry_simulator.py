"""
Phase 6 — Run-to-failure telemetry generator.

Produces physically-plausible degradation episodes matching the frozen
``TelemetryReading`` contract so the training pipeline (and the pytest
suite) can run end-to-end without a live historian connection. When the
plant historian is wired in (Member 2's Kafka topic ``telemetry.raw``),
``load_run_to_failure_episodes`` is the single seam to replace.

Every episode simulates a rotating asset (pump/compressor) whose bearing
degrades: bearing temperature and vibration RMS trend upward with
accelerating (quadratic) drift plus stochastic noise, while pressure/flow
slowly derate. The failure timestamp is the end of the episode.

Deterministic given a seed — training runs are reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np

from app.models.telemetry import OperatingMode, SensorReading, TelemetryReading


@dataclass
class Episode:
    """One run-to-failure record: frames plus the failure timestamp."""

    asset_id: str
    component_id: str
    frames: List[TelemetryReading]
    failure_time: datetime
    failure_mode_id: str = "failuremode-bearing-overheat"
    failure_mode_label: str = "Bearing Overheat"
    metadata: dict = field(default_factory=dict)


def _sensor(sensor_id: str, metric: str, value: float, unit: str) -> SensorReading:
    return SensorReading(sensor_id=sensor_id, metric=metric, value=float(value), unit=unit, quality=1.0)


def generate_episode(
    asset_id: str,
    *,
    duration_hours: float = 240.0,
    sample_minutes: float = 10.0,
    degradation_onset: float = 0.45,
    seed: int = 7,
    start: datetime | None = None,
    healthy_only: bool = False,
) -> Episode:
    """Generate one degradation episode ending in failure.

    ``degradation_onset`` is the fraction of the episode after which the
    fault signature starts accelerating. ``healthy_only=True`` yields a
    flat, no-fault baseline (used to fit the Isolation Forest on healthy
    operation only).
    """
    rng = np.random.default_rng(seed)
    start = start or (datetime(2026, 1, 1, tzinfo=timezone.utc))
    n = max(int(duration_hours * 60.0 / sample_minutes), 24)
    t = np.linspace(0.0, 1.0, n)

    # Degradation factor: 0 while healthy, quadratic ramp after onset.
    if healthy_only:
        dgr = np.zeros(n)
    else:
        dgr = np.clip((t - degradation_onset) / (1.0 - degradation_onset), 0.0, None) ** 2

    bearing_temp = 62.0 + 4.0 * np.sin(t * 6.0) * 0.2 + 28.0 * dgr + rng.normal(0, 0.6, n)
    vibration = 1.6 + 0.15 * np.sin(t * 9.0) * 0.3 + 4.5 * dgr + rng.normal(0, 0.08, n)
    pressure = 8.4 - 1.2 * dgr + rng.normal(0, 0.10, n)
    flow = 120.0 - 18.0 * dgr + rng.normal(0, 1.2, n)
    rpm = 2950.0 - 40.0 * dgr + rng.normal(0, 6.0, n)
    load = 185.0 + 22.0 * dgr + rng.normal(0, 1.8, n)

    frames: List[TelemetryReading] = []
    for i in range(n):
        ts = start + timedelta(minutes=sample_minutes * i)
        frames.append(
            TelemetryReading(
                asset_id=asset_id,
                component_id=f"{asset_id}-bearing-de",
                timestamp=ts,
                operating_mode=OperatingMode.RUNNING,
                readings=[
                    _sensor(f"{asset_id}-s1", "bearing_temp", bearing_temp[i], "C"),
                    _sensor(f"{asset_id}-s2", "vibration_rms", vibration[i], "mm/s"),
                    _sensor(f"{asset_id}-s3", "pressure", pressure[i], "bar"),
                    _sensor(f"{asset_id}-s4", "flow_rate", flow[i], "m3/h"),
                    _sensor(f"{asset_id}-s5", "rpm", rpm[i], "rpm"),
                    _sensor(f"{asset_id}-s6", "load_kw", load[i], "kW"),
                ],
            )
        )

    failure_time = frames[-1].timestamp
    return Episode(
        asset_id=asset_id,
        component_id=f"{asset_id}-bearing-de",
        frames=frames,
        failure_time=failure_time,
        metadata={"seed": seed, "healthy_only": healthy_only, "n_frames": n},
    )


def load_run_to_failure_episodes(
    n_episodes: int = 6,
    *,
    duration_hours: float = 240.0,
    sample_minutes: float = 10.0,
    seed: int = 42,
) -> List[Episode]:
    """Historian seam: return a fleet of run-to-failure episodes.

    Replace this body with a Neo4j/Kafka-backed loader once Member 2's
    historical failure-mode timestamps (Phase 1/2 catalogue) are online —
    the return type is the only contract the trainer depends on.
    """
    rng = np.random.default_rng(seed)
    episodes: List[Episode] = []
    for k in range(n_episodes):
        episodes.append(
            generate_episode(
                asset_id=f"asset-{101 + k}",
                duration_hours=duration_hours * float(rng.uniform(0.8, 1.2)),
                sample_minutes=sample_minutes,
                degradation_onset=float(rng.uniform(0.35, 0.6)),
                seed=int(rng.integers(0, 2**31 - 1)),
                start=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=3 * k),
            )
        )
    return episodes
