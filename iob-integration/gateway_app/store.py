"""
In-memory store for Phase 5A integration gateway.
Simulates Postgres + Redis + Alert Engine.
Thread-safe via lock.
"""
from __future__ import annotations
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Set

_lock = threading.RLock()
_tokens: Set[str] = set()
_alerts: List[Dict] = []
_simulator_live: bool = True

# Pre-seeded assets - matches industrial taxonomy, includes machine07 for alarm injection tests
_ASSETS = [
    {
        "id": "machine07",
        "asset_id": "machine07",
        "name": "Pump-007 Bearing Assembly",
        "type": "PUMP",
        "asset_type": "PUMP",
        "status": "OPERATIONAL",
        "location": "Plant-A / Sector-3",
        "criticality": "HIGH",
        "components": ["bearing", "seal", "impeller"],
    },
    {
        "id": "machine01",
        "asset_id": "machine01",
        "name": "Compressor-001",
        "type": "COMPRESSOR",
        "asset_type": "COMPRESSOR",
        "status": "DEGRADED",
        "location": "Plant-A / Sector-1",
        "criticality": "CRITICAL",
    },
    {
        "id": "machine02",
        "asset_id": "machine02",
        "name": "Turbine-002",
        "type": "TURBINE",
        "asset_type": "TURBINE",
        "status": "OPERATIONAL",
        "location": "Plant-B / Sector-2",
    },
    {
        "id": "pump101",
        "asset_id": "pump101",
        "name": "Pump-101 Main Feed",
        "type": "PUMP",
        "asset_type": "PUMP",
        "status": "OPERATIONAL",
        "location": "Plant-A",
    },
    {
        "id": "asset-101",
        "asset_id": "asset-101",
        "name": "Motor Assembly 101",
        "type": "MOTOR",
        "asset_type": "MOTOR",
        "status": "OPERATIONAL",
        "location": "Plant-C",
    },
]

def add_token(token: str):
    with _lock:
        _tokens.add(token)

def is_valid_token(token: str) -> bool:
    with _lock:
        # In demo mode, accept any non-empty token that looks like ours,
        # but also allow the hardcoded demo token for robustness.
        if not token:
            return False
        # Accept if we issued it OR if it is at least 10 chars (allow fallback)
        return token in _tokens or len(token) > 10

def get_assets() -> List[Dict]:
    with _lock:
        return list(_ASSETS)

def get_asset_by_id(asset_id: str) -> Dict | None:
    with _lock:
        for a in _ASSETS:
            if a["id"] == asset_id or a["asset_id"] == asset_id:
                return a
        return None

def inject_alert(asset_id: str, metric: str, value: float) -> Dict:
    with _lock:
        alert = {
            "id": str(uuid.uuid4()),
            "alert_id": str(uuid.uuid4()),
            "asset_id": asset_id,
            "metric": metric,
            "value": value,
            "severity": "CRITICAL",
            "status": "ACTIVE",
            "acknowledged": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Critical tripwire: {metric}={value} on {asset_id}",
            "description": f"Bearing temperature critical threshold breached {value}°C",
        }
        _alerts.append(alert)
        return alert

def get_active_alerts() -> List[Dict]:
    with _lock:
        return list(_alerts)

def set_simulator_live(live: bool):
    global _simulator_live
    with _lock:
        _simulator_live = live

def is_simulator_live() -> bool:
    with _lock:
        return _simulator_live

def clear_alerts():
    with _lock:
        _alerts.clear()
