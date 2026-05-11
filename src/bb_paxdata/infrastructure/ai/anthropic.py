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
from bb_paxdata.infrastructure.observability.metrics import get_metrics

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

            # [FAZ3-METRIC]
            _t0 = time.perf_counter()
            try:
                response = await self._client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers,
                    timeout=options.timeout,
                )
                response.raise_for_status()
                duration = time.perf_counter() - _t0
                try:
                    get_metrics().record_ai_request(
                        backend="anthropic",
                        model=self._model,
                        duration_seconds=duration,
                        status="success",
                    )
                except Exception:
                    pass
            except Exception:
                duration = time.perf_counter() - _t0
                try:
                    get_metrics().record_ai_request(
                        backend="anthropic",
                        model=self._model,
                        duration_seconds=duration,
                        status="error",
                    )
                except Exception:
                    pass
                raise

            raw_response = response.json()
            content = raw_response.get("content", [{}])[0].get("text", "")

            # Remove the prefill "{" if we added it
            if options.json_mode and content.startswith("{"):
                content = "{" + content

            # Calculate tokens
            usage = raw_response.get("usage", {})
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

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
            return bool(response.status_code == 200)
        except Exception as e:
            logger.warning("Anthropic health check failed", error=str(e))
            return False

    async def __aenter__(self) -> AnthropicClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.aclose()
