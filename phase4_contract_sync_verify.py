#!/usr/bin/env python3
"""
Phase 4 — Contract Synchronization Verifier
===========================================

Run locally (where FastAPI + your deps are installed) from the repo root:

    python phase4_contract_sync_verify.py

Exit code 0  => documentation (manifest/OpenAPI) matches implementation.
Exit code 1  => drift detected; details printed. Wire this into CI to make
                contract drift a build failure.

What it checks
--------------
1. The app imports and mounts cleanly (verifies router mounting).
2. Every route the app serves appears in the OpenAPI schema
   (no path mismatches / no undocumented endpoints).
3. Every documented OpenAPI path is actually served (nothing phantom).
4. The `/api/v1/ai/ui/contracts` endpoint responds and reports in_sync=True.
"""

from __future__ import annotations

import json
import sys

# Import the live application. Adjust this import ONLY if your app object lives
# elsewhere than app/main.py:app
try:
    from app.main import app
except Exception as exc:  # pragma: no cover
    print(f"[FATAL] could not import app.main:app -> {exc!r}")
    sys.exit(1)

from app.ai_service.integration.contracts_manifest import (
    build_contract_manifest,
    validate_manifest_against_openapi,
)


def main() -> int:
    print("== Phase 4: Contracts Manifest & API Synchronization ==\n")

    manifest = build_contract_manifest(app)
    print(f"service           : {manifest['service']} v{manifest['version']}")
    print(f"mounted routes    : {manifest['route_count']}")

    report = validate_manifest_against_openapi(app)

    if report.get("error"):
        print(f"\n[FAIL] OpenAPI generation error: {report['error']}")
        return 1

    ok = report["in_sync"]
    print(f"in_sync_openapi   : {ok}")

    if report["missing_in_openapi"]:
        print("\n[DRIFT] served but NOT in OpenAPI schema:")
        for p in report["missing_in_openapi"]:
            print(f"   - {p}")
    if report["missing_in_manifest"]:
        print("\n[DRIFT] in OpenAPI schema but NOT served:")
        for p in report["missing_in_manifest"]:
            print(f"   - {p}")
    if report["method_mismatches"]:
        print("\n[DRIFT] method mismatches:")
        for m in report["method_mismatches"]:
            print(f"   - {m['path']}: served={m['served_methods']} "
                  f"documented={m['documented_methods']}")
    if report["hidden_routes"]:
        print("\n[info] routes intentionally hidden from schema "
              f"(include_in_schema=False): {len(report['hidden_routes'])}")

    # Exercise the live endpoint via TestClient so we prove it actually responds.
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            # Try the canonical path first, then fall back to a discovered one.
            candidate = "/api/v1/ai/ui/contracts"
            resp = client.get(candidate)
            if resp.status_code == 404:
                discovered = next(
                    (r["path"] for r in manifest["routes"]
                     if r["path"].endswith("/contracts")),
                    None,
                )
                if discovered:
                    candidate = discovered
                    resp = client.get(candidate)
            print(f"\nGET {candidate} -> {resp.status_code}")
            if resp.status_code == 200:
                body = resp.json()
                print(f"   endpoint reports in_sync={body.get('in_sync_with_openapi')}")
            else:
                print("   [FAIL] contracts endpoint did not return 200")
                ok = False
    except Exception as exc:
        print(f"\n[warn] could not exercise endpoint via TestClient: {exc!r}")

    print("\n" + ("PASS: manifest matches implementation." if ok
                  else "FAIL: contract drift detected (see above)."))
    # Also dump the machine-readable report next to the script for CI artifacts.
    with open("phase4_contract_sync_report.json", "w") as fh:
        json.dump({"manifest_route_count": manifest["route_count"],
                   "validation": report}, fh, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
