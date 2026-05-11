from __future__ import annotations

from typing import Any

import structlog

from bb_paxdata.infrastructure.ai.anthropic import AnthropicClient
from bb_paxdata.infrastructure.ai.base import AIClient
from bb_paxdata.infrastructure.ai.gemini import GeminiClient
from bb_paxdata.infrastructure.ai.groq import GroqClient
from bb_paxdata.infrastructure.ai.ollama import OllamaClient

logger = structlog.get_logger(__name__)


class AIClientFactory:
    """Factory for creating AI client instances."""

    @staticmethod
    def create(
        backend: str,  # "local" | "api" | "gemini" | "groq"
        *,
        api_key: str = "",
        model: str | None = None,
        base_url: str | None = None,
    ) -> AIClient:
        """
        Create an AI client instance.

        Args:
            backend: Backend type ("local", "api", "gemini", "groq")
            api_key: API key for remote backends (required for api, gemini, groq)
            model: Model name (uses default if None)
            base_url: Base URL for local backend

        Returns:
            AIClient instance

        Raises:
            ValueError: If backend is unknown or api_key is missing for remote backends
        """
        backend = backend.lower()

        # Default models
        default_models = {
            "local": "gemma3:4b",
            "api": "claude-haiku-4-5-20251001",
            "gemini": "gemini-2.5-flash",
            "groq": "llama-3.3-70b-versatile",
        }

        if model is None:
            model = default_models.get(backend)
            if model is None:
                raise ValueError(f"Unknown backend: {backend}")

        if backend == "local":
            return OllamaClient(
                model=model,
                base_url=base_url or "http://localhost:11434",
            )

        elif backend == "api":
            if not api_key:
                raise ValueError("API key is required for Anthropic backend")
            return AnthropicClient(
                api_key=api_key,
                model=model,
            )

        elif backend == "gemini":
            if not api_key:
                raise ValueError("API key is required for Gemini backend")
            return GeminiClient(
                api_key=api_key,
                model=model,
            )

        elif backend == "groq":
            if not api_key:
                raise ValueError("API key is required for Groq backend")
            return GroqClient(
                api_key=api_key,
                model=model,
            )

        else:
            raise ValueError(f"Unknown backend: {backend}")

    @staticmethod
    def from_settings(settings: Any) -> AIClient:
        """
        Create AI client from settings object.

        Expected settings attributes:
            ai_backend: str
            ai_model: str (optional)
            anthropic_api_key: str (for api backend)
            gemini_api_key: str (for gemini backend)
            groq_api_key: str (for groq backend)
            ollama_base_url: str (for local backend)
        """
        backend = getattr(settings, "ai_backend", "local")
        model = getattr(settings, "ai_model", None)

        # Get API key based on backend
        api_key = ""
        if backend == "api":
            api_key = getattr(settings, "anthropic_api_key", "")
        elif backend == "gemini":
            api_key = getattr(settings, "gemini_api_key", "")
        elif backend == "groq":
            api_key = getattr(settings, "groq_api_key", "")

        # Get base URL for local backend
        base_url = None
        if backend == "local":
            base_url = getattr(settings, "ollama_base_url", None)

        return AIClientFactory.create(
            backend=backend,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
