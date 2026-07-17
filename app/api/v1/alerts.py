from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, Request
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
    active = [a for a in _alerts if a.get("status") not in {"RESOLVED", "CLOSED"}]
    return {
        "success": True,
        "data": active,
        "alerts": active,
        "total": len(active),
    }

@router.post("/acknowledge/{alert_id}")
async def ack_alert(alert_id: str, token: str = Depends(_extract_token)):
    for a in _alerts:
        if a["id"] == alert_id or a.get("alert_id") == alert_id:
            a["acknowledged"] = True
            a["status"] = "ACKNOWLEDGED"
            return {"success": True, "data": a}
    raise HTTPException(status_code=404, detail="Alert not found")

@router.post("/resolve")
async def resolve_alerts(request: Request, token: str = Depends(_extract_token)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    alert_id = body.get("alert_id") or body.get("id")
    asset_id = body.get("asset_id")
    resolved = []
    now = datetime.now(timezone.utc).isoformat()
    for alert in _alerts:
        matches_id = not alert_id or alert.get("id") == alert_id or alert.get("alert_id") == alert_id
        matches_asset = not asset_id or alert.get("asset_id") == asset_id
        if matches_id and matches_asset and alert.get("status") not in {"RESOLVED", "CLOSED"}:
            alert["status"] = "RESOLVED"
            alert["resolved"] = True
            alert["resolved_at"] = now
            resolved.append(alert)
    active = [a for a in _alerts if a.get("status") not in {"RESOLVED", "CLOSED"}]
    return {
        "success": True,
        "status": "RESOLVED",
        "data": resolved,
        "resolved_alerts": resolved,
        "resolved_count": len(resolved),
        "active_count": len(active),
    }

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
