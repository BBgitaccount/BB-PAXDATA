# ============================================================
# DOSYA: src/bb_paxdata/application/pipeline/analysis_pipeline.py
# AÇIKLAMA: 4 aşamalı end-to-end pipeline
# ============================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult

from ...domain.exceptions import MissingAIOutputException
from ...domain.models.analysis import Analysis
from ...domain.services.language_detector import LanguageDetector
from ...domain.services.protocols import (
    AIAnalystProtocol,
    AnomalyServiceProtocol,
    NERServiceProtocol,
    TokenizerProtocol,
)
from .assembler import AnalysisAssembler
from .stages.collect_stage import CollectStage
from .stages.country_reference_collector import CountryReferenceCollector
from .stages.finalize_stage import FinalizeStage

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """
    Diplomatik metin analizi için uçtan uca 4 aşamalı pipeline.

    Aşamalar:
    1. COLLECT  — Her alt-servis bağımsız çalışır, ham veri/model üretir
    2. ASSEMBLE — AnalysisAssembler ile Analysis modeline dönüştürülür
    3. DETECT   — CrossAnomalyService ile anomali tespiti; model_copy ile güncellenir
    4. FINALIZE — PipelineResult zarfı oluşturulur

    Tasarım kararları:
    - Hiçbir aşama Analysis nesnesini doğrudan mutate etmez (immutable data flow)
    - Birden fazla aşama hatası tolere edilir (graceful degradation)
    - AI çıktısı eksikse MissingAIOutputException loglanır ama pipeline durdurmaz
    """

    def __init__(
        self,
        ner_service: NERServiceProtocol,
        tokenizer_service: TokenizerProtocol,
        ai_analyst: AIAnalystProtocol,
        anomaly_service: AnomalyServiceProtocol,
        country_collector: CountryReferenceCollector,
        language_detector: LanguageDetector | None = None,
        assembler: AnalysisAssembler | None = None,
        collect_stage: CollectStage | None = None,
        finalize_stage: FinalizeStage | None = None,
        fail_fast_on_missing_ai: bool = False,
    ):
        self.ner_service = ner_service
        self.tokenizer_service = tokenizer_service
        self.ai_analyst = ai_analyst
        self.anomaly_service = anomaly_service
        self.country_collector = country_collector
        self.language_detector = language_detector or LanguageDetector()
        self.assembler = assembler or AnalysisAssembler()

        self.collect_stage = collect_stage or CollectStage(
            ner_service, tokenizer_service, ai_analyst, country_collector
        )
        # FinalizeStage needs a repository, which we'll assume is injected if finalize_stage is None
        # This is a bit tricky if we don't have the repo here.
        # For now, let's assume FinalizeStage is injected.
        self.finalize_stage = finalize_stage
        self.fail_fast_on_missing_ai = fail_fast_on_missing_ai

    async def run(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        panel_id: str = "default_panel",
        speaker_country: str = "unknown",
        speaker_power_level: float = 0.5,
        session: AsyncSession | None = None,
    ) -> PipelineResult:
        """Metni uçtan uca analiz eder. Tüm hatalar PipelineResult.errors'a eklenir."""
        errors: list[str] = []

        # ─────────────────────────────────────────
        # AŞAMA 0: PRE-PROCESS (Centralized Language Detection)
        # ─────────────────────────────────────────
        detected_language = self.language_detector.detect(text)
        logger.info(
            f"Pipeline başladı: Dil='{detected_language}', Metin Uzunluğu={len(text)}"
        )

        # ─────────────────────────────────────────
        # AŞAMA 1: COLLECT (Async Parallel)
        # ─────────────────────────────────────────
        collect_result = await self.collect_stage.run(
            text=text,
            panel_id=panel_id,
            speaker_country=speaker_country,
            speaker_power_level=speaker_power_level,
            language=detected_language,
        )
        errors.extend(collect_result.errors)

        # ─────────────────────────────────────────
        # AŞAMA 2: ASSEMBLE
        # ─────────────────────────────────────────
        try:
            ai_result = collect_result.raw_ai
            if ai_result is None:
                # COLLECT aşamasında bir hata olmuş olmalı;
                # fallback olarak boş bir AIAnalysisResult üret
                from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult

                ai_result = AIAnalysisResult(
                    prompt_version="missing",
                    error="AI result was None in COLLECT stage",
                )

            analysis = self.assembler.assemble(
                source_text=text,
                language=detected_language,
                ner_result=collect_result.raw_ner,
                tokenizer_result=collect_result.raw_tokenizer,
                ai_result=ai_result,
                metadata=metadata,
            )
        except Exception as e:
            errors.append(f"[ASSEMBLE] {e}")
            logger.error(f"Assembly başarısız: {e}")
            return PipelineResult(
                analysis=Analysis(source_text=text),
                raw_ner=collect_result.raw_ner,
                raw_tokenizer=collect_result.raw_tokenizer,
                raw_ai=collect_result.raw_ai,
                success=False,
                errors=errors,
                stage="assemble",
            )

        # ─────────────────────────────────────────
        # AŞAMA 3: DETECT (Immutable update)
        # ─────────────────────────────────────────
        try:
            if self.fail_fast_on_missing_ai and not analysis.has_ai_output:
                raise MissingAIOutputException(
                    analysis_id=analysis.id,
                    missing_fields=["ai_sentiment_score", "ai_risk_score"],
                )

            anomaly_result = await self.anomaly_service.detect(analysis)

            # IMMUTABLE: model_copy ile yeni Analysis nesnesi üretilir, mevcut mutate edilmez
            analysis = analysis.model_copy(
                update={
                    "anomaly_score": anomaly_result.score,
                    "anomaly_flags": anomaly_result.flags,
                    "risk_level": anomaly_result.risk_level,
                }
            )
        except MissingAIOutputException as e:
            errors.append(f"[DETECT/MISSING_AI] {e}")
            logger.error(str(e))
        except Exception as e:
            errors.append(f"[DETECT] {e}")
            logger.error(f"Anomali servisi başarısız: {e}")

        # ─────────────────────────────────────────
        # AŞAMA 4: FINALIZE
        # ─────────────────────────────────────────
        if self.finalize_stage:
            return await self.finalize_stage.run(
                analysis=analysis,
                collect_result=collect_result,
                success=len(errors) == 0,
                errors=errors,
                session=session,
            )

        return PipelineResult(
            analysis=analysis,
            raw_ner=collect_result.raw_ner,
            raw_tokenizer=collect_result.raw_tokenizer,
            raw_ai=collect_result.raw_ai,
            success=len(errors) == 0,
            errors=errors,
            stage="completed" if len(errors) == 0 else "completed_with_errors",
        )

    async def analyze_sentence(
        self, text: str, metadata: dict[str, Any] | None = None
    ) -> PipelineResult:
        """Geriye uyumlu alias — dış API contract'ı bozulmaz."""
        return await self.run(text, metadata)
