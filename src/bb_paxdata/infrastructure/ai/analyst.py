"""AI Analyst service for diplomatic discourse analysis.

This service provides AI-powered analysis capabilities by interfacing with
various AI backends (Ollama, Anthropic, Gemini, Groq). It implements
structured output generation, batch processing, and robust error recovery.
"""

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import requests


class BackendType(Enum):
    """Supported AI backend types."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"


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


class JSONRecoveryEngine:
    """Engine for recovering JSON from malformed AI responses."""

    @staticmethod
    def recover_json(text: str) -> dict[str, Any] | None:
        """Attempt to recover JSON from potentially malformed text.

        Args:
            text: Text that should contain JSON

        Returns:
            Parsed JSON dictionary or None if recovery fails
        """
        # Step 1: Strip markdown code blocks
        json_text = re.sub(r"```json\s*", "", text)
        json_text = re.sub(r"```\s*$", "", json_text)

        # Step 2: Remove thinking tags
        json_text = re.sub(r"<thinking>.*?</thinking>", "", json_text, flags=re.DOTALL)

        # Step 3: Fix trailing commas
        json_text = re.sub(r",\s*}", "}", json_text)
        json_text = re.sub(r",\s*]", "]", json_text)

        # Step 4: Normalize quotes
        json_text = json_text.replace("'", '"')

        # Step 5: Remove YAML block indicators
        json_text = re.sub(
            r"^---.*?---\s*", "", json_text, flags=re.MULTILINE | re.DOTALL
        )

        # Step 6: Try to extract JSON with regex
        json_match = re.search(r"\{.*\}", json_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)

        try:
            return cast(dict[str, Any], json.loads(json_text))
        except json.JSONDecodeError:
            # Last resort: try to salvage key-value pairs
            return JSONRecoveryEngine._salvage_kv_pairs(json_text)

    @staticmethod
    def _salvage_kv_pairs(text: str) -> dict[str, Any]:
        """Salvage key-value pairs from malformed JSON.

        Args:
            text: Text containing key-value pairs

        Returns:
            Dictionary with salvaged pairs
        """
        result = {}

        # Simple pattern for key: value pairs
        kv_pattern = r'"?([^"\s,{}:]+)"?\s*:\s*"?([^"\s,{}:]*)"?\s*[,}]'
        matches = re.findall(kv_pattern, text)

        for key, value in matches:
            # Try to convert to appropriate type
            if value.lower() in ["true", "false"]:
                result[key] = value.lower() == "true"
            elif value.isdigit():
                result[key] = int(value)
            elif re.match(r"^\d+\.\d+$", value):
                result[key] = float(value)
            else:
                result[key] = value

        return result


class BaseAIBackend(ABC):
    """Abstract base class for AI backends."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize the backend.

        Args:
            api_key: API key for authentication
            base_url: Base URL for the API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()

    @abstractmethod
    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate AI response for the given request.

        Args:
            request: AI request configuration

        Returns:
            AI response
        """
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """Get list of available models.

        Returns:
            List of model names
        """
        pass


class OllamaBackend(BaseAIBackend):
    """Ollama backend for local AI models."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        """Initialize Ollama backend.

        Args:
            base_url: Ollama API base URL
        """
        super().__init__(base_url=base_url)

    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate response using Ollama API."""
        start_time = time.time()

        payload = {
            "model": request.model or "gemma3:4b",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a diplomatic discourse analyst. "
                        "Always respond with valid JSON."
                    ),
                },
                {"role": "user", "content": self._build_prompt(request)},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/chat", json=payload, timeout=120
            )
            response.raise_for_status()

            data = response.json()
            content_str = data["message"]["content"]

            # Parse JSON response
            content = JSONRecoveryEngine.recover_json(content_str) or {}

            return AIResponse(
                content=content,
                model_used=cast(str, payload["model"]),
                backend_used=BackendType.OLLAMA,
                processing_time=time.time() - start_time,
            )

        except Exception as e:
            # Return error response
            return AIResponse(
                content={"error": str(e), "success": False},
                model_used=request.model or "gemma3:4b",
                backend_used=BackendType.OLLAMA,
                processing_time=time.time() - start_time,
            )

    def get_available_models(self) -> list[str]:
        """Get available Ollama models."""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=30)
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception:
            return ["gemma3:4b"]  # Fallback

    def _build_prompt(self, request: AIRequest) -> str:
        """Build prompt for Ollama."""
        prompt = request.text
        if request.context:
            prompt = f"Context: {request.context}\n\nText: {request.text}"

        prompt += (
            "\n\nAnalyze this diplomatic text and provide your response in JSON format."
        )
        return prompt


class AnthropicBackend(BaseAIBackend):
    """Anthropic Claude backend."""

    def __init__(self, api_key: str):
        """Initialize Anthropic backend.

        Args:
            api_key: Anthropic API key
        """
        super().__init__(
            api_key=api_key, base_url="https://api.anthropic.com/v1/messages"
        )

    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate response using Anthropic API."""
        start_time = time.time()

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": request.model or "claude-haiku-4-5-20251001",
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": self._build_prompt(request)}],
            "system": (
                "You are a diplomatic discourse analyst. "
                "Always respond with valid JSON. NO MARKDOWN."
            ),
        }

        try:
            response = self.session.post(
                cast(str, self.base_url), headers=headers, json=payload, timeout=120
            )
            response.raise_for_status()

            data = response.json()
            content_str = data["content"][0]["text"]

            # Parse JSON response
            content = JSONRecoveryEngine.recover_json(content_str) or {}

            return AIResponse(
                content=content,
                model_used=cast(str, payload["model"]),
                backend_used=BackendType.ANTHROPIC,
                processing_time=time.time() - start_time,
                tokens_used=data.get("usage", {}).get("input_tokens"),
            )

        except Exception as e:
            return AIResponse(
                content={"error": str(e), "success": False},
                model_used=request.model or "claude-haiku-4-5-20251001",
                backend_used=BackendType.ANTHROPIC,
                processing_time=time.time() - start_time,
            )

    def get_available_models(self) -> list[str]:
        """Get available Anthropic models."""
        return ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"]

    def _build_prompt(self, request: AIRequest) -> str:
        """Build prompt for Anthropic."""
        prompt = request.text
        if request.context:
            prompt = f"Context: {request.context}\n\nText: {request.text}"

        prompt += (
            "\n\nAnalyze this diplomatic text and provide your response in "
            "JSON format. Do NOT use markdown formatting."
        )
        return prompt


class AIAnalyst:
    """Main AI analyst service that coordinates multiple backends."""

    def __init__(
        self,
        default_backend: BackendType = BackendType.OLLAMA,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize AI analyst.

        Args:
            default_backend: Default backend to use
            api_key: API key for cloud backends
            base_url: Base URL for local backends
        """
        self.default_backend = default_backend
        self.backends: dict[BackendType, BaseAIBackend] = {}
        self.cache: dict[str, AIResponse] = {}

        # Initialize backends
        self._initialize_backends(api_key, base_url)

    def _initialize_backends(self, api_key: str | None, base_url: str | None) -> None:
        """Initialize available backends."""
        # Always initialize Ollama
        self.backends[BackendType.OLLAMA] = OllamaBackend(
            base_url or "http://localhost:11434"
        )

        # Initialize cloud backends if API key provided
        if api_key:
            self.backends[BackendType.ANTHROPIC] = AnthropicBackend(api_key)
            # Add other cloud backends as needed

    def analyze_text(
        self,
        text: str,
        context: str | None = None,
        backend: BackendType | None = None,
        model: str | None = None,
    ) -> AIResponse:
        """Analyze text using AI.

        Args:
            text: Text to analyze
            context: Optional context
            backend: Backend to use (uses default if None)
            model: Model to use (uses backend default if None)

        Returns:
            AI analysis response
        """
        backend = backend or self.default_backend

        if backend not in self.backends:
            raise ValueError(f"Backend {backend} not available")

        # Check cache
        cache_key = self._get_cache_key(text, context, backend, model)
        if cache_key in self.cache:
            cached_response = self.cache[cache_key]
            cached_response.cached = True
            return cached_response

        # Create request
        request = AIRequest(text=text, context=context, model=model)

        # Generate response
        response = self.backends[backend].generate_response(request)

        # Cache response
        if response.content.get("success", True):
            self.cache[cache_key] = response

        return response

    def analyze_batch(
        self,
        texts: list[str],
        context: str | None = None,
        backend: BackendType | None = None,
        model: str | None = None,
    ) -> list[AIResponse]:
        """Analyze multiple texts in batch.

        Args:
            texts: List of texts to analyze
            context: Optional context for all texts
            backend: Backend to use
            model: Model to use

        Returns:
            List of AI responses
        """
        responses = []

        for text in texts:
            response = self.analyze_text(text, context, backend, model)
            responses.append(response)

        return responses

    def get_available_backends(self) -> list[BackendType]:
        """Get list of available backends."""
        return list(self.backends.keys())

    def get_available_models(self, backend: BackendType) -> list[str]:
        """Get available models for a backend.

        Args:
            backend: Backend type

        Returns:
            List of model names
        """
        if backend in self.backends:
            return self.backends[backend].get_available_models()
        return []

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self.cache.clear()

    def _get_cache_key(
        self, text: str, context: str | None, backend: BackendType, model: str | None
    ) -> str:
        """Generate cache key for request."""
        key_data = f"{text}|{context or ''}|{backend.value}|{model or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def health_check(self) -> dict[str, bool]:
        """Check health of all backends.

        Returns:
            Dictionary mapping backend names to health status
        """
        health = {}

        for backend_type, backend in self.backends.items():
            try:
                # Try to get models as a simple health check
                models = backend.get_available_models()
                health[backend_type.value] = len(models) > 0
            except Exception:
                health[backend_type.value] = False

        return health
