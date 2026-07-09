from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Dict
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/alerts", tags=["alerts"])

_alerts: List[Dict] = []

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

@router.get("/active")
async def active_alerts(token: str = Depends(_extract_token)):
    return {
        "success": True,
        "data": _alerts,
        "alerts": _alerts,
        "total": len(_alerts),
    }

@router.post("/acknowledge/{alert_id}")
async def ack_alert(alert_id: str, token: str = Depends(_extract_token)):
    for a in _alerts:
        if a["id"] == alert_id or a.get("alert_id") == alert_id:
            a["acknowledged"] = True
            a["status"] = "ACKNOWLEDGED"
            return {"success": True, "data": a}
    raise HTTPException(status_code=404, detail="Alert not found")

# Also expose injection route under same prefix for convenience (alternative path)
@router.post("/inject")
async def inject_alert_alt(body: AlarmInject, token: str = Depends(_extract_token)):
    alert = {
        "id": str(uuid.uuid4()),
        "asset_id": body.asset_id,
        "metric": body.metric,
        "value": body.value,
        "severity": "CRITICAL",
        "status": "ACTIVE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _alerts.append(alert)
    return {"success": True, "data": alert}
