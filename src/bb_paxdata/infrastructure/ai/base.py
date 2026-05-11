from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompletionOptions:
    """Options for AI completion requests."""

    system_prompt: str = ""
    temperature: float = 0.1
    max_tokens: int = 1024
    json_mode: bool = (
        True  # All backends require JSON mode - monolithic code v5.0 feature
    )
    timeout: float = 120.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResult:
    """Result of an AI completion request."""

    content: str
    parsed: dict[str, Any] | None  # JSON parse success = dict, failure = None
    backend: str
    model: str
    tokens_used: int
    latency_ms: int
    success: bool
    error: str | None = None
    raw_response: dict[str, Any] | None = None  # Debug purposes


class AIClient(ABC):
    """Abstract base class for AI backend clients."""

    @property
    @abstractmethod
    def backend_name(self) -> str: ...  # "local" | "api" | "gemini" | "groq"

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def complete(
        self,
        user_message: str,
        options: CompletionOptions | None = None,
    ) -> CompletionResult:
        """
        Complete a user message.
        Does not throw exceptions on error.
        Always returns CompletionResult; success=False on failure.
        """

    @abstractmethod
    async def health_check(self) -> bool: ...

    async def complete_batch(
        self,
        messages: list[str],
        options: CompletionOptions | None = None,
    ) -> list[CompletionResult]:
        """
        Default: sequential individual calls.
        Subclasses can override for batching.
        """
        results = []
        for msg in messages:
            results.append(await self.complete(msg, options))
        return results
