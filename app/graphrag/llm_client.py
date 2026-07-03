"""
Phase 5 — LLM Client Interface
================================
Provides a unified interface for calling LLMs (OpenAI, Anthropic, or local
models) for the GraphRAG synthesis step.

The client is designed to be swappable — production deployments can use
OpenAI's GPT-4 / GPT-4o, while development and testing can use a mock
that returns deterministic responses for reproducible tests.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol for LLM providers
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMProvider(Protocol):
    """Interface that all LLM providers must implement."""

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Generate a completion.

        Returns:
            dict with keys:
              - text: str — the generated text
              - model: str — model identifier
              - usage: dict — token usage info
              - latency_ms: float — generation time
        """
        ...


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider:
    """OpenAI GPT-4 / GPT-4o provider using the official client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                kwargs: Dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise RuntimeError("openai package not installed — run: pip install openai")
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        client = self._get_client()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.choices[0].message.content or ""
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            latency = (time.perf_counter() - t0) * 1000.0
            return {
                "text": text,
                "model": self.model,
                "usage": usage,
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            logger.exception("OpenAI completion failed: %s", e)
            raise


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class AnthropicProvider:
    """Anthropic Claude provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("anthropic package not installed")
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        client = self._get_client()

        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            latency = (time.perf_counter() - t0) * 1000.0
            return {
                "text": text,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            logger.exception("Anthropic completion failed: %s", e)
            raise


# ---------------------------------------------------------------------------
# Mock provider (for tests and offline development)
# ---------------------------------------------------------------------------

class MockLLMProvider:
    """
    Deterministic mock provider for testing.
    Generates a response that includes proper citation tags referencing
    the context provided.
    """

    def __init__(self, model: str = "mock-llm-v1") -> None:
        self.model = model

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # Extract citation tags from the system prompt to generate grounded response
        import re

        tags = re.findall(r"\[Source #(\d+)\]", system_prompt)
        unique_tags = list(dict.fromkeys(tags))[:5]  # deduplicate, cap at 5

        if unique_tags:
            citation_refs = " ".join(f"[Source #{t}]" for t in unique_tags[:3])
            text = (
                f"Based on the retrieved context, the analysis indicates the following:\n\n"
                f"The operational data confirms the reported anomaly pattern {citation_refs}. "
                f"Structural relationships in the knowledge graph corroborate the vector-retrieved "
                f"documentation {citation_refs}.\n\n"
                f"Recommended action: Execute the referenced SOP procedure with standard safety "
                f"precautions. Monitor telemetry for confirmation of resolution."
            )
        else:
            text = (
                "The retrieval pipeline did not return sufficient context to generate a "
                "grounded response. Please verify the query parameters and ensure relevant "
                "documents have been ingested into the knowledge base."
            )

        latency = (time.perf_counter() - t0) * 1000.0
        return {
            "text": text,
            "model": self.model,
            "usage": {"prompt_tokens": len(system_prompt.split()), "completion_tokens": len(text.split()), "total_tokens": 0},
            "latency_ms": round(latency, 2),
        }


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_provider_instance: Optional[LLMProvider] = None


def get_llm_provider(
    provider_name: Optional[str] = None,
    **kwargs: Any,
) -> LLMProvider:
    """
    Get or create the configured LLM provider.

    Priority:
      1. Explicit provider_name argument
      2. LLM_PROVIDER environment variable
      3. Auto-detect: openai if OPENAI_API_KEY set, else mock
    """
    global _provider_instance
    if _provider_instance is not None and provider_name is None:
        return _provider_instance

    name = provider_name or os.getenv("LLM_PROVIDER", "").lower()

    if name == "openai" or (not name and os.getenv("OPENAI_API_KEY")):
        provider = OpenAIProvider(**kwargs)
    elif name == "anthropic" or (not name and os.getenv("ANTHROPIC_API_KEY")):
        provider = AnthropicProvider(**kwargs)
    else:
        logger.info("Using MockLLMProvider (no LLM API key configured)")
        provider = MockLLMProvider(**kwargs)

    if provider_name:
        _provider_instance = provider
    return provider


def reset_llm_provider() -> None:
    """Reset the singleton — useful for testing."""
    global _provider_instance
    _provider_instance = None
