from __future__ import annotations

import json
import re
from typing import Any, cast

import structlog

from bb_paxdata.infrastructure.ai.batch import BatchItem, BatchProcessor

from ..models.ai_analysis import AIAnalysisResult
from .language_detector import LanguageDetector
from .prompt_registry import PromptRegistry, build_default_registry

logger = structlog.get_logger(__name__)


class AIProviderNotConfiguredError(RuntimeError):
    """Raised when AIAnalyst has no infrastructure analyst configured.

    This error signals that the *infra_analyst* dependency was not injected
    and no real AI backend is available.  Callers should either:

    1. Provide a working *infra_analyst* instance (e.g.
       ``ModernAIAnalystAdapter``) at construction time, or
    2. Set up the environment variables / config so that the service
       container can inject one automatically.
    """


class AIAnalyst:
    def __init__(
        self,
        registry: PromptRegistry | None = None,
        language_detector: LanguageDetector | None = None,
        default_prompt_id: str = "diplomatic_analysis",
        few_shot_injector: Any | None = None,
        infra_analyst: Any | None = None,
        batch_processor: BatchProcessor | None = None,
    ):
        self.registry = registry or build_default_registry()
        self.language_detector = language_detector or LanguageDetector()
        self.default_prompt_id = default_prompt_id
        self.few_shot_injector = few_shot_injector
        self.infra_analyst = infra_analyst
        self._batch_processor = batch_processor

    async def analyze(
        self,
        text: str,
        prompt_id: str | None = None,
        forced_version: str | None = None,
        language: str | None = None,
        file_id: str | None = None,
    ) -> AIAnalysisResult:
        """Analyze a single text.

        Raises:
            AIProviderNotConfiguredError: If *infra_analyst* is ``None`` and
                no batch processor can handle the request.
        """
        resolved_prompt_id = prompt_id or self.default_prompt_id
        detected_language = language or self.language_detector.detect(text)
        if forced_version:
            active_prompt = self.registry.get_version(
                resolved_prompt_id, forced_version
            )
            if active_prompt is None:
                logger.warning(f"Zorlanan versiyon bulunamadı: {forced_version}")
        else:
            active_prompt = self.registry.get_active(
                resolved_prompt_id, detected_language
            )
        if active_prompt is None:
            logger.error(f"Aktif prompt bulunamadı: {resolved_prompt_id}")
            return AIAnalysisResult(
                prompt_version=f"{resolved_prompt_id}@unknown",
                error="no_active_prompt",
            )
        rendered = active_prompt.template.format(text=text)
        if self.few_shot_injector:
            rendered = await self.few_shot_injector.inject(
                base_prompt=rendered, frame_hint=None
            )
        raw_response = await self._call_ai_model(rendered, active_prompt.model_name)
        parsed = self._parse_response(raw_response)
        return AIAnalysisResult(
            sentiment_score=parsed.get("sentiment_score"),
            risk_score=parsed.get("risk_score"),
            sentiment_label=parsed.get("sentiment_label"),
            risk_factors=parsed.get("risk_factors", []),
            summary=parsed.get("summary"),
            key_claims=parsed.get("key_claims", []),
            prompt_version=active_prompt.full_version_id,
            prompt_hash=active_prompt.hash,
            model_name=active_prompt.model_name,
            parse_error=parsed.get("_parse_error"),
        )

    async def _call_ai_model(self, rendered_prompt: str, model_name: str) -> str:
        """Route the request to the configured infrastructure analyst.

        Raises:
            AIProviderNotConfiguredError: If *infra_analyst* is ``None``.
        """
        if self.infra_analyst is not None:
            from bb_paxdata.infrastructure.ai.base import CompletionOptions

            options = CompletionOptions(
                system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
                temperature=0.3,
                max_tokens=1000,
                json_mode=True,
            )
            res = await self.infra_analyst.complete(rendered_prompt, options)
            return res.content
        raise AIProviderNotConfiguredError(
            "AIAnalyst has no infra_analyst configured. "
            "Provide a modern AIClient instance or configure "
            "AI backend environment variables."
        )

    def _parse_response(self, raw: str) -> dict[str, Any]:
        try:
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                return cast(dict[str, Any], json.loads(json_match.group()))
            return cast(dict[str, Any], json.loads(raw))
        except json.JSONDecodeError as e:
            logger.error(f"AI yanıtı parse edilemedi: {e}. Ham yanıt: {raw[:200]}")
            return {
                "sentiment_score": None,
                "risk_score": None,
                "sentiment_label": None,
                "risk_factors": [],
                "summary": None,
                "key_claims": [],
                "_parse_error": str(e),
            }

    async def analyze_texts(
        self, texts: list[str], file_id: str | None = None
    ) -> list[AIAnalysisResult]:
        """Analyze multiple texts using the batch processor if available.

        If no batch processor is configured, falls back to sequential single
        analysis.  Each item is wrapped in a try/except so that a failure for
        one text (e.g. missing AI provider) does not abort the entire list.
        """
        if not texts:
            return []

        if not self._batch_processor:
            results: list[AIAnalysisResult] = []
            for text in texts:
                try:
                    res = await self.analyze(text, file_id=file_id)
                    results.append(res)
                except AIProviderNotConfiguredError as exc:
                    logger.error(f"AI provider not configured: {exc}")
                    results.append(
                        AIAnalysisResult(
                            prompt_version=f"{self.default_prompt_id}@unavailable",
                            error="ai_provider_not_configured",
                        )
                    )
                except Exception as exc:
                    logger.exception("Unexpected error during single analysis")
                    results.append(
                        AIAnalysisResult(
                            prompt_version=f"{self.default_prompt_id}@error",
                            error=f"analysis_failed: {exc}",
                        )
                    )
            return results

        items = [
            BatchItem(
                item_id=str(i),
                payload=text,
                metadata={"file_id": file_id} if file_id else {},
            )
            for i, text in enumerate(texts)
        ]
        resolved_prompt_id = self.default_prompt_id
        detected_language = self.language_detector.detect(texts[0])
        active_prompt = self.registry.get_active(resolved_prompt_id, detected_language)
        if active_prompt is None:
            logger.error(f"Aktif prompt bulunamadı: {resolved_prompt_id}")
            return [
                AIAnalysisResult(
                    prompt_version=f"{resolved_prompt_id}@unknown",
                    error="no_active_prompt",
                )
                for _ in texts
            ]

        def build_prompt(batch_items: list[BatchItem]) -> str:
            items_str = ""
            for item in batch_items:
                items_str += f"ID: {item.item_id}\nMetin: {item.payload}\n---\n"
            return (
                "Sen, uluslararası diplomasi ve jeopolitik analizde uzman bir yapay zeka asistanısın.\n"
                "Aşağıdaki metinlerin her birini çok katmanlı olarak analiz et.\n\n"
                "İnceleme kriterleri:\n"
                "- Siyasi risk düzeyi (gerginlik esnekliği, retorik şiddeti, sözde diplomasi tespiti)\n"
                "- Duygusal ton (matematiksel olarak: -1.0 = aşırı negatif, +1.0 = aşırı pozitif)\n"
                "- Ana iddialar ve bunların diplomatik doğruluk riski\n\n"
                "YANIT FORMATI (sadece geçerli JSON, markdown veya açıklama olmadan):\n"
                "Önemli: Yanıtın mutlaka her bir metin için bir analiz objesi içeren bir JSON listesi veya\n"
                '"results" anahtarı altında bir liste olmalıdır.\n'
                "Her obje mutlaka ilgili metnin ID'sini 'sent_id' alanı altında barındırmalıdır.\n"
                "Format örneği:\n"
                "[\n"
                '  {"sent_id": "0", "sentiment_score": -0.35, "risk_score": 0.55, "sentiment_label": "negative", "risk_factors": ["diplomatic_tension"], "summary": "...", "key_claims": ["..."]},\n'
                '  {"sent_id": "1", ...}\n'
                "]\n\n"
                f"Analiz edilecek metinler:\n\n{items_str}"
            )

        try:
            batch_results, _stats = await self._batch_processor.process(
                items, build_prompt
            )
        except Exception as exc:
            logger.error(f"BatchProcessor failed: {exc}. Falling back to individual.")
            return await self._fallback_individual(texts, file_id=file_id)

        results_map = {res.item_id: res for res in batch_results}
        final_results: list[AIAnalysisResult] = []
        for i, text in enumerate(texts):
            res = results_map.get(str(i))
            if res and res.success and res.parsed:
                parsed = res.parsed
                final_results.append(
                    AIAnalysisResult(
                        sentiment_score=parsed.get("sentiment_score"),
                        risk_score=parsed.get("risk_score"),
                        sentiment_label=parsed.get("sentiment_label"),
                        risk_factors=parsed.get("risk_factors", []),
                        summary=parsed.get("summary"),
                        key_claims=parsed.get("key_claims", []),
                        prompt_version=active_prompt.full_version_id,
                        prompt_hash=active_prompt.hash,
                        model_name=active_prompt.model_name,
                        parse_error=res.error,
                    )
                )
            else:
                logger.warning(
                    f"Batch item {i} failed or has no parsed data, "
                    "calling single analyze fallback."
                )
                try:
                    fallback_res = await self.analyze(text)
                    final_results.append(fallback_res)
                except AIProviderNotConfiguredError as exc:
                    logger.error(f"AI provider not configured for fallback: {exc}")
                    final_results.append(
                        AIAnalysisResult(
                            prompt_version=active_prompt.full_version_id,
                            prompt_hash=active_prompt.hash,
                            model_name=active_prompt.model_name,
                            error="ai_provider_not_configured",
                        )
                    )
                except Exception as exc:
                    logger.exception(f"Single fallback failed for item {i}")
                    final_results.append(
                        AIAnalysisResult(
                            prompt_version=active_prompt.full_version_id,
                            prompt_hash=active_prompt.hash,
                            model_name=active_prompt.model_name,
                            error=f"fallback_failed: {exc}",
                        )
                    )
        return final_results

    async def _fallback_individual(
        self, texts: list[str], file_id: str | None = None
    ) -> list[AIAnalysisResult]:
        """Process texts one-by-one when batch processing is unavailable."""
        results: list[AIAnalysisResult] = []
        for text in texts:
            try:
                res = await self.analyze(text, file_id=file_id)
                results.append(res)
            except AIProviderNotConfiguredError as exc:
                logger.error(f"AI provider not configured: {exc}")
                results.append(
                    AIAnalysisResult(
                        prompt_version=f"{self.default_prompt_id}@unavailable",
                        error="ai_provider_not_configured",
                    )
                )
            except Exception as exc:
                logger.exception("Unexpected error during fallback analysis")
                results.append(
                    AIAnalysisResult(
                        prompt_version=f"{self.default_prompt_id}@error",
                        error=f"analysis_failed: {exc}",
                    )
                )
        return results
