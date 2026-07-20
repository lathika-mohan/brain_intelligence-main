#!/usr/bin/env python3
"""
Phase 7 — Final Verification & Cleanup
======================================

Confirms the implementation is complete AND within scope. This is a *checker*,
not a sign-off: per the Phase 7 rule, pytest results are the only acceptance
criterion, so this script writes NO completion certificate. It prints findings to
stdout and exits non-zero if a hard check fails (scope violation), so CI can gate
on it, while explicitly deferring "done/accepted" to your pytest run.

Usage (from repo root, in your venv):

    # 1) Scope guard — prove protected modules were NOT modified by this work.
    python phase7_final_verification.py --base <ref-before-your-changes>
        # e.g. --base origin/main   or   --base <commit-sha>   or   --base <tag>

    # 2) Live contract checks (requires the app to import):
    python phase7_final_verification.py --live

    # both:
    python phase7_final_verification.py --base origin/main --live

Hard check (fails the run):
    * No modifications to protected paths.

Report-only checks (surface issues; acceptance still = pytest):
    * required endpoints exist
    * headers present/correct
    * response envelopes consistent
    * contracts manifest accurate (in sync with OpenAPI)
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# Protected paths — the checklist forbids any modification here. Both spellings
# of the graphrag dir are covered (checklist wrote graph_rag; tree uses graphrag).
PROTECTED_PATTERNS = [
    "app/predictive/",
    "app/graph_rag/",
    "app/graphrag/",
    "app/decision/",
    "app/orchestration/service.py",
    "app/models/",
]


def is_protected(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    for pat in PROTECTED_PATTERNS:
        if pat.endswith("/"):
            if p.startswith(pat):
                return True
        elif p == pat:
            return True
    return False


def changed_files(base_ref: str) -> list:
    """Return files changed between base_ref and the working tree (via git)."""
    cmd = ["git", "diff", "--name-only", base_ref]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`git diff {base_ref}` failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def run_scope_guard(base_ref: str) -> bool:
    print(f"\n== Scope guard (protected modules untouched vs {base_ref}) ==")
    try:
        files = changed_files(base_ref)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        return False

    violations = sorted(f for f in files if is_protected(f))
    print(f"changed files vs base : {len(files)}")
    if violations:
        print("[FAIL] protected paths were modified:")
        for v in violations:
            print(f"   - {v}")
        return False
    print("[OK] no protected path was modified.")
    # Also show, for transparency, which non-protected files changed.
    if files:
        print("changed (allowed) files:")
        for f in files:
            print(f"   . {f}")
    return True


# ---------------------------------------------------------------------------
# Envelope conformance (pure; unit-tested offline)
# ---------------------------------------------------------------------------

def envelope_is_consistent(body: object, required_keys: set) -> tuple[bool, str]:
    """Check a JSON response body conforms to the shared response envelope.

    required_keys is derived from app/models/common.py (APIResponse) at runtime
    when available; a sensible default is used otherwise.
    """
    if not isinstance(body, dict):
        return False, f"body is {type(body).__name__}, expected object envelope"
    missing = required_keys - set(body.keys())
    if missing:
        return False, f"missing envelope keys: {sorted(missing)}"
    return True, "envelope ok"


def _discover_envelope_keys() -> set:
    """Best-effort: read the APIResponse model's required fields."""
    try:
        from app.models.common import APIResponse  # type: ignore
        fields = getattr(APIResponse, "model_fields", None) or getattr(
            APIResponse, "__fields__", {}
        )
        # required = fields without a default
        req = set()
        for name, f in fields.items():
            is_required = getattr(f, "is_required", None)
            if callable(is_required):
                if is_required():
                    req.add(name)
            elif getattr(f, "required", False):
                req.add(name)
        return req or set(fields.keys())
    except Exception:
        # Fall back to the commonly used envelope shape; adjust if yours differs.
        return {"success", "data"}


def run_live_checks() -> bool:
    print("\n== Live contract checks ==")
    try:
        from app.main import app  # noqa
        from fastapi.testclient import TestClient
    except Exception as exc:
        print(f"[skip] could not import app.main:app / TestClient ({exc!r}).")
        print("       run this inside the app venv to enable live checks.")
        return True  # report-only; do not fail the run on environment gaps

    try:
        from app.ai_service.integration.contracts_manifest import (
            build_contract_manifest,
            validate_manifest_against_openapi,
        )
        have_manifest = True
    except Exception:
        have_manifest = False

    ok_report = True
    with TestClient(app) as client:
        # 1) required endpoints exist + manifest accurate
        if have_manifest:
            manifest = build_contract_manifest(app)
            print(f"mounted routes        : {manifest['route_count']}")
            report = validate_manifest_against_openapi(app)
            print(f"manifest in sync      : {report['in_sync']}")
            if not report["in_sync"]:
                ok_report = False
                for k in ("missing_in_openapi", "missing_in_manifest", "method_mismatches"):
                    if report.get(k):
                        print(f"   {k}: {report[k]}")
        else:
            print("[note] contracts_manifest not importable; skipping manifest accuracy.")

        # 2) contracts endpoint responds + headers + envelope
        candidate = "/api/v1/ai/ui/contracts"
        resp = client.get(candidate)
        print(f"GET {candidate} -> {resp.status_code}")
        ctype = resp.headers.get("content-type", "")
        print(f"content-type          : {ctype or '(none)'}")
        if "application/json" not in ctype:
            print("[warn] contracts response is not application/json")

        # 3) envelope consistency on a representative endpoint
        env_keys = _discover_envelope_keys()
        print(f"envelope required keys: {sorted(env_keys)}")
        # Pick a GET endpoint likely to return the standard envelope; health is typical.
        for path in ("/api/v1/health", "/api/v1/ai/ui/contracts"):
            r = client.get(path)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith(
                "application/json"
            ):
                consistent, why = envelope_is_consistent(r.json(), env_keys)
                print(f"envelope @ {path}: {'ok' if consistent else 'INCONSISTENT'} ({why})")

    return ok_report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="git ref before your changes (enables scope guard)")
    ap.add_argument("--live", action="store_true", help="run live contract checks")
    args = ap.parse_args()

    if not args.base and not args.live:
        ap.error("provide --base <ref> and/or --live")

    hard_ok = True
    if args.base:
        hard_ok = run_scope_guard(args.base) and hard_ok
    if args.live:
        run_live_checks()  # report-only

    print("\n" + "-" * 60)
    if args.base and not hard_ok:
        print("SCOPE VIOLATION ❌  (a protected module was modified)")
    else:
        print("scope guard clean." if args.base else "scope guard not run (no --base).")
    print("Acceptance is decided by pytest, not by this script "
          "(see phase6_regression_runner.py). No certificate written by design.")
    return 0 if hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
