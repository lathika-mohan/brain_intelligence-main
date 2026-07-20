"""Phase 1 — Common Infrastructure & Response Contract: the envelope model.

This module defines :class:`UIAPIResponseEnvelope`, the **single, frozen**
top-level shape every ``/api/v1/ai/ui/*`` endpoint must return:

.. code-block:: json

    {
      "requestId": "9b116ef2-36ec-4429-9b0d-14f6ed8dbf37",
      "generatedAt": "2026-07-19T16:20:00Z",
      "success": true,
      "error": null,
      "data": { ... }
    }

Design notes
------------
* ``requestId`` always mirrors the inbound ``X-Request-ID`` header (or a
  generated UUID4 fallback) — see :mod:`app.ai_service.common.middleware`.
* ``generatedAt`` is always an ISO-8601 **UTC** timestamp rendered with a
  literal ``Z`` suffix (never ``+00:00``), matching the contract example
  in the spec (``"2026-07-19T16:20:00Z"``).
* ``error`` is ``null`` on success and a structured
  :class:`UIAPIErrorPayload` on failure — never a bare string. When
  ``success`` is ``False``, ``data`` is forced to ``null`` per Section 1.1.
* This model intentionally does **not** replace the richer, already
  shipped :class:`app.ai_service.integration.schemas.ui_schemas.UIAPIResponse`
  generic envelope. It is the *common, backend-typed* mirror used by the
  Phase 1 middleware/helper layer so every submodule — including future
  ones that never import ``ui_schemas`` — gets the exact same contract
  guarantees. :func:`app.ai_service.common.responses.create_ui_response`
  is the recommended way to build one; most callers never need to
  instantiate this class directly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer

T = TypeVar("T")


def utc_now_iso() -> str:
    """Return the current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``.

    Always uses a literal ``Z`` suffix (never ``+00:00``) and truncates to
    whole seconds so the value matches the contract example exactly, e.g.
    ``"2026-07-19T16:20:00Z"``.
    """

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


class UIAPIErrorPayload(BaseModel):
    """Section 1.1 ``error`` object shape.

    ``{"code": "ERROR_CODE", "message": "Human readable reason"}``
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Machine-readable error code, e.g. 'AI_DEPENDENCY_UNAVAILABLE'.")
    message: str = Field(..., description="Human-readable explanation safe to surface to the UI.")
    details: Optional[Any] = Field(
        default=None,
        description="Optional structured details (e.g. field-level validation errors).",
    )


class UIAPIResponseEnvelope(BaseModel, Generic[T]):
    """The frozen top-level ``UIAPIResponse`` envelope (Section 1.1).

    Exactly these fields, no more, no less:

    * ``requestId``   (str)                    — echoes ``X-Request-ID``.
    * ``generatedAt`` (str, ISO-8601 UTC)       — response generation time.
    * ``success``     (bool)
    * ``error``       (UIAPIErrorPayload | null)
    * ``data``        (T | null)
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId")
    generated_at: str = Field(alias="generatedAt", default_factory=utc_now_iso)
    success: bool
    error: Optional[UIAPIErrorPayload] = None
    data: Optional[T] = None

    @field_serializer("generated_at")
    def _serialize_generated_at(self, value: Any) -> str:  # noqa: D401
        # Accept either a pre-formatted string or a datetime for convenience.
        if isinstance(value, datetime):
            value = value.astimezone(timezone.utc).replace(microsecond=0)
            return value.isoformat().replace("+00:00", "Z")
        return str(value)
