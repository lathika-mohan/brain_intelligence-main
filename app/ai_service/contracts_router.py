"""
Phase 4 — Contracts router (additive).

Exposes the self-describing contract manifest. Mount it under the SAME prefix as
your existing UI router so the final paths resolve to:

    GET /api/v1/ai/ui/contracts           -> full manifest
    GET /api/v1/ai/ui/contracts/routes    -> flat list of mounted paths
    GET /api/v1/ai/ui/contracts/validate  -> live drift report vs OpenAPI

Wiring (pick ONE):

  A) Preferred — fold into your existing UI router. In
     ``app/ai_service/integration/ui_router.py``:

         from .contracts_router import router as contracts_router
         router.include_router(contracts_router)   # `router` is your existing UI APIRouter

     If your ui_router already defines a `/contracts` handler, delete that old
     handler first so there is exactly one — that removal is the "fix" for the
     stale endpoint.

  B) Alternative — include directly where the UI router is mounted
     (``app/ai_service/main_router.py``), using whatever prefix currently yields
     `/ui` (e.g. prefix="/ui"):

         from .integration.contracts_router import router as contracts_router
         main_router.include_router(contracts_router, prefix="/ui")

Either way, no prefix is set on this router itself, so it inherits `/ui` from the
parent and produces `/api/v1/ai/ui/contracts`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from .contracts_manifest import (
    build_contract_manifest,
    list_mounted_paths,
    validate_manifest_against_openapi,
)

router = APIRouter(tags=["contracts"])


@router.get("/contracts", summary="Full self-describing contract manifest")
async def get_contracts(request: Request) -> dict:
    """Return the live contract manifest derived from the mounted route table."""
    return build_contract_manifest(request.app)


@router.get("/contracts/routes", summary="Flat list of fully mounted paths")
async def get_contract_routes(request: Request) -> dict:
    """Return every fully mounted path with its methods (prefixes resolved)."""
    routes = list_mounted_paths(request.app)
    return {"route_count": len(routes), "routes": routes}


@router.get("/contracts/validate", summary="Manifest vs OpenAPI drift report")
async def validate_contracts(request: Request) -> dict:
    """Return a structured report of any drift between served routes and OpenAPI."""
    return validate_manifest_against_openapi(request.app)
