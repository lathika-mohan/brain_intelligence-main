from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ASSETS = [
    {"id": "machine07", "asset_id": "machine07", "name": "Pump-007", "type": "PUMP", "status": "OPERATIONAL", "location": "Plant-A"},
    {"id": "machine01", "asset_id": "machine01", "name": "Compressor-001", "type": "COMPRESSOR", "status": "DEGRADED", "location": "Plant-A"},
    {"id": "machine02", "asset_id": "machine02", "name": "Turbine-002", "type": "TURBINE", "status": "OPERATIONAL", "location": "Plant-B"},
    {"id": "pump101", "asset_id": "pump101", "name": "Pump-101", "type": "PUMP", "status": "OPERATIONAL", "location": "Plant-A"},
    {"id": "asset-101", "asset_id": "asset-101", "name": "Motor 101", "type": "MOTOR", "status": "OPERATIONAL", "location": "Plant-C"},
]

def _extract_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth")
    token = authorization.split()[1] if "Bearer" in authorization else authorization
    if len(token) < 5:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

@router.get("/overview")
async def overview(token: str = Depends(_extract_token)):
    nominal_assets = [a for a in _ASSETS if a.get("status") == "OPERATIONAL"]
    degraded_assets = [a for a in _ASSETS if a.get("status") == "DEGRADED"]
    return {
        "success": True,
        "data": {
            "total_assets": len(_ASSETS),
            "operational_assets": len(nominal_assets),
            "critical_alerts": 0,
            "simulator_live": True,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "assets": _ASSETS,
            "nominal_assets": nominal_assets,
            "degraded_asset_rows": degraded_assets,
        },
        "assets": _ASSETS,
        "nominal_assets": nominal_assets,
    }
