# ============================================================
# DOSYA: src/bb_paxdata/application/pipeline/analysis_pipeline.py
# AÇIKLAMA: 4 aşamalı end-to-end pipeline
# ============================================================

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.pipeline.dki_assembler import DKIAssembler
from bb_paxdata.application.pipeline.frame.episodic_themetic_classifier import (
    EpisodicThematicClassifier,
)
from bb_paxdata.application.pipeline.frame.frame_assembler import FrameAssembler
from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult
from bb_paxdata.application.pipeline.sbi_calculator import SBICalculator
from bb_paxdata.domain.models.dki import SegmentWindow
from bb_paxdata.infrastructure.ai.frame_detection.frame_detection_pipeline import (
    FrameDetectionPipeline,
)
from bb_paxdata.infrastructure.ai.frame_detection.frame_lexicon_service import (
    FrameLexiconService,
)

from ...domain.exceptions import MissingAIOutputException
from ...domain.models.analysis import Analysis
from ...domain.services.language_detector import LanguageDetector
from ...domain.services.negation_detector_protocol import NegationDetectorProtocol
from ...domain.services.power_calculator_protocol import PowerCalculatorProtocol
from ...domain.services.protocols import (
    AIAnalystProtocol,
    AnomalyServiceProtocol,
    NERServiceProtocol,
    TokenizerProtocol,
)
from ...domain.services.risk_detector_protocol import RiskSignalDetectorProtocol
from ...domain.services.sbi_protocols import (
    EngagementScorerProtocol,
    StanceDensityProtocol,
)
from ...domain.services.topic_modeling_protocol import TopicModelingProtocol
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
        negation_detector: NegationDetectorProtocol,
        risk_detector: RiskSignalDetectorProtocol,
        power_calculator: PowerCalculatorProtocol,
        topic_modeling_service: TopicModelingProtocol,
        frame_pipeline: FrameDetectionPipeline,
        lexicon_service: FrameLexiconService,
        episodic_classifier: EpisodicThematicClassifier,
        frame_assembler: FrameAssembler,
        sbi_calculator: SBICalculator,
        stance_calculator: StanceDensityProtocol,
        engagement_scorer: EngagementScorerProtocol,
        language_detector: LanguageDetector | None = None,
        assembler: AnalysisAssembler | None = None,
        collect_stage: CollectStage | None = None,
        finalize_stage: FinalizeStage | None = None,
        dki_assembler: DKIAssembler | None = None,
        fail_fast_on_missing_ai: bool = False,
    ):
        self.ner_service = ner_service
        self.tokenizer_service = tokenizer_service
        self.ai_analyst = ai_analyst
        self.anomaly_service = anomaly_service
        self.country_collector = country_collector
        self.negation_detector = negation_detector
        self.risk_detector = risk_detector
        self.power_calculator = power_calculator
        self.topic_modeling_service = topic_modeling_service
        self.sbi_calculator = sbi_calculator
        self.language_detector = language_detector or LanguageDetector()
        self.assembler = assembler or AnalysisAssembler(sbi_calculator=sbi_calculator)
        self.dki_assembler = dki_assembler

        self.collect_stage = collect_stage or CollectStage(
            ner_service,
            tokenizer_service,
            ai_analyst,
            country_collector,
            negation_detector,
            risk_detector,
            power_calculator,
            topic_modeling_service,
            frame_pipeline,
            lexicon_service,
            episodic_classifier,
            frame_assembler,
            stance_calculator,
            engagement_scorer,
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
        historical_analyses: list[Analysis] | None = None,
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
            historical_segments=(
                [
                    SegmentWindow(
                        segment_ids=[h.segment_id],
                        texts=[h.source_text],
                        speaker_id=h.speaker_id,
                    )
                    for h in (historical_analyses or [])
                ]
                if historical_analyses
                else None
            ),
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
                negation_cues=collect_result.negation_cues,
                risk_signals=collect_result.risk_signals,
                power_indices=collect_result.power_indices,
                topic_result=collect_result.topic_result,
                frame_detection=collect_result.frame_detection,
                frame_salience=collect_result.frame_salience,
                # Note: sbi_result is calculated later at session level,
                # but we can store individual components for now.
                metadata=metadata,
            )

            # Enrich analysis with collected SBI components
            analysis = analysis.model_copy(
                update={
                    "emotional_intensity": collect_result.engagement_score,  # Proxy
                    "complexity_score": (
                        collect_result.stance_density / 100.0
                        if collect_result.stance_density
                        else None
                    ),  # Proxy
                }
            )

            # Phase 8: Attach DKI (Immutable copy chain)
            if self.dki_assembler:
                analysis = await self.dki_assembler.attach_dki(
                    analysis=analysis,
                    history=historical_analyses or [],
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
