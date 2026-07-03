"""
Shared Phase 0 platform contracts consumed across the IOB AI Intelligence
Platform backend.

These are the frozen, cross-cutting primitives that every domain module
(ontology, telemetry, predictive, graphrag, xai) and the FastAPI routers
depend on. This module intentionally contains **no** Neo4j/Cypher logic,
**no** parser code, and **no** business rules — it is shared vocabulary only.

Reconstructed in Phase 2 to restore the package import graph after the
initial repository snapshot shipped without it (see PHASE2 notes).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp (ISO-8601 compatible)."""
    return datetime.now(timezone.utc)


class AssetType(str, Enum):
    """Phase 0 canonical physical/logical asset taxonomy.

    Mirrors the taxonomy surfaced to the frontend in section 11 of the
    TypeScript contract and reused by the Phase 1 industrial ontology.
    """

    PUMP = "PUMP"
    MOTOR = "MOTOR"
    COMPRESSOR = "COMPRESSOR"
    TURBINE = "TURBINE"
    FAN = "FAN"
    BLOWER = "BLOWER"
    MIXER = "MIXER"
    AGITATOR = "AGITATOR"
    TANK = "TANK"
    VESSEL = "VESSEL"
    HEAT_EXCHANGER = "HEAT_EXCHANGER"
    VALVE = "VALVE"
    PIPING = "PIPING"
    CONVEYOR = "CONVEYOR"
    MCC = "MCC"
    TRANSFORMER = "TRANSFORMER"
    VFD = "VFD"
    PLC = "PLC"
    GENERIC = "GENERIC"


class AssetStatus(str, Enum):
    """Operational status of an asset (Phase 0 frozen enum)."""

    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"


class TimeRange(BaseModel):
    """Closed time window used to bound retrieval (e.g. incident/SOP revision)."""

    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime
    label: Optional[str] = Field(default=None, description="Optional human label, e.g. 'last_30d'.")


class APIResponse(BaseModel, Generic[T]):
    """Shared response envelope that wraps every API payload.

    The frontend's ``APIResponse<T>`` TypeScript contract (section 11)
    mirrors this shape verbatim. ``APIResponse[GraphRagQueryResponse](data=...)``
    is the canonical construction pattern used by the routers.
    """

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: T
    error: Optional[str] = None
    request_id: Optional[str] = Field(default=None, description="Correlation id for tracing.")
    generated_at: datetime = Field(default_factory=utc_now)
