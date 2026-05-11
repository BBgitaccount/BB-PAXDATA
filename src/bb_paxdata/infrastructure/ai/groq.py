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

logger = structlog.get_logger(__name__)


class GroqClient(AIClient):
    """Groq client with json_object response format."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def backend_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        user_message: str,
        options: CompletionOptions | None = None,
    ) -> CompletionResult:
        """Complete a message using Groq with json_object response format."""
        if options is None:
            options = CompletionOptions()

        start_time = time.monotonic()

        try:
            # Build messages array
            messages = []
            if options.system_prompt:
                messages.append({"role": "system", "content": options.system_prompt})
            messages.append({"role": "user", "content": user_message})

            payload: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": options.temperature,
                "max_tokens": options.max_tokens,
            }

            # Add JSON mode if requested
            if options.json_mode:
                payload["response_format"] = {"type": "json_object"}

            # Add extra options
            if options.extra:
                payload.update(options.extra)

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            }

            response = await self._client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=options.timeout,
            )
            response.raise_for_status()

            raw_response = response.json()

            # Extract content from response
            choices = raw_response.get("choices", [])
            if not choices:
                raise ValueError("No choices in response")

            content = choices[0].get("message", {}).get("content", "")

            # Calculate tokens
            usage = raw_response.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Parse JSON if requested
            parsed = None
            if options.json_mode and content:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON response from Groq",
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
                "Groq completion failed",
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
        """Check if Groq API is available."""
        try:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            }

            payload = {
                "model": self._model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1,
            }

            response = await self._client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            return bool(response.status_code == 200)
        except Exception as e:
            logger.warning("Groq health check failed", error=str(e))
            return False

    async def __aenter__(self) -> GroqClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.aclose()
