from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def _extract_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth")
    token = authorization.split()[1] if "Bearer" in authorization else authorization
    if len(token) < 5:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

@router.get("/overview")
async def overview(token: str = Depends(_extract_token)):
    return {
        "success": True,
        "data": {
            "total_assets": 5,
            "operational_assets": 4,
            "critical_alerts": 0,
            "simulator_live": True,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    }
