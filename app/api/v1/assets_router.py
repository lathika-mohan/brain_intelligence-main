from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException

router = APIRouter(prefix="/assets", tags=["assets"])

_assets = [
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

@router.get("")
async def list_assets(token: str = Depends(_extract_token)):
    return {
        "success": True,
        "data": _assets,
        "assets": _assets,
        "total": len(_assets),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/{asset_id}")
async def get_asset(asset_id: str, token: str = Depends(_extract_token)):
    for a in _assets:
        if a["id"] == asset_id or a["asset_id"] == asset_id:
            return {"success": True, "data": a}
    raise HTTPException(status_code=404, detail="Asset not found")
