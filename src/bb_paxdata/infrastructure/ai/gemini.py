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


class GeminiClient(AIClient):
    """Gemini client with responseMimeType JSON support."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def backend_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        user_message: str,
        options: CompletionOptions | None = None,
    ) -> CompletionResult:
        """Complete a message using Gemini with responseMimeType JSON."""
        if options is None:
            options = CompletionOptions()

        start_time = time.monotonic()

        try:
            # Build contents array
            contents = [{"role": "user", "parts": [{"text": user_message}]}]

            # Build generation config
            generation_config: dict[str, Any] = {
                "temperature": options.temperature,
                "maxOutputTokens": options.max_tokens,
            }

            # Add JSON mode if requested
            if options.json_mode:
                generation_config["responseMimeType"] = "application/json"

            # Add extra options
            if options.extra:
                generation_config.update(options.extra)

            # Build system instruction
            system_instruction = None
            if options.system_prompt:
                system_instruction = {"parts": [{"text": options.system_prompt}]}

            payload = {
                "contents": contents,
                "generationConfig": generation_config,
            }

            if system_instruction:
                payload["systemInstruction"] = system_instruction

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"

            # [FAZ3-METRIC]
            _t0 = time.perf_counter()
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    timeout=options.timeout,
                )
                response.raise_for_status()
                duration = time.perf_counter() - _t0
                try:
                    get_metrics().record_ai_request(
                        backend="gemini",
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
                        backend="gemini",
                        model=self._model,
                        duration_seconds=duration,
                        status="error",
                    )
                except Exception:
                    pass
                raise

            raw_response = response.json()

            # Extract content from response
            candidates = raw_response.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in response")

            content = (
                candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            )

            # Calculate tokens (Gemini provides usage metadata)
            usage_metadata = raw_response.get("usageMetadata", {})
            tokens_used = (
                usage_metadata.get("promptTokenCount", 0)
                + usage_metadata.get("candidatesTokenCount", 0)
                + usage_metadata.get("totalTokenCount", 0)
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Parse JSON if requested
            parsed = None
            if options.json_mode and content:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON response from Gemini",
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
                "Gemini completion failed",
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
        """Check if Gemini API is available."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"

            payload = {
                "contents": [{"role": "user", "parts": [{"text": "test"}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1,
                },
            }

            response = await self._client.post(
                url,
                json=payload,
                timeout=10.0,
            )
            return bool(response.status_code == 200)
        except Exception as e:
            logger.warning("Gemini health check failed", error=str(e))
            return False

    async def __aenter__(self) -> GeminiClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.aclose()
