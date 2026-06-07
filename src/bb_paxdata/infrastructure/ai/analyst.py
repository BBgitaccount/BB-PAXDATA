# DEPRECATED: Bu dosya artik aktif degil.
# requests kutuphanesi burada hala mevcut ama aktif kod yolunda kullanilmiyor.
# Tum AI cagrilari infrastructure/ai/anthropic.py vb. uzerinden yapılıyor.
"""AI Analyst service for diplomatic discourse analysis.

This service provides AI-powered analysis capabilities by interfacing with
various AI backends (Ollama, Anthropic, Gemini, Groq). It implements
structured output generation, batch processing, and robust error recovery.

DEPRECATED: The old sync implementation using requests.Session has been replaced
with an async adapter that wraps modern AIClient implementations (anthropic, groq, gemini).
This file now serves as a compatibility layer between the old interface and the new async clients.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from bb_paxdata.infrastructure.ai.recovery import (  # noqa: F401
    RecoveryEngine,
    RecoveryLevel,
    RecoveryResult,
)


class BackendType(Enum):
    """Supported AI backend types."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    DEEPSEEK = "deepseek"


@dataclass
class AIRequest:
    """AI request configuration."""

    text: str
    context: str | None = None
    temperature: float = 0.3
    max_tokens: int = 1000
    model: str | None = None


@dataclass
class AIResponse:
    """AI response data."""

    content: dict[str, Any]
    model_used: str
    backend_used: BackendType
    processing_time: float
    tokens_used: int | None = None
    cached: bool = False


class ModernAIAnalystAdapter:
    """Adapter that wraps modern AIClient implementations with the old AIAnalyst interface.

    This adapter provides backward compatibility while using async httpx-based clients
    instead of the old sync requests.Session-based implementation.
    """

    def __init__(
        self,
        default_backend: BackendType = BackendType.OLLAMA,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the adapter with modern AI clients.

        Args:
            default_backend: Default backend to use
            api_key: API key for cloud backends
            base_url: Base URL for local backends
        """
        self.default_backend = default_backend
        self.api_key = api_key
        self.base_url = base_url
        self.cache: dict[str, AIResponse] = {}
        self._clients: dict[BackendType, Any] = {}
        self._backend_mapping = {
            BackendType.OLLAMA: "local",
            BackendType.ANTHROPIC: "api",
            BackendType.GEMINI: "gemini",
            BackendType.GROQ: "groq",
            BackendType.DEEPSEEK: "deepseek",
        }

    def _get_client(self, backend: BackendType) -> Any:
        """Get or create a modern AIClient for the given backend."""
        if backend not in self._clients:
            from bb_paxdata.infrastructure.ai.factory import AIClientFactory

            backend_str = self._backend_mapping[backend]
            api_key = self.api_key if backend != BackendType.OLLAMA else None
            base_url = self.base_url if backend == BackendType.OLLAMA else None

            self._clients[backend] = AIClientFactory.create(
                backend=backend_str,
                api_key=api_key or "",
                base_url=base_url,
            )

        return self._clients[backend]

    async def analyze_text(
        self,
        text: str,
        context: str | None = None,
        backend: BackendType | None = None,
        model: str | None = None,
    ) -> AIResponse:
        """Analyze text using AI (async).

        Args:
            text: Text to analyze
            context: Optional context
            backend: Backend to use (uses default if None)
            model: Model to use (uses backend default if None)

        Returns:
            AI analysis response
        """
        backend = backend or self.default_backend

        # Check cache
        cache_key = self._get_cache_key(text, context, backend, model)
        if cache_key in self.cache:
            cached_response = self.cache[cache_key]
            cached_response.cached = True
            return cached_response

        # Build prompt
        prompt = text
        if context:
            prompt = f"Context: {context}\n\nText: {text}"
        prompt += (
            "\n\nAnalyze this diplomatic text and provide your response in JSON format."
        )

        # Get modern client and call it
        client = self._get_client(backend)

        from bb_paxdata.infrastructure.ai.base import CompletionOptions

        options = CompletionOptions(
            system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
        )

        if model:
            # Note: Modern clients don't support dynamic model switching after creation
            # This is a limitation of the new architecture
            pass

        start_time = time.time()
        result = await client.complete(prompt, options)
        processing_time = time.time() - start_time

        parsed_content = result.parsed
        if not parsed_content and result.content:
            parsed_content = self._parse_ai_response(result.content)

        # Convert CompletionResult to AIResponse for backward compatibility
        response = AIResponse(
            content=parsed_content or {"raw_content": result.content},
            model_used=result.model,
            backend_used=backend,
            processing_time=processing_time,
            tokens_used=result.tokens_used,
            cached=False,
        )

        # Cache response
        if result.success:
            self.cache[cache_key] = response

        return response

    def _parse_ai_response(self, raw: str) -> dict[str, Any]:
        """Route AI JSON recovery through the canonical RecoveryEngine."""
        result = RecoveryEngine().recover(raw)
        if result.success and result.data is not None:
            return result.data
        return {}

    async def analyze_batch(
        self,
        texts: list[str],
        context: str | None = None,
        backend: BackendType | None = None,
        model: str | None = None,
    ) -> list[AIResponse]:
        """Analyze multiple texts in batch using asyncio.gather for parallel processing.

        Args:
            texts: List of texts to analyze
            context: Optional context for all texts
            backend: Backend to use
            model: Model to use

        Returns:
            List of AI responses
        """
        # Use asyncio.gather for parallel processing instead of serial loop
        tasks = [self.analyze_text(text, context, backend, model) for text in texts]
        return await asyncio.gather(*tasks)

    def get_available_backends(self) -> list[BackendType]:
        """Get list of available backends."""
        return list(self._backend_mapping.keys())

    def get_available_models(self, backend: BackendType) -> list[str]:
        """Get available models for a backend.

        Args:
            backend: Backend type

        Returns:
            List of model names
        """
        # Return default models for each backend
        default_models = {
            BackendType.OLLAMA: ["gemma3:4b"],
            BackendType.ANTHROPIC: ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
            BackendType.GEMINI: ["gemini-2.5-flash"],
            BackendType.GROQ: ["llama-3.3-70b-versatile"],
            BackendType.DEEPSEEK: ["deepseek-chat"],
        }
        return default_models.get(backend, [])

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self.cache.clear()

    def _get_cache_key(
        self, text: str, context: str | None, backend: BackendType, model: str | None
    ) -> str:
        """Generate cache key for request."""
        key_data = f"{text}|{context or ''}|{backend.value}|{model or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def health_check(self) -> dict[str, bool]:
        """Check health of all backends.

        Returns:
            Dictionary mapping backend names to health status
        """
        health = {}

        for backend_type in self._backend_mapping.keys():
            try:
                client = self._get_client(backend_type)
                is_healthy = await client.health_check()
                health[backend_type.value] = is_healthy
            except Exception:
                health[backend_type.value] = False

        return health

    async def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Asynchronously generate a text completion from a prompt.

        Args:
            prompt: The prompt to complete
            temperature: Sampling temperature

        Returns:
            Generated text as JSON string
        """
        response = await self.analyze_text(text=prompt, backend=self.default_backend)
        return json.dumps(response.content)


# Backward compatibility alias: AIAnalyst now points to the modern async adapter
AIAnalyst = ModernAIAnalystAdapter
