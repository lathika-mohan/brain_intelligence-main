#!/bin/bash
# Phase 5A Local Runner - No Docker required
# Starts gateway (8000) + WS (8001) and runs orchestrator

set -e

echo "🚀 Phase 5A Local Integration - No Docker"

# Kill any previous
pkill -f "gateway_app.main" || true
pkill -f "gateway_app.ws_server" || true
sleep 1

# Install deps if missing
pip install fastapi uvicorn httpx websocket-client websockets pydantic pydantic-settings -q

# Start gateway
echo "Starting Gateway on 8000..."
python -m uvicorn iob-integration.gateway_app.main:app --host 127.0.0.1 --port 8000 --log-level warning &
GW_PID=$!

echo "Starting WS on 8001..."
python -m uvicorn iob-integration.gateway_app.ws_server:app --host 127.0.0.1 --port 8001 --log-level warning &
WS_PID=$!

# Wait for health
for i in {1..10}; do
  if curl -s http://127.0.0.1:8000/health > /dev/null; then
    echo "Gateway ready"
    break
  fi
  sleep 1
done

for i in {1..10}; do
  if curl -s http://127.0.0.1:8001/health > /dev/null; then
    echo "WS ready"
    break
  fi
  sleep 1
done

echo ""
echo "Running orchestrator..."
python phase5_integration_orchestrator.py --gateway http://127.0.0.1:8000 --ws-url ws://127.0.0.1:8001

echo ""
echo "Cleaning up..."
kill $GW_PID || true
kill $WS_PID || true

echo "Done."
