"""Phase 1 — Shared middleware/dependency layer (Section 2.1 / 3.2).

``APIRouter`` does not support ``add_middleware`` the way a full ``FastAPI``/
``Starlette`` application does — middleware can only be attached to an ASGI
app (or the app-level router). To get a middleware-like guarantee that is
scoped to *only* the ``/api/v1/ai/ui/*`` router (and any other router that
opts in), this module ships a custom :class:`fastapi.routing.APIRoute`
subclass, :class:`UIContractRoute`, installed as the router's
``route_class``:

.. code-block:: python

    from app.ai_service.middleware import UIContractRoute

    ui_router = APIRouter(
        prefix="/ui",
        route_class=UIContractRoute,   # <-- Phase 1 wiring
        ...,
    )

Every request that matches a route on that router is transparently
wrapped so that, regardless of what the handler itself does:

1. The inbound ``X-Request-ID`` (or ``X-Correlation-ID``) header is read
   early and a UUID4 is generated as a fallback when absent.
2. That id is stashed on ``request.state.request_id`` so handlers/response
   helpers can read it back consistently (see :func:`get_request_id`).
3. On the way out, the resolved id is echoed on the ``x-request-id``
   response header and ``x-ai-module`` is injected — even for handlers
   that build a raw ``Response``/``StreamingResponse`` and forget to set
   the headers themselves.

This complements (does not replace) :func:`app.ai_service.responses.
create_ui_response`, which already sets these headers explicitly on the
``JSONResponse`` it builds. The route class is the safety net that
guarantees the contract holds even for hand-rolled responses (e.g. NDJSON
streams, 204 preflight responses, or a future endpoint that forgets to
call the helper).
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable, Optional, Type

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Header contract constants (Section 1.2)
# ---------------------------------------------------------------------------
REQUEST_ID_HEADER = "x-request-id"
CORRELATION_ID_HEADER = "x-correlation-id"
AI_MODULE_HEADER = "x-ai-module"

#: Fallback module identifier used when a router/response doesn't specify
#: its own. Individual sub-routers (e.g. Phase 11's UI router) should pass
#: an explicit, more specific value (e.g. ``"phase-11-ui"``) to
#: :func:`app.ai_service.responses.create_ui_response` /
#: :func:`make_ui_contract_route`.
DEFAULT_AI_MODULE = "ai-ui-common"


def resolve_request_id(request: Request) -> str:
    """Extract the tracking id from the inbound request, generating a fallback.

    Resolution order:

    1. ``X-Request-ID`` request header (exact echo requirement, Section 1.2).
    2. ``X-Correlation-ID`` request header (legacy/alternate clients).
    3. A freshly generated UUID4.
    """

    return (
        request.headers.get(REQUEST_ID_HEADER)
        or request.headers.get(CORRELATION_ID_HEADER)
        or str(uuid.uuid4())
    )


def get_request_id(request: Request) -> str:
    """Return the request id resolved for this request.

    Prefers the value already stashed on ``request.state`` by
    :class:`UIContractRoute` (or any earlier middleware) so the same id is
    used consistently across the whole request lifecycle; falls back to
    resolving it fresh (e.g. for routers that don't use
    :class:`UIContractRoute`).
    """

    cached = getattr(request.state, "request_id", None)
    if cached:
        return cached
    return resolve_request_id(request)


def make_ui_contract_route(*, module: str = DEFAULT_AI_MODULE) -> Type[APIRoute]:
    """Build a :class:`UIContractRoute` subclass bound to a fixed module name.

    Use this when a sub-router wants its own ``x-ai-module`` value baked
    into the route class instead of relying on the default:

    .. code-block:: python

        ui_router = APIRouter(
            prefix="/ui",
            route_class=make_ui_contract_route(module="phase-11-ui"),
        )
    """

    class _BoundUIContractRoute(UIContractRoute):
        default_module = module

    _BoundUIContractRoute.__name__ = "UIContractRoute"
    _BoundUIContractRoute.__qualname__ = "UIContractRoute"
    return _BoundUIContractRoute


class UIContractRoute(APIRoute):
    """``APIRoute`` subclass enforcing the Phase 1 header contract.

    Installed as a router's ``route_class`` this acts as router-scoped
    middleware:

    * Resolves/generates the request id **before** the handler runs and
      exposes it via ``request.state.request_id``.
    * After the handler returns (success *or* exception bubbling up to
      Starlette's error handling), ensures the response carries
      ``x-request-id`` (echoed exactly) and ``x-ai-module`` headers.

    Subclass and override :attr:`default_module` (or use
    :func:`make_ui_contract_route`) to customize the module identifier per
    router without touching this shared implementation.
    """

    default_module: str = DEFAULT_AI_MODULE

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request_id = resolve_request_id(request)
            # Expose to downstream handlers / dependencies / response helpers.
            request.state.request_id = request_id

            try:
                response = await original_route_handler(request)
            except RequestValidationError as exc:
                # Route-level wrapping sees validation failures before the
                # application-level exception handler. Preserve their 422
                # semantics while returning the same UI envelope.
                from app.ai_service.responses import create_ui_response
                response = create_ui_response(
                    request_id=request_id,
                    success=False,
                    error={
                        "code": "VALIDATION_ERROR",
                        "message": "Request validation failed. Check payload shape, field types, and allowed values.",
                        "details": exc.errors(),
                    },
                    module=self.default_module,
                    status_code=422,
                )
            except Exception:  # noqa: BLE001
                # Dependency resolution runs before a handler body and can
                # therefore fail outside a route's own try/except.  Keep the
                # UI boundary deterministic even in that case.
                logger.exception("Unhandled UI route exception path=%s", request.url.path)
                from app.ai_service.responses import create_ui_response
                response = create_ui_response(
                    request_id=request_id,
                    success=False,
                    error={
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected UI service error occurred.",
                        "details": None,
                    },
                    module=self.default_module,
                    status_code=500,
                )

            # Belt & suspenders: guarantee the contract headers exist even
            # if the handler built its own Response/StreamingResponse and
            # forgot to set them (e.g. hand-rolled NDJSON streams).
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers.setdefault(AI_MODULE_HEADER, self.default_module)
            return response

        return custom_route_handler
