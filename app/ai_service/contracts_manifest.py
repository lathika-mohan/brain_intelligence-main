"""
Phase 4 — Contracts Manifest & API Synchronization
==================================================

Single source of truth for the application's self-description.

Design principle (why this prevents contract drift):
    The manifest is NOT a hand-maintained list of paths. It is *derived* from
    the live FastAPI application's route table (``app.routes``) every time it is
    requested. Because the manifest is generated from the same object that serves
    the requests, the documented contract and the implemented contract can never
    disagree. "Add an endpoint" and "the manifest updates" become the same action.

Public API
----------
build_contract_manifest(app)            -> dict   full self-description payload
list_mounted_paths(app)                 -> list   flat [{path, methods, name}]
validate_manifest_against_openapi(app)  -> dict   drift report (in_sync + diffs)
assert_in_sync(app)                     -> None   raises RuntimeError on drift

This module has no external dependencies beyond FastAPI/Starlette (already in
your requirements) and is safe to import from any router.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    # FastAPI wraps user endpoints in APIRoute; Starlette provides Mount / Route.
    from fastapi.routing import APIRoute
except Exception:  # pragma: no cover - FastAPI always present in this project
    APIRoute = tuple()  # type: ignore

from starlette.routing import Mount, Route, WebSocketRoute

# Methods that FastAPI/Starlette add automatically and that are not part of the
# semantic contract. We strip them so the manifest lists only intentional verbs.
_IMPLICIT_METHODS = {"HEAD", "OPTIONS"}


def _visible_methods(methods: Any) -> List[str]:
    """Return the sorted, contract-relevant HTTP verbs for a route."""
    if not methods:
        return []
    return sorted(m for m in methods if m not in _IMPLICIT_METHODS)


def _iter_api_routes(app) -> List[Any]:
    """
    Flatten the application's route tree into concrete HTTP routes.

    FastAPI bakes every ``include_router(prefix=...)`` into the child route's
    ``.path``, so ``route.path`` is already the *full mounted path*. We still walk
    Mount() sub-applications recursively in case any sub-app is mounted manually.
    """
    collected: List[Any] = []

    def _walk(routes, prefix: str = "") -> None:
        for route in routes:
            if isinstance(route, Mount):
                # A manually mounted sub-application (e.g. a nested FastAPI app).
                sub = getattr(route.app, "routes", None)
                if sub is not None:
                    _walk(sub, prefix + route.path.rstrip("/"))
                continue
            if isinstance(route, (Route, WebSocketRoute)):
                # Clone-ish view carrying the fully-qualified path.
                route._full_path = prefix + route.path  # type: ignore[attr-defined]
                collected.append(route)

    _walk(app.routes)
    return collected


def list_mounted_paths(app) -> List[Dict[str, Any]]:
    """
    Report every fully mounted path the application actually serves.

    This is the answer to "Report full mounted paths" — prefixes from
    ``include_router`` and any manual ``Mount`` are already resolved.
    """
    entries: List[Dict[str, Any]] = []
    for route in _iter_api_routes(app):
        full_path = getattr(route, "_full_path", route.path)
        methods = _visible_methods(getattr(route, "methods", None))
        # WebSocket routes have no .methods; label them explicitly.
        if isinstance(route, WebSocketRoute):
            methods = ["WEBSOCKET"]
        entries.append(
            {
                "path": full_path,
                "methods": methods,
                "name": getattr(route, "name", None),
                "tags": list(getattr(route, "tags", []) or []),
                "summary": getattr(route, "summary", None),
                "include_in_schema": getattr(route, "include_in_schema", True),
            }
        )
    # Deterministic ordering => stable diffs / snapshots.
    entries.sort(key=lambda e: (e["path"], ",".join(e["methods"])))
    return entries


def build_contract_manifest(app) -> Dict[str, Any]:
    """
    Build the full contract manifest served at ``/api/v1/ai/ui/contracts``.

    The payload is intentionally self-describing so downstream teams (Frontend,
    Platform Backend) can integrate against it without reading source.
    """
    routes = list_mounted_paths(app)
    validation = validate_manifest_against_openapi(app)

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in routes:
        key = entry["tags"][0] if entry["tags"] else "untagged"
        grouped.setdefault(key, []).append(entry)

    return {
        "service": getattr(app, "title", "ai-platform"),
        "version": getattr(app, "version", "0.0.0"),
        "openapi_version": getattr(app, "openapi_version", "3.1.0"),
        "route_count": len(routes),
        "generated_from": "live_fastapi_route_table",
        "in_sync_with_openapi": validation["in_sync"],
        "routes": routes,
        "routes_by_tag": grouped,
        "validation": validation,
    }


def validate_manifest_against_openapi(app) -> Dict[str, Any]:
    """
    Cross-check the derived manifest against FastAPI's generated OpenAPI schema.

    Returns a structured drift report:
        in_sync              -> bool
        missing_in_openapi   -> paths served but absent from the schema
        missing_in_manifest  -> paths in the schema but not served (should be empty)
        method_mismatches    -> paths where served verbs != documented verbs
    Only schema-visible routes (include_in_schema=True) are compared; hidden
    routes are reported separately so they never register as false drift.
    """
    manifest = list_mounted_paths(app)

    # Served, schema-visible verbs keyed by path.
    served: Dict[str, set] = {}
    hidden: List[str] = []
    for entry in manifest:
        if not entry["include_in_schema"]:
            hidden.append(entry["path"])
            continue
        verbs = {m for m in entry["methods"] if m != "WEBSOCKET"}
        if verbs:
            served.setdefault(entry["path"], set()).update(verbs)

    try:
        openapi = app.openapi()
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "in_sync": False,
            "error": f"app.openapi() failed: {exc!r}",
            "missing_in_openapi": [],
            "missing_in_manifest": [],
            "method_mismatches": [],
            "hidden_routes": sorted(hidden),
        }

    documented: Dict[str, set] = {}
    for path, item in (openapi.get("paths") or {}).items():
        verbs = {m.upper() for m in item.keys() if m.upper() not in _IMPLICIT_METHODS}
        documented[path] = verbs

    served_paths = set(served)
    documented_paths = set(documented)

    missing_in_openapi = sorted(served_paths - documented_paths)
    missing_in_manifest = sorted(documented_paths - served_paths)

    method_mismatches = []
    for path in sorted(served_paths & documented_paths):
        if served[path] != documented[path]:
            method_mismatches.append(
                {
                    "path": path,
                    "served_methods": sorted(served[path]),
                    "documented_methods": sorted(documented[path]),
                }
            )

    in_sync = not (missing_in_openapi or missing_in_manifest or method_mismatches)

    return {
        "in_sync": in_sync,
        "missing_in_openapi": missing_in_openapi,
        "missing_in_manifest": missing_in_manifest,
        "method_mismatches": method_mismatches,
        "hidden_routes": sorted(hidden),
    }


def assert_in_sync(app) -> None:
    """Raise ``RuntimeError`` if the manifest and OpenAPI schema disagree.

    Call this from a startup hook or CI test to fail fast on contract drift.
    """
    report = validate_manifest_against_openapi(app)
    if not report["in_sync"]:
        raise RuntimeError(f"Contract manifest is out of sync: {report}")
