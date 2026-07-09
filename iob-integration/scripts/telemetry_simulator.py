"""
Mock telemetry simulator - pushes data to WS gateway.
This container is intentionally stoppable live to test Stage 3 degraded detection.
"""
import time
import random
import os
import json

print("Telemetry simulator started (mock) - will stream dummy data. Stop with 'docker compose stop telemetry-simulator'")

# In real setup this would push to Kafka or directly to WS.
# For Phase 5A demo, we just keep alive and log.

try:
    while True:
        payload = {
            "asset_id": "machine07",
            "vibration": round(random.uniform(2.0, 4.5), 2),
            "temperature": round(random.uniform(70, 95), 2),
            "timestamp": time.time(),
            "simulator_live": True
        }
        print(f"[SIM] {json.dumps(payload)}")
        time.sleep(2)
except KeyboardInterrupt:
    print("Simulator stopped")
