"""
Telemetry ingestion contracts — Phase 0 (frozen) + Phase 6 alignment.

This module is the *upstream* contract shared with Member 2 (Data & Edge
Engineer). Section 5 of ``docs/api_contracts.md`` freezes the wire shape:

    TelemetryBatch
      └── readings: List[TelemetryReading]
            └── readings: List[SensorReading]   (sensor_id, metric, value, unit, quality)

Phase 6 consumes these frames as the raw input of the predictive-maintenance
feature-engineering pipeline (``app/predictive/feature_engineering.py``).

The original Phase 0 ``TelemetryIngestRequest`` stub is preserved verbatim for
backward compatibility with earlier phases.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Phase 0 stub — kept for backward compatibility (do not remove)
# ---------------------------------------------------------------------------

class TelemetryIngestRequest(BaseModel):
    asset_id: str
    timestamp: datetime
    metrics: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None
    schema_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Frozen upstream contract (Member 2) — docs/api_contracts.md §5
# ---------------------------------------------------------------------------

class OperatingMode(str, Enum):
    """Operating state stamped on every telemetry frame."""

    RUNNING = "RUNNING"
    IDLE = "IDLE"
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"
    MAINTENANCE = "MAINTENANCE"
    FAULT = "FAULT"


class TelemetryMetric(str, Enum):
    """Canonical sensor metric vocabulary used across the platform.

    Mirrors the physical channels rendered by ``DigitalTwinView.tsx``
    (temperature / vibration / rpm / pressure / load) plus flow rate,
    which Member 2's edge gateway emits for pumps and compressors.
    """

    BEARING_TEMP = "bearing_temp"          # °C
    VIBRATION_RMS = "vibration_rms"        # mm/s (velocity, RMS)
    PRESSURE = "pressure"                  # bar
    FLOW_RATE = "flow_rate"                # m³/h
    RPM = "rpm"                            # rev/min
    LOAD_KW = "load_kw"                    # kW


class SensorReading(BaseModel):
    """One (sensor, metric, value) observation inside a telemetry frame."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str = Field(..., min_length=1)
    metric: str = Field(..., min_length=1, description="Canonical metric name, e.g. 'bearing_temp'.")
    value: float
    unit: str = Field(default="", description="Engineering unit, e.g. 'C', 'mm/s', 'bar'.")
    quality: float = Field(default=1.0, ge=0.0, le=1.0, description="Signal quality 0..1 from the edge gateway.")


class TelemetryReading(BaseModel):
    """One timestamped multi-sensor frame for a single asset/component."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    asset_id: str = Field(..., min_length=1)
    component_id: Optional[str] = None
    timestamp: datetime
    readings: List[SensorReading] = Field(..., min_length=1)
    operating_mode: OperatingMode = OperatingMode.RUNNING
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TelemetryBatch(BaseModel):
    """Batch envelope produced by Member 2's edge/stream gateway."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(..., min_length=1)
    produced_at: datetime
    readings: List[TelemetryReading] = Field(..., min_length=1)
