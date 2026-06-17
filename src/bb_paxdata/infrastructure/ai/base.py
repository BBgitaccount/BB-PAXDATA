from __future__ import annotations

import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog

from bb_paxdata.infrastructure.observability.metrics import get_metrics


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
    prompt_tokens: int = 0
    completion_tokens: int = 0


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

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Asynchronously generate a text completion from a prompt."""
        options = CompletionOptions(
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )
        result = await self.complete(prompt, options)
        return result.content

    @abstractmethod
    async def health_check(self) -> bool: ...

    async def aclose(self) -> None:
        """Close client resource connections."""
        if hasattr(self, "_client") and hasattr(self._client, "aclose"):
            await self._client.aclose()

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


class AICallRecord:
    """Mutable container to record token counts and status of an AI call."""

    def __init__(self) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.status: str = "success"
        self.error: str | None = None


@asynccontextmanager
async def ai_call_instrumented(
    backend: str,
    model: str,
    logger: structlog.BoundLogger,
):
    """
    Async context manager to instrument AI backend calls.
    Measures duration/latency, logs detailed metrics, and records to Prometheus.
    """
    record = AICallRecord()
    start_time = time.monotonic()
    t0 = time.perf_counter()
    try:
        yield record
    except Exception as e:
        record.status = "error"
        record.error = str(e)
        raise
    finally:
        duration_seconds = time.perf_counter() - t0
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Record to Prometheus (duration and status)
        try:
            get_metrics().record_ai_request(
                backend=backend,
                model=model,
                duration_seconds=duration_seconds,
                status=record.status,
            )
        except Exception:
            pass

        # Record tokens to Prometheus
        if record.status == "success":
            try:
                get_metrics().record_ai_tokens(
                    backend=backend,
                    model=model,
                    prompt_tokens=record.prompt_tokens,
                    completion_tokens=record.completion_tokens,
                    latency_ms=latency_ms,
                )
            except Exception:
                pass

        total_tokens = record.prompt_tokens + record.completion_tokens
        tokens_per_second = 0.0
        if latency_ms > 0 and total_tokens > 0:
            tokens_per_second = round(total_tokens / (latency_ms / 1000.0), 1)

        log_fields: dict[str, Any] = {
            "backend": backend,
            "model": model,
            "status": record.status,
            "latency_ms": latency_ms,
            "prompt_tokens": record.prompt_tokens,
            "completion_tokens": record.completion_tokens,
            "tokens_used": total_tokens,
        }
        if record.status == "success":
            log_fields["tokens_per_second"] = tokens_per_second
            logger.info("ai_call_complete", **log_fields)
        else:
            if record.error:
                log_fields["error"] = record.error
            logger.warning("ai_call_complete", **log_fields)
