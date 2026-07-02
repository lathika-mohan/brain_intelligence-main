"""
Telemetry ingestion router — CONSUMES the upstream contract from Member 2
(PLC/SCADA team). Validates incoming batches against `TelemetryBatch`
(frozen in `app.models.telemetry`) and acknowledges receipt.

Phase 0 scope: validation + acknowledgement only. Actual persistence to
the feature store / streaming to inference is a later-phase concern.
"""
from __future__ import annotations

from fastapi import APIRouter, status

from app.models.common import APIResponse
from app.models.telemetry import TelemetryBatch

router = APIRouter(prefix="/ingestion", tags=["telemetry-ingestion"])


@router.post(
    "/telemetry",
    response_model=APIResponse[dict],
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_telemetry(batch: TelemetryBatch) -> APIResponse[dict]:
    """
    Validates a batch against the frozen upstream contract and
    acknowledges receipt. Returns counts only — no downstream side
    effects in Phase 0.
    """
    return APIResponse[dict](
        data={
            "batch_id": batch.batch_id,
            "accepted_readings": len(batch.readings),
            "schema_version": batch.readings[0].schema_version if batch.readings else None,
        }
    )
