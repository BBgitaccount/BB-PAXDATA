import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from bb_paxdata.infrastructure.ai.recovery import (
    RecoveryEngine,
)


class BackendType(Enum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    DEEPSEEK = "deepseek"


@dataclass
class AIRequest:
    text: str
    context: str | None = None
    temperature: float = 0.3
    max_tokens: int = 1000
    model: str | None = None


@dataclass
class AIResponse:
    content: dict[str, Any]
    model_used: str
    backend_used: BackendType
    processing_time: float
    tokens_used: int | None = None
    cached: bool = False


class ModernAIAnalystAdapter:
    def __init__(
        self,
        default_backend: BackendType = BackendType.OLLAMA,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
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
        cache_key = self._get_cache_key(text, context, backend, model)
        if cache_key in self.cache:
            cached_response = self.cache[cache_key]
            cached_response.cached = True
            return cached_response
        prompt = text
        if context:
            prompt = f"Context: {context}\n\nText: {text}"
        prompt += (
            "\n\nAnalyze this diplomatic text and provide your response in JSON format."
        )
        client = self._get_client(backend)
        from bb_paxdata.infrastructure.ai.base import CompletionOptions

        options = CompletionOptions(
            system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
        )
        if model:
            pass
        start_time = time.time()
        result = await client.complete(prompt, options)
        processing_time = time.time() - start_time
        parsed_content = result.parsed
        if not parsed_content and result.content:
            parsed_content = self._parse_ai_response(result.content)
        response = AIResponse(
            content=parsed_content or {"raw_content": result.content},
            model_used=result.model,
            backend_used=backend,
            processing_time=processing_time,
            tokens_used=result.tokens_used,
            cached=False,
        )
        if result.success:
            self.cache[cache_key] = response
        return response

    def _parse_ai_response(self, raw: str) -> dict[str, Any]:
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
        """Analyze multiple texts using a **real** single-prompt batch call.

        Instead of spawning N parallel individual requests (which creates N
        round-trips to the API), this method:

        1. Binds all texts into one structured prompt with indexed IDs.
        2. Makes **a single API call**.
        3. Parses the unified JSON response and maps each sub-result back to
           the original text slot.

        If the batch call fails, or the response shape does not match the
        number of input texts, it automatically falls back to parallel
        individual calls via :meth:`analyze_text`.

        Args:
            texts: List of texts to analyze.
            context: Optional shared context prepended to the batch prompt.
            backend: Backend to use (default if ``None``).
            model: Model override (backend default if ``None``).

        Returns:
            A list of :class:`AIResponse` objects in the **same order** as
            *texts*.
        """
        if not texts:
            return []

        # For a single text delegate to the regular path (no batch overhead).
        if len(texts) == 1:
            return [await self.analyze_text(texts[0], context, backend, model)]

        backend = backend or self.default_backend
        client = self._get_client(backend)

        # ------------------------------------------------------------------
        # 1. Build the unified batch prompt
        # ------------------------------------------------------------------
        indexed_texts = "\n---\n".join(
            f"[{idx}] {txt}" for idx, txt in enumerate(texts)
        )
        batch_prompt = (
            "Analyze the following diplomatic texts and return a JSON object "
            'with a "results" key containing an array of analysis objects. '
            "The array MUST be in the SAME order as the input texts and "
            "contain EXACTLY one result per text.\n\n"
            "Each result object must contain:\n"
            '  - "sent_id": the index number of the text\n'
            '  - "sentiment_score": float [-1.0, +1.0]\n'
            '  - "risk_score": float [0.0, 1.0]\n'
            '  - "sentiment_label": string (e.g. "negative", "positive", "neutral")\n'
            '  - "risk_factors": list of strings\n'
            '  - "summary": string\n'
            '  - "key_claims": list of strings\n\n'
            f"{indexed_texts}\n\n"
            "Example response format:\n"
            '{"results": [\n'
            '  {"sent_id": 0, "sentiment_score": -0.35, ...},\n'
            '  {"sent_id": 1, "sentiment_score": 0.20, ...}\n'
            "]}"
        )
        if context:
            batch_prompt = f"Context: {context}\n\n{batch_prompt}"

        from bb_paxdata.infrastructure.ai.base import CompletionOptions

        options = CompletionOptions(
            system_prompt=(
                "You are a diplomatic discourse analyst. "
                "Always return a single JSON object with a 'results' array."
            ),
            temperature=0.3,
            max_tokens=min(1000 * len(texts), 8000),
            json_mode=True,
        )

        # ------------------------------------------------------------------
        # 2. Single API call
        # ------------------------------------------------------------------
        start_time = time.time()
        try:
            result = await client.complete(batch_prompt, options)
        except Exception as exc:
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "Batch API call raised an exception; falling back to individual calls.",
                error=str(exc),
                text_count=len(texts),
                backend=backend.value,
            )
            return await self._analyze_batch_individual(texts, context, backend, model)

        processing_time = time.time() - start_time

        if not result.success or not result.content:
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "Batch API call failed or returned empty; falling back to individual calls.",
                error=result.error,
                text_count=len(texts),
                backend=backend.value,
            )
            return await self._analyze_batch_individual(texts, context, backend, model)

        # ------------------------------------------------------------------
        # 3. Parse the unified response
        # ------------------------------------------------------------------
        parsed = self._parse_ai_response(result.content)

        if not isinstance(parsed, dict):
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "Batch response is not a JSON object; falling back to individual calls.",
                got_type=type(parsed).__name__,
            )
            return await self._analyze_batch_individual(texts, context, backend, model)

        results_list: list[dict[str, Any]] | None = None

        if "results" in parsed and isinstance(parsed["results"], list):
            results_list = parsed["results"]
        # Some backends may return the raw list without the wrapper key
        elif isinstance(parsed, list):
            results_list = parsed

        if results_list is None or len(results_list) != len(texts):
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "Batch response item count mismatch; falling back to individual calls.",
                expected=len(texts),
                got=len(results_list) if results_list is not None else "None",
            )
            return await self._analyze_batch_individual(texts, context, backend, model)

        # ------------------------------------------------------------------
        # 4. Map each sub-result back to an AIResponse
        # ------------------------------------------------------------------
        per_item_time = processing_time / len(texts)
        per_item_tokens = (
            (result.tokens_used or 0) // len(texts) if result.tokens_used else None
        )
        responses: list[AIResponse] = []
        for idx, item_data in enumerate(results_list):
            data: dict[str, Any] = (
                item_data if isinstance(item_data, dict) else {"_raw": item_data}
            )
            # Ensure sent_id consistency (helpful for downstream debugging)
            data["sent_id"] = idx
            responses.append(
                AIResponse(
                    content=data,
                    model_used=result.model,
                    backend_used=backend,
                    processing_time=per_item_time,
                    tokens_used=per_item_tokens,
                    cached=False,
                )
            )
        return responses

    async def _analyze_batch_individual(
        self,
        texts: list[str],
        context: str | None = None,
        backend: BackendType | None = None,
        model: str | None = None,
    ) -> list[AIResponse]:
        """Fallback: process each text with a separate API call in parallel.

        This mirrors the old ``analyze_batch`` behaviour and is invoked only
        when the true single-prompt batch path fails.
        """
        tasks = [self.analyze_text(text, context, backend, model) for text in texts]
        return await asyncio.gather(*tasks)

    def get_available_backends(self) -> list[BackendType]:
        return list(self._backend_mapping.keys())

    def get_available_models(self, backend: BackendType) -> list[str]:
        default_models = {
            BackendType.OLLAMA: ["gemma3:4b"],
            BackendType.ANTHROPIC: ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
            BackendType.GEMINI: ["gemini-2.5-flash"],
            BackendType.GROQ: ["llama-3.3-70b-versatile"],
            BackendType.DEEPSEEK: ["deepseek-chat"],
        }
        return default_models.get(backend, [])

    def clear_cache(self) -> None:
        self.cache.clear()

    def _get_cache_key(
        self, text: str, context: str | None, backend: BackendType, model: str | None
    ) -> str:
        key_data = f"{text}|{context or ''}|{backend.value}|{model or ''}"
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()

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


AIAnalyst = ModernAIAnalystAdapter
