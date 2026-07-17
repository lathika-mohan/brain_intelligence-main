from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

from app.orchestration.state import AgentError, AgentState

logger = logging.getLogger(__name__)
T = TypeVar("T")


def ensure_state(value: AgentState | dict[str, Any]) -> AgentState:
    if isinstance(value, AgentState):
        return value
    return AgentState.model_validate(value)


def export_state(state: AgentState) -> dict[str, Any]:
    return state.model_dump(mode="python")


async def with_retries(
    *,
    state: AgentState,
    agent: str,
    operation: str,
    call: Callable[[], Awaitable[T]],
    fallback: Callable[[Exception], T] | None = None,
    max_retries: int = 2,
    base_delay_seconds: float = 0.05,
) -> T | None:
    """Exception boundary and deterministic retry ring for agent tool calls."""
    attempt = 0
    last_exc: Exception | None = None
    key = f"{agent}.{operation}"
    while attempt <= max_retries:
        try:
            if attempt:
                state.retries[key] = attempt
            return await call()
        except Exception as exc:  # noqa: BLE001 - boundary must catch tool failures
            last_exc = exc
            logger.warning("%s failed on attempt %d/%d: %s", key, attempt + 1, max_retries + 1, exc)
            if attempt >= max_retries:
                break
            attempt += 1
            await asyncio.sleep(base_delay_seconds * attempt)
    assert last_exc is not None
    state.errors.append(
        AgentError(
            agent=agent,
            error_type=type(last_exc).__name__,
            message=str(last_exc),
            retry_count=max_retries,
            recoverable=fallback is not None,
        )
    )
    if fallback is not None:
        return fallback(last_exc)
    return None
