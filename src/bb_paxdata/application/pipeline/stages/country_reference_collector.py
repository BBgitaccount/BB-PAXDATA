# src/bb_paxdata/application/pipeline/stages/country_reference_collector.py
"""
COLLECT aşamasının country-extraction worker'ı.

Sorumluluklar:
1. spaCy NER ile metinden ülke entity'lerini çıkar.
2. Her atıf için konuşmacı ve bağlam bilgisini belirle.
3. Opsiyonel: LLM ile bağlam sınıflandırması yap (ReferenceContext).
4. CountryReference entity listesi döndür — kaydetme, sadece döndür.

LLM çağrısı yapıldığında:
- PromptRegistry'den versiyonlu prompt al.
- RecoveryEngine üzerinden parse et.
- quality/evaluator ile doğrula.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from bb_paxdata.application.pipeline.models.collect_result import CountryCollectResult
from bb_paxdata.domain.enums.country_enums import ReferenceContext
from bb_paxdata.domain.models.country_reference import CountryReference

if TYPE_CHECKING:
    import spacy
    from bb_paxdata.domain.services.protocols import AIAnalystProtocol
    from bb_paxdata.infrastructure.ai.prompt_registry import PromptRegistry
    from bb_paxdata.infrastructure.ai.recovery import RecoveryEngine
    from bb_paxdata.quality.evaluator import QualityEvaluator

logger = structlog.get_logger(__name__)

# Bağlam mapping: LLM çıktısı string → ReferenceContext enum
_CONTEXT_MAP: dict[str, ReferenceContext] = {
    "accusation": ReferenceContext.ACCUSATION,
    "praise": ReferenceContext.PRAISE,
    "negotiation": ReferenceContext.NEGOTIATION,
    "threat": ReferenceContext.THREAT,
    "cooperation": ReferenceContext.COOPERATION,
    "neutral": ReferenceContext.NEUTRAL_MENTION,
}


class CountryReferenceCollector:
    """
    COLLECT aşamasının country-extraction worker'ı.

    Constructor bağımlılıkları:
    - nlp: spaCy Language objesi (infrastructure/nlp'den inject edilir)
    - country_vocabulary: bilinen ülke adları sözlüğü
    - llm_client: LLM istemcisi (opsiyonel — None ise sadece NER kullanılır)
    - recovery_engine: AI yanıtlarını parse eden engine
    - prompt_registry: versiyonlu prompt yöneticisi
    - quality_evaluator: çıktı kalitesini denetleyen judge

    Tüm bu bağımlılıklar dışarıdan inject edilir — collector içinde örneklenmez.
    """

    def __init__(
        self,
        nlp: spacy.Language,  # type: ignore[name-defined]
        country_vocabulary: set[str],
        llm_client: AIAnalystProtocol | None = None,
        recovery_engine: RecoveryEngine | None = None,
        prompt_registry: PromptRegistry | None = None,
        quality_evaluator: QualityEvaluator | None = None,
        use_llm_context: bool = False,
    ) -> None:
        self._nlp = nlp
        self._vocab = country_vocabulary
        self._llm = llm_client
        self._recovery = recovery_engine
        self._prompts = prompt_registry
        self._evaluator = quality_evaluator
        self._use_llm_context = use_llm_context and llm_client is not None

    async def collect(
        self,
        text: str,
        panel_id: str,
        speaker_country: str,
        speaker_power_level: float = 0.5,
    ) -> CountryCollectResult:
        """
        Ana giriş noktası. COLLECT aşamasından asyncio.gather() ile çağrılır.
        Exception fırlatmaz; hata durumunda error field'lı CountryCollectResult döndürür.
        """
        try:
            raw_mentions = await self._extract_mentions(text, speaker_country)
            if not raw_mentions:
                return CountryCollectResult(panel_id=panel_id, references=())

            if self._use_llm_context:
                references = await self._classify_with_llm(
                    raw_mentions, text, panel_id, speaker_country, speaker_power_level
                )
            else:
                references = self._classify_with_rules(
                    raw_mentions, panel_id, speaker_country, speaker_power_level
                )

            confidence = self._calculate_confidence(references)
            return CountryCollectResult(
                panel_id=panel_id,
                references=tuple(references),
                extraction_confidence=confidence,
            )

        except Exception as exc:
            logger.error(
                "country_reference_collector.failed",
                panel_id=panel_id,
                speaker=speaker_country,
                error=str(exc),
            )
            return CountryCollectResult(panel_id=panel_id, error=str(exc))

    async def _extract_mentions(
        self, text: str, speaker_country: str
    ) -> list[tuple[int, str, float]]:
        """
        spaCy ile metinden ülke entity'lerini çıkarır.
        Döndürür: [(sentence_index, country_name, vader_sentiment), ...]

        spaCy IO-bound değildir ama CPU-bound olduğu için
        asyncio event loop'u bloke etmemek için executor'da çalıştırılır.
        """
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, self._nlp, text)

        mentions: list[tuple[int, str, float]] = []
        sentences = list(doc.sents)

        for sent_idx, sent in enumerate(sentences):
            for ent in sent.ents:
                if ent.label_ in {"GPE", "LOC", "NORP"} and ent.text in self._vocab:
                    if ent.text.lower() == speaker_country.lower():
                        continue  # Konuşmacı kendi ülkesinden bahsediyorsa atla
                    sentiment = self._vader_score(sent.text)
                    mentions.append((sent_idx, ent.text, sentiment))

        return mentions

    def _vader_score(self, text: str) -> float:
        """
        VADER ile basit cümle duygu skoru.
        VADER zaten infrastructure/nlp'de mevcut olmalı; burada sadece kullanılır.
        Mevcut VADER entegrasyonu farklıysa bu metodu o entegrasyona uyarla.
        """
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            analyzer = SentimentIntensityAnalyzer()
            return float(analyzer.polarity_scores(text)["compound"])
        except ImportError:
            return 0.0

    def _classify_with_rules(
        self,
        mentions: list[tuple[int, str, float]],
        panel_id: str,
        speaker_country: str,
        power_level: float,
    ) -> list[CountryReference]:
        """
        Kural tabanlı bağlam sınıflandırması.
        Sentiment eşiklerine göre ReferenceContext atar.
        """
        references: list[CountryReference] = []
        for sent_idx, country, sentiment in mentions:
            if sentiment < -0.5:
                context = ReferenceContext.ACCUSATION
            elif sentiment > 0.5:
                context = ReferenceContext.PRAISE
            else:
                context = ReferenceContext.NEUTRAL_MENTION

            references.append(
                CountryReference(
                    panel_id=panel_id,
                    speaker_country=speaker_country,
                    referenced_country=country,
                    sentence_index=sent_idx,
                    reference_context=context,
                    raw_sentiment_score=sentiment,
                    speaker_power_level=power_level,
                )
            )
        return references

    async def _classify_with_llm(
        self,
        mentions: list[tuple[int, str, float]],
        full_text: str,
        panel_id: str,
        speaker_country: str,
        power_level: float,
    ) -> list[CountryReference]:
        """
        LLM ile gelişmiş bağlam sınıflandırması.

        Akış:
        1. PromptRegistry'den prompt al (versiyonlu, audit trail için)
        2. LLM'e gönder
        3. RecoveryEngine ile parse et (6 seviyeli kurtarma)
        4. QualityEvaluator ile doğrula
        5. Başarısız olursa kural tabanlı fallback'e dön
        """
        if not self._prompts or not self._recovery or not self._llm:
            return self._classify_with_rules(
                mentions, panel_id, speaker_country, power_level
            )

        try:
            prompt_template_meta = await self._prompts.get(
                "country_context_classifier@v1.0"
            )
            if not prompt_template_meta:
                logger.warning("country_llm_classifier.prompt_missing")
                return self._classify_with_rules(
                    mentions, panel_id, speaker_country, power_level
                )

            prompt_template = prompt_template_meta.content
            mention_list = "\n".join(
                f"- {country} (sentence {idx}, sentiment {sent:.2f})"
                for idx, country, sent in mentions
            )
            prompt = prompt_template.format(
                speaker_country=speaker_country,
                mention_list=mention_list,
                text_excerpt=full_text[:1500],  # Token limit koruması
            )

            raw_analysis = await self._llm.analyze(prompt)
            raw_text = raw_analysis.raw_output or ""

            # RecoveryEngine.recover is synchronous
            recovery_result = self._recovery.recover(
                raw_text,
                default_schema={"classifications": []},
            )

            if not recovery_result.success or not recovery_result.data:
                logger.warning(
                    "country_llm_classifier.recovery_failed", panel_id=panel_id
                )
                return self._classify_with_rules(
                    mentions, panel_id, speaker_country, power_level
                )

            parsed = recovery_result.data

            if self._evaluator:
                is_valid = await self._evaluator.validate(
                    output=parsed,
                    criteria=["completeness", "schema_conformance"],
                )
                if not is_valid:
                    logger.warning(
                        "country_llm_classifier.quality_failed", panel_id=panel_id
                    )
                    return self._classify_with_rules(
                        mentions, panel_id, speaker_country, power_level
                    )

            return self._build_from_llm_output(
                parsed, mentions, panel_id, speaker_country, power_level
            )

        except Exception as exc:
            logger.warning(
                "country_llm_classifier.fallback_to_rules",
                reason=str(exc),
                panel_id=panel_id,
            )
            return self._classify_with_rules(
                mentions, panel_id, speaker_country, power_level
            )

    def _build_from_llm_output(
        self,
        parsed: list[dict[str, Any]] | dict[str, Any],
        mentions: list[tuple[int, str, float]],
        panel_id: str,
        speaker_country: str,
        power_level: float,
    ) -> list[CountryReference]:
        """LLM çıktısından CountryReference listesi oluşturur."""
        mention_lookup: dict[str, tuple[int, float]] = {
            country: (idx, sent) for idx, country, sent in mentions
        }
        references: list[CountryReference] = []

        # JSON recovery sometimes returns a dict with 'classifications' key
        # or a single classification dict directly.
        classifications: list[dict[str, Any]]
        if isinstance(parsed, dict):
            if "classifications" in parsed and isinstance(
                parsed["classifications"], list
            ):
                classifications = parsed["classifications"]
            else:
                # Wrap single dict in a list
                classifications = [parsed]
        else:
            classifications = parsed

        for classification in classifications:
            country = classification.get("country", "")
            context_str = classification.get("context", "neutral").lower()
            context = _CONTEXT_MAP.get(context_str, ReferenceContext.NEUTRAL_MENTION)

            if country not in mention_lookup:
                continue

            sent_idx, sentiment = mention_lookup[country]
            references.append(
                CountryReference(
                    panel_id=panel_id,
                    speaker_country=speaker_country,
                    referenced_country=country,
                    sentence_index=sent_idx,
                    reference_context=context,
                    raw_sentiment_score=sentiment,
                    speaker_power_level=power_level,
                )
            )
        return references

    def _calculate_confidence(self, references: list[CountryReference]) -> float:
        """
        Extraction güven skoru. Kural tabanlıda orta güven,
        LLM tabanlıda yüksek güven (eğer quality geçtiyse) döner.
        """
        if not references:
            return 0.0
        return 0.85 if self._use_llm_context else 0.65
