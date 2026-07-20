# Phase 4 — snippet to FIX the existing /contracts handler in ui_router.py
# =========================================================================
# This is the "Fix /api/v1/ai/ui/contracts" step for teams who already have a
# hand-written @router.get("/contracts") in app/ai_service/integration/ui_router.py.
#
# 1. Find your current `/contracts` handler in ui_router.py.
# 2. DELETE its body (the part that builds a hardcoded/hand-maintained manifest
#    — that stale list is the source of the drift).
# 3. Replace it with the version below. Keep your existing `router` object and
#    any response_model / decorators your frontend relies on.
#
# The manifest now regenerates from the live route table on every call, so it
# can never fall out of sync with what the app actually serves.

from fastapi import Request

from .contracts_manifest import build_contract_manifest  # add this import at top


@router.get("/contracts")  # keep your existing decorator args (response_model, etc.)
async def get_contracts(request: Request) -> dict:
    return build_contract_manifest(request.app)


# Optional but recommended — expose the live drift report so ops/CI can poll it:
from .contracts_manifest import validate_manifest_against_openapi  # noqa: E402


@router.get("/contracts/validate")
async def validate_contracts(request: Request) -> dict:
    return validate_manifest_against_openapi(request.app)
