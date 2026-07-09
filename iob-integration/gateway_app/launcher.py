"""
Launcher for Phase 5A - starts both Gateway (8000) and WebSocket (8001) concurrently.
Usage:
  python -m gateway_app.launcher
  or
  python gateway_app/launcher.py
"""
from __future__ import annotations
import os
import sys
import time
import subprocess
import signal

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Ensure parent is in path
    sys.path.insert(0, os.path.dirname(base_dir))

    gateway_cmd = [
        sys.executable, "-m", "uvicorn",
        "gateway_app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info",
    ]
    ws_cmd = [
        sys.executable, "-m", "uvicorn",
        "gateway_app.ws_server:app",
        "--host", "0.0.0.0",
        "--port", "8001",
        "--log-level", "info",
    ]

    print("\033[92m🚀 Starting Phase 5A Integration Stack\033[0m")
    print(f"  Gateway: {gateway_cmd}")
    print(f"  WS:      {ws_cmd}")

    # Try to run both in same directory context
    env = os.environ.copy()
    # Set AI_SERVICE_URL if running with AI platform on 8002 internally
    env.setdefault("AI_SERVICE_URL", "http://localhost:8002")

    try:
        gw_proc = subprocess.Popen(gateway_cmd, cwd=os.path.dirname(base_dir), env=env)
        ws_proc = subprocess.Popen(ws_cmd, cwd=os.path.dirname(base_dir), env=env)

        print("\n\033[94mGateway running at http://localhost:8000  |  WS at ws://localhost:8001\033[0m")
        print("Press Ctrl+C to stop both.\n")

        def handle_sigint(sig, frame):
            print("\nStopping...")
            gw_proc.terminate()
            ws_proc.terminate()
            gw_proc.wait(timeout=5)
            ws_proc.wait(timeout=5)
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_sigint)
        signal.signal(signal.SIGTERM, handle_sigint)

        # Wait for both
        while True:
            # Check if any died
            gw_ret = gw_proc.poll()
            ws_ret = ws_proc.poll()
            if gw_ret is not None:
                print(f"Gateway exited with {gw_ret}, restarting in 2s...")
                time.sleep(2)
                gw_proc = subprocess.Popen(gateway_cmd, cwd=os.path.dirname(base_dir), env=env)
            if ws_ret is not None:
                print(f"WS server exited with {ws_ret}, restarting in 2s...")
                time.sleep(2)
                ws_proc = subprocess.Popen(ws_cmd, cwd=os.path.dirname(base_dir), env=env)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nInterrupted, cleaning up...")
        try:
            gw_proc.terminate()
            ws_proc.terminate()
        except:
            pass

if __name__ == "__main__":
    main()
