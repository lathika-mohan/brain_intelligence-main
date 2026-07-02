"""
Shared primitives, enums, and response envelopes.

`APIResponse[T]` intentionally mirrors the frontend's strict TypeScript
contract already frozen in `src/types/index.ts` (see
INTEGRATION_NOTES_SECTION11.md in the repo root):

    export interface APIResponse<T> {
      success: boolean;
      data: T;
      error?: { code: string; message: string; details?: unknown };
    }

Every AI-platform endpoint response body is wrapped in this envelope so
Member 4 (Frontend) can bind to it with zero shape translation, and
Member 1 (Platform Backend) can proxy it unmodified through the
enterprise gateway.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class AssetStatus(str, Enum):
    """Mirrors frontend `Asset.status` union exactly."""

    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"


class AlertSeverity(str, Enum):
    """Mirrors frontend `Alert.severity` union exactly."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class AssetType(str, Enum):
    PUMP = "PUMP"
    MOTOR = "MOTOR"
    COMPRESSOR = "COMPRESSOR"
    TURBINE = "TURBINE"
    CONVEYOR = "CONVEYOR"
    VALVE = "VALVE"
    SENSOR_NODE = "SENSOR_NODE"
    GENERIC = "GENERIC"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Machine-readable error code, e.g. 'GRAPH_TIMEOUT'.")
    message: str = Field(..., description="Human-readable error message.")
    details: Optional[dict] = Field(default=None, description="Optional structured error context.")


class APIResponse(BaseModel, Generic[T]):
    """Standard response envelope used by every AI-platform endpoint."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    request_id: str = Field(default_factory=new_id)
    generated_at: datetime = Field(default_factory=utc_now)


class PaginationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class TimeRange(BaseModel):
    """Inclusive UTC time bounds used across telemetry / graph / vector filters."""

    model_config = ConfigDict(extra="forbid")

    start: Optional[datetime] = Field(default=None, description="Inclusive start (UTC).")
    end: Optional[datetime] = Field(default=None, description="Inclusive end (UTC).")
