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


class OllamaClient(AIClient):
    """Ollama client with native JSON mode support."""

    def __init__(
        self,
        model: str = "gemma3:4b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def backend_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        user_message: str,
        options: CompletionOptions | None = None,
    ) -> CompletionResult:
        """Complete a message using Ollama's native JSON mode."""
        if options is None:
            options = CompletionOptions()

        start_time = time.monotonic()

        try:
            payload: dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": options.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,  # Required for JSON mode
                "options": {
                    "temperature": options.temperature,
                    "num_predict": options.max_tokens,
                },
            }

            # Add native JSON mode if requested
            if options.json_mode:
                payload["format"] = "json"

            # Add extra options
            if options.extra:
                payload["options"].update(options.extra)

            # [FAZ3-METRIC]
            _t0 = time.perf_counter()
            try:
                response = await self._client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=options.timeout,
                )
                response.raise_for_status()
                duration = time.perf_counter() - _t0
                try:
                    get_metrics().record_ai_request(
                        backend="ollama",
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
                        backend="ollama",
                        model=self._model,
                        duration_seconds=duration,
                        status="error",
                    )
                except Exception:
                    pass
                raise

            raw_response = response.json()
            content = raw_response.get("message", {}).get("content", "")

            # Calculate tokens (Ollama provides prompt_eval_count + eval_count)
            tokens_used = raw_response.get("prompt_eval_count", 0) + raw_response.get(
                "eval_count", 0
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Parse JSON if requested
            parsed = None
            if options.json_mode and content:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Failed to parse JSON response from Ollama",
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
                "Ollama completion failed",
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
        """Check if Ollama is available."""
        try:
            response = await self._client.get(
                f"{self._base_url}/api/tags",
                timeout=10.0,
            )
            return bool(response.status_code == 200)
        except Exception as e:
            logger.warning("Ollama health check failed", error=str(e))
            return False

    async def __aenter__(self) -> OllamaClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self._client.aclose()
