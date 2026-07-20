#!/bin/bash
cd /home/user/brain_intelligence-main
echo "=== Phase 0 Script Start ==="

# 1. Create stabilization branch
git checkout -b phase-0/baseline-inventory 2>&1
echo "Branch created: $(git branch --show-current)"

# 2. Install core deps
pip install fastapi uvicorn pydantic pydantic-settings python-dotenv httpx pytest pytest-asyncio orjson 2>&1 | tail -5
echo "=== Dependencies installed ==="

# 3. Boot verification
python -c "
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
res = client.get('/openapi.json')
routes = [f'{r.methods} {r.path}' for r in app.routes]

print(f'=== BOOT VERIFICATION ===')
print(f'App Boot Status: HTTP {res.status_code}')
print(f'Total Registered Routes: {len(routes)} (Expected: 49)')
for r in routes:
    print(f'  {r}')
" 2>&1
echo "=== Boot check done ==="

# 4. UI Contract test
python -m pytest tests/test_phase11_ui_router_contract.py -v 2>&1
echo "=== UI Contract done ==="

# 5. Remaining test suites
python -m pytest tests/test_phase5_byte_identical_relay.py -v 2>&1
echo "=== Phase5 done ==="

python -m pytest tests/test_phase6_predictive.py tests/test_phase7_xai.py tests/test_phase8_decision.py tests/test_phase9_orchestration.py tests/test_phase10_ai_service.py tests/test_phase12_ml_models.py -q 2>&1
echo "=== Core AI suites done ==="

echo "=== Phase 0 Script Complete ==="
