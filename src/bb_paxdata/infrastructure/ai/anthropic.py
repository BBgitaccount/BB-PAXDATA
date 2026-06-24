from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

from bb_paxdata.infrastructure.ai.base import (
    AIClient,
    CompletionOptions,
    CompletionResult,
)
from bb_paxdata.infrastructure.ai.circuit_breaker import (
    CircuitBreakerConfig,
    with_circuit_breaker,
)

logger = structlog.get_logger(__name__)


class AnthropicClient(AIClient):
    """Anthropic client with JSON prefill technique."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def backend_name(self) -> str:
        return "api"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        user_message: str,
        options: CompletionOptions | None = None,
    ) -> CompletionResult:
        """Complete a message using Anthropic with JSON prefill technique."""
        if options is None:
            options = CompletionOptions()

        async def _do_complete() -> CompletionResult:
            start_time = time.monotonic()

            try:
                # Build messages array
                messages = [{"role": "user", "content": user_message}]

                # Add JSON prefill technique if JSON mode is requested
                if options.json_mode:
                    # Add instruction to system prompt
                    system_prompt = (
                        options.system_prompt
                        + "\n\nRespond ONLY with valid JSON. No markdown."
                    )

                    # Add prefill message to force JSON response
                    messages.append({"role": "assistant", "content": "{"})
                else:
                    system_prompt = options.system_prompt

                payload: dict[str, Any] = {
                    "model": self._model,
                    "max_tokens": options.max_tokens,
                    "temperature": options.temperature,
                    "messages": messages,
                    "system": system_prompt,
                }

                # Add extra options
                if options.extra:
                    payload.update(options.extra)

                headers = {
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }

                from bb_paxdata.infrastructure.ai.base import ai_call_instrumented

                async with ai_call_instrumented(
                    "anthropic", self._model, logger
                ) as record:
                    response = await self._client.post(
                        "https://api.anthropic.com/v1/messages",
                        json=payload,
                        headers=headers,
                        timeout=options.timeout,
                    )
                    response.raise_for_status()
                    raw_response = response.json()
                    usage = raw_response.get("usage", {})
                    record.prompt_tokens = usage.get("input_tokens", 0)
                    record.completion_tokens = usage.get("output_tokens", 0)

                content = raw_response.get("content", [{}])[0].get("text", "")

                # Remove the prefill "{" we added - response should start with "{"
                if options.json_mode:
                    stripped = content.lstrip()
                    if stripped.startswith("{"):
                        # Prefill was included in response, remove it
                        content = stripped[1:]
                    else:
                        # Model didn't see the prefill - log warning but continue
                        logger.warning(
                            "Anthropic response missing prefill '{'",
                            content_start=content[:50],
                        )
                        content = stripped

                tokens_used = record.prompt_tokens + record.completion_tokens
                latency_ms = int((time.monotonic() - start_time) * 1000)

                # Parse JSON if requested
                parsed = None
                if options.json_mode and content:
                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Failed to parse JSON response from Anthropic",
                            content=content[:200],
                            error=str(e),
                        )

                return CompletionResult(
                    content=content,
                    parsed=parsed,
                    backend=self.backend_name,
                    model=self._model,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                    success=True,
                    raw_response=raw_response,
                    prompt_tokens=record.prompt_tokens,
                    completion_tokens=record.completion_tokens,
                )

            except Exception as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(
                    "Anthropic completion failed",
                    model=self._model,
                    error=str(e),
                    latency_ms=latency_ms,
                )

                return CompletionResult(
                    content="",
                    parsed=None,
                    backend=self.backend_name,
                    model=self._model,
                    tokens_used=0,
                    latency_ms=latency_ms,
                    success=False,
                    error=str(e),
                )

        # Use circuit breaker for protection
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            open_timeout_seconds=60,
            timeout_seconds=options.timeout or 120,
            fallback_enabled=False,
        )

        fallback_result = CompletionResult(
            content="",
            parsed=None,
            backend=self.backend_name,
            model=self._model,
            tokens_used=0,
            latency_ms=0,
            success=False,
            error="Circuit breaker open - service temporarily unavailable",
        )

        return await with_circuit_breaker(
            service_name="anthropic",
            func=_do_complete,
            fallback_response=fallback_result,
            config=config,
        )

    async def health_check(self) -> bool:
        """Check if Anthropic API is available."""
        try:
            headers = {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }

            payload = {
                "model": self._model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "test"}],
            }

            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning("Anthropic health check failed", error=str(e))
            return False

    async def __aenter__(self) -> AnthropicClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.aclose()
