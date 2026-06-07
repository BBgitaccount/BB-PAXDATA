# ============================================================
# DOSYA: src/bb_paxdata/domain/services/ai_analyst.py
# AÇIKLAMA: Versiyon damgalı, dil-aware AI analiz servisi
# ============================================================

from __future__ import annotations

import json
import logging
import re
from typing import Any, cast

from bb_paxdata.infrastructure.ai.batch import BatchItem, BatchProcessor

from ..models.ai_analysis import AIAnalysisResult
from .language_detector import LanguageDetector
from .prompt_registry import PromptRegistry, build_default_registry

logger = logging.getLogger(__name__)


class AIAnalyst:
    """
    AI tabanlı metin analiz servisi.

    Her analiz çağrısında:
    1. Aktif prompt versiyonunu dil bazlı olarak registry'den çeker
    2. Şablonu metinle doldurur
    3. AI modeli çağırır (gerçek implementasyonda OpenAI/Anthropic SDK)
    4. Yanıtı parse eder
    5. prompt_version + prompt_hash damgasını çıktıya ekler
    6. AIAnalysisResult Pydantic modeli döner (ham dict değil)
    """

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
    ) -> AIAnalysisResult:
        """
        Metin üzerinde AI analizi çalıştırır.
        AIAnalysisResult (Pydantic) döner — ham dict değil.
        """
        resolved_prompt_id = prompt_id or self.default_prompt_id
        detected_language = language or self.language_detector.detect(text)

        # Aktif prompt seçimi: forced_version > dil bazlı > any
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

        # Şablonu metinle doldur ve AI'a gönder
        rendered = active_prompt.template.format(text=text)
        if self.few_shot_injector:
            rendered = await self.few_shot_injector.inject(
                base_prompt=rendered, frame_hint=None
            )
        raw_response = await self._call_ai_model(rendered, active_prompt.model_name)
        parsed = self._parse_response(raw_response)

        # KRİTİK: Prompt versiyon ve hash damgası
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
        """
        AI modeli çağrısı.
        """
        if self.infra_analyst is not None:
            from bb_paxdata.infrastructure.ai.analyst import BackendType

            backend = BackendType.OLLAMA
            model_name_lower = model_name.lower()
            if "claude" in model_name_lower:
                backend = BackendType.ANTHROPIC
            elif "gemini" in model_name_lower:
                backend = BackendType.GEMINI
            elif "groq" in model_name_lower:
                backend = BackendType.GROQ

            # Direct async call - no longer using asyncio.to_thread workaround
            res = await self.infra_analyst.analyze_text(
                text=rendered_prompt,
                backend=backend,
                model=model_name,
            )
            return json.dumps(res.content)

        logger.warning(
            "AIAnalyst: MOCK yanıt kullanılıyor — gerçek AI provider bağlayın!"
        )
        return json.dumps(
            {
                "sentiment_score": -0.35,
                "risk_score": 0.55,
                "sentiment_label": "negative",
                "risk_factors": ["diplomatic_tension", "ambiguous_rhetoric"],
                "summary": "Metin diplomatik gerginlik unsurları içermektedir.",
                "key_claims": ["İlişkilerin gözden geçirilmesi gerektiği vurgulanmış."],
            }
        )

        # ── GERÇEK IMPLEMENTASYON (OpenAI) ──────────────────────────────
        # import openai
        # client = openai.OpenAI()
        # response = client.chat.completions.create(
        #     model=model_name,
        #     messages=[
        #         {"role": "system", "content": "Sadece geçerli JSON yanıt ver."},
        #         {"role": "user", "content": rendered_prompt}
        #     ],
        #     temperature=0.1,
        #     response_format={"type": "json_object"}
        # )
        # return response.choices[0].message.content

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """AI yanıtını parse eder. Markdown kod bloğu içindeki JSON'u da çıkarır."""
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

    async def analyze_texts(self, texts: list[str]) -> list[AIAnalysisResult]:
        """
        Metin listesi üzerinde AI analizi çalıştırır.
        BatchProcessor kullanarak toplu işlem yapar.
        """
        if not self._batch_processor or not texts:
            # Fallback to sequential
            results = []
            for text in texts:
                res = await self.analyze(text)
                results.append(res)
            return results

        # Wrap each text into a BatchItem
        items = [
            BatchItem(item_id=str(i), payload=text) for i, text in enumerate(texts)
        ]

        resolved_prompt_id = self.default_prompt_id
        detected_language = "any"
        if texts:
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

        # Process via BatchProcessor
        batch_results, stats = await self._batch_processor.process(items, build_prompt)

        # Map back to original order
        results_map = {res.item_id: res for res in batch_results}
        final_results = []
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
                    f"Batch item {i} failed or has no parsed data, calling single analyze fallback."
                )
                fallback_res = await self.analyze(text)
                final_results.append(fallback_res)

        return final_results
