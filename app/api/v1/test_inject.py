from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import List, Dict

# Shared alerts list - import from alerts router if possible
try:
    from .alerts import _alerts as shared_alerts
except ImportError:
    shared_alerts: List[Dict] = []

router = APIRouter(prefix="/test", tags=["test"])

class AlarmInject(BaseModel):
    asset_id: str
    metric: str
    value: float
    model_config = {"extra": "allow"}

def _extract_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth")
    token = authorization.split()[1] if "Bearer" in authorization else authorization
    if len(token) < 5:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

@router.post("/inject-alarm")
async def inject_alarm(body: AlarmInject, token: str = Depends(_extract_token)):
    alert = {
        "id": str(uuid.uuid4()),
        "alert_id": str(uuid.uuid4()),
        "asset_id": body.asset_id,
        "metric": body.metric,
        "value": body.value,
        "severity": "CRITICAL",
        "status": "ACTIVE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Critical: {body.metric}={body.value}",
    }
    # Add to shared list
    try:
        from .alerts import _alerts
        _alerts.append(alert)
    except ImportError:
        shared_alerts.append(alert)
    return {
        "success": True,
        "data": alert,
        "message": "Critical alarm state successfully registered",
        "request_id": str(uuid.uuid4()),
    }
