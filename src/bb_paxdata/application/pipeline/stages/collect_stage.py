# src/bb_paxdata/application/pipeline/stages/collect_stage.py
"""
Pipeline COLLECT aşaması.
Tüm alt-servisleri paralel (asyncio.gather) çalıştırır.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from bb_paxdata.application.pipeline.models.collect_result import (
    CollectResult,
    CountryCollectResult,
)

if TYPE_CHECKING:
    from bb_paxdata.application.pipeline.stages.country_reference_collector import (
        CountryReferenceCollector,
    )
    from bb_paxdata.domain.models.country_reference import CountryReference
    from bb_paxdata.domain.services.protocols import (
        AIAnalystProtocol,
        NERServiceProtocol,
        TokenizerProtocol,
    )

logger = structlog.get_logger(__name__)


class CollectStage:
    def __init__(
        self,
        ner_service: NERServiceProtocol,
        tokenizer_service: TokenizerProtocol,
        ai_analyst: AIAnalystProtocol,
        country_collector: CountryReferenceCollector,
    ) -> None:
        self._ner_service = ner_service
        self._tokenizer_service = tokenizer_service
        self._ai_analyst = ai_analyst
        self._country_collector = country_collector

    async def run(
        self,
        text: str,
        panel_id: str,
        speaker_country: str,
        speaker_power_level: float = 0.5,
        language: str | None = None,
    ) -> CollectResult:
        """
        Tüm servisleri paralel çalıştırır.
        Hataları toplar ama pipeline'ı durdurmaz (graceful degradation).
        """
        logger.info("collect_stage.started", panel_id=panel_id, language=language)

        results = await asyncio.gather(
            self._ner_service.extract(text, language=language),
            self._tokenizer_service.tokenize(text, language=language),
            self._ai_analyst.analyze(text, language=language),
            self._country_collector.collect(
                text=text,
                panel_id=panel_id,
                speaker_country=speaker_country,
                speaker_power_level=speaker_power_level,
            ),
            return_exceptions=True,
        )

        errors: list[str] = []

        # 1. NER Result
        raw_ner = results[0]
        if isinstance(raw_ner, Exception):
            errors.append(f"[COLLECT/NER] {raw_ner}")
            logger.warning("collect_stage.ner_failed", error=str(raw_ner))
            raw_ner = {}

        # 2. Tokenizer Result
        raw_tokenizer = results[1]
        if isinstance(raw_tokenizer, Exception):
            errors.append(f"[COLLECT/TOKENIZER] {raw_tokenizer}")
            logger.warning("collect_stage.tokenizer_failed", error=str(raw_tokenizer))
            raw_tokenizer = {}

        # 3. AI Result
        raw_ai = results[2]
        if isinstance(raw_ai, Exception):
            errors.append(f"[COLLECT/AI] {raw_ai}")
            logger.error("collect_stage.ai_failed", error=str(raw_ai))
            from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult

            raw_ai = AIAnalysisResult(prompt_version="unknown@error", error=str(raw_ai))

        # 4. Country Result
        country_result = results[3]
        country_references: tuple[CountryReference, ...] = ()
        if isinstance(country_result, Exception):
            errors.append(f"[COLLECT/COUNTRY] {country_result}")
            logger.warning("collect_stage.country_failed", error=str(country_result))
        elif (
            isinstance(country_result, CountryCollectResult)
            and country_result.succeeded
        ):
            country_references = country_result.references
        else:
            logger.warning(
                "collect_stage.country_extraction_skipped",
                reason=(
                    country_result.error
                    if hasattr(country_result, "error")
                    else "no_results"
                ),
            )

        return CollectResult(
            raw_ner=raw_ner,
            raw_tokenizer=raw_tokenizer,
            raw_ai=raw_ai,
            country_references=country_references,
            errors=errors,
        )
