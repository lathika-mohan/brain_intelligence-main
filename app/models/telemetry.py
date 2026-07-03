"""Telemetry ingestion contract — Phase 0"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, Optional

class TelemetryIngestRequest(BaseModel):
    asset_id: str
    timestamp: datetime
    metrics: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None
    schema_version: str = "1.0.0"
