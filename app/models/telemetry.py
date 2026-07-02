"""
Telemetry ingestion contract — CONSUMED FROM Member 2 (PLC/SCADA team).

This is the frozen shape the AI platform expects live sensor data to
arrive in, whether pulled from a Kafka topic, MQTT bridge, or REST push
from the SCADA historian. Predictive Maintenance inference schemas
(`predictive.py`) build directly on top of `TelemetryReading`.

Contract owner note: any change to this schema MUST be renegotiated with
Member 2 — it is the upstream/downstream boundary documented in Phase 0
Section 4 (Team Coordination Boundaries).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import utc_now


class SensorUnit(str, Enum):
    CELSIUS = "C"
    FAHRENHEIT = "F"
    PSI = "psi"
    BAR = "bar"
    RPM = "rpm"
    HERTZ = "Hz"
    VOLT = "V"
    AMPERE = "A"
    MM_PER_S = "mm/s"  # vibration velocity
    G_FORCE = "g"       # vibration acceleration
    PERCENT = "%"
    LITER_PER_MIN = "L/min"
    UNKNOWN = "unknown"


class SensorReading(BaseModel):
    """A single sensor's instantaneous reading within a telemetry frame."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str = Field(..., description="Unique sensor identifier, matches Phase 1 ontology :Sensor.id.")
    metric: str = Field(..., description="Metric name, e.g. 'vibration_x', 'bearing_temp'.")
    value: float
    unit: SensorUnit = SensorUnit.UNKNOWN
    quality: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Signal quality / confidence from the SCADA layer."
    )


class TelemetryReading(BaseModel):
    """
    A single telemetry frame for one asset, as produced by the ingestion
    layer (Member 2). Schema version is pinned via `schema_version` so
    breaking upstream changes are explicit and negotiable.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0")
    asset_id: str = Field(..., description="Matches Phase 1 ontology :Asset.id.")
    component_id: Optional[str] = Field(
        default=None, description="Matches Phase 1 ontology :Component.id, if reading is component-scoped."
    )
    timestamp: datetime = Field(default_factory=utc_now)
    readings: List[SensorReading] = Field(..., min_length=1)
    operating_mode: Optional[str] = Field(
        default=None, description="Operational context, e.g. 'RUNNING', 'STARTUP', 'IDLE'."
    )
    metadata: Dict[str, str] = Field(default_factory=dict)

    @field_validator("readings")
    @classmethod
    def _non_empty_readings(cls, v: List[SensorReading]) -> List[SensorReading]:
        if not v:
            raise ValueError("readings must contain at least one SensorReading")
        return v


class TelemetryBatch(BaseModel):
    """Batched ingestion payload (e.g. one Kafka message with N frames)."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str
    produced_at: datetime = Field(default_factory=utc_now)
    readings: List[TelemetryReading] = Field(..., max_length=500)
