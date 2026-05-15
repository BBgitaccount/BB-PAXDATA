# ============================================================
# DOSYA: src/bb_paxdata/domain/services/ai_analyst.py
# AÇIKLAMA: Versiyon damgalı, dil-aware AI analiz servisi
# ============================================================

from __future__ import annotations

import json
import logging
import re
from typing import Any, cast

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
    ):
        self.registry = registry or build_default_registry()
        self.language_detector = language_detector or LanguageDetector()
        self.default_prompt_id = default_prompt_id

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
        raw_response = self._call_ai_model(rendered, active_prompt.model_name)
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

    def _call_ai_model(self, rendered_prompt: str, model_name: str) -> str:
        """
        AI modeli çağrısı.
        Üretimde bu metod OpenAI/Anthropic SDK ile değiştirilir.
        Şu an mock yanıt döner — gerçek implementasyon için aşağıdaki yorumlu bloğu aç.
        """
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
