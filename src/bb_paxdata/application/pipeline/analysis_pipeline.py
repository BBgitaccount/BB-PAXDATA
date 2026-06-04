# ============================================================
# DOSYA: src/bb_paxdata/application/pipeline/analysis_pipeline.py
# AÇIKLAMA: 4 aşamalı end-to-end pipeline
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.consensus.dual_gate import DualGateConsensusLayer
from bb_paxdata.application.pipeline.configurator import PipelineConfigurator
from bb_paxdata.application.pipeline.dki_assembler import DKIAssembler
from bb_paxdata.application.pipeline.frame.episodic_themetic_classifier import (
    EpisodicThematicClassifier,
)
from bb_paxdata.application.pipeline.frame.frame_assembler import FrameAssembler
from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult
from bb_paxdata.application.pipeline.sbi_calculator import SBICalculator
from bb_paxdata.domain.models.anomaly import AnomalyResult, RuleIndicator
from bb_paxdata.domain.models.dki import SegmentWindow
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.ai.anomaly_controller import AIAnomalyController
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

logger = structlog.get_logger(__name__)


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
        dual_gate_layer: DualGateConsensusLayer | None = None,
        anomaly_controller: AIAnomalyController | None = None,
        fail_fast_on_missing_ai: bool = False,
        configurator: PipelineConfigurator | None = None,
        config_variant: str = "default",
        llm_position_estimator: Any | None = None,
        semantic_shift_calculator: Any | None = None,
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
            llm_position_estimator=llm_position_estimator,
            semantic_shift_calculator=semantic_shift_calculator,
        )
        self.dual_gate_layer = dual_gate_layer
        self.anomaly_controller = anomaly_controller
        self.finalize_stage = finalize_stage
        self.fail_fast_on_missing_ai = fail_fast_on_missing_ai
        self.configurator = configurator or PipelineConfigurator()
        self.config_variant = config_variant

    async def run(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        file_id: str = "default_panel",
        speaker_country: str = "unknown",
        speaker_power_level: float = 0.5,
        session: AsyncSession | None = None,
        historical_analyses: list[Analysis] | None = None,
        speaker_id: str = "unknown",
        sentence_index: int = 0,
    ) -> PipelineResult:
        """Metni uçtan uca analiz eder. Tüm hatalar PipelineResult.errors'a eklenir."""
        errors: list[str] = []

        # Resolve configuration variant from metadata (A/B testing)
        variant = (metadata or {}).get("pipeline_variant", self.config_variant)
        config = self.configurator.get_config(variant)
        active_stages = config.get(
            "stages",
            ["pre_process", "collect", "assemble", "detect", "dual_gate", "finalize"],
        )

        # ─────────────────────────────────────────
        # AŞAMA 0: PRE-PROCESS (Centralized Language Detection)
        # ─────────────────────────────────────────
        if "pre_process" in active_stages:
            detected_language = self.language_detector.detect(text)
        else:
            detected_language = "en"  # fallback
        logger.info(
            f"Pipeline başladı: Varyant='{variant}', Dil='{detected_language}', Metin Uzunluğu={len(text)}"
        )

        # ─────────────────────────────────────────
        # AŞAMA 1: COLLECT (Async Parallel)
        # ─────────────────────────────────────────
        if "collect" in active_stages:
            collect_config = config.get("collect", {})
            services_config = collect_config.get("services", None)
            lazy_threshold = collect_config.get("lazy_ai_risk_threshold", 0.5)
            lazy_formula = collect_config.get("lazy_ai_risk_formula", "max")

            if not (0.0 <= lazy_threshold <= 2.0):
                logger.warning(
                    f"pipeline.invalid_threshold: {lazy_threshold}, falling back to 0.5"
                )
                lazy_threshold = 0.5

            collect_result = await self.collect_stage.run(
                text=text,
                panel_id=file_id,
                speaker_country=speaker_country,
                speaker_power_level=speaker_power_level,
                language=detected_language,
                historical_segments=(
                    [
                        SegmentWindow(
                            segment_ids=[h.segment_id] if h.segment_id else [],
                            texts=[h.source_text],
                            speaker_id=h.speaker_id,
                        )
                        for h in (historical_analyses or [])
                    ]
                    if historical_analyses
                    else None
                ),
                speaker_id=speaker_id,
                sentence_index=sentence_index,
                services_config=services_config,
                lazy_ai_risk_threshold=lazy_threshold,
                lazy_ai_risk_formula=lazy_formula,
            )
            errors.extend(collect_result.errors)
        else:
            from bb_paxdata.application.pipeline.models.collect_result import (
                CollectResult,
            )

            collect_result = CollectResult(
                raw_ner={},
                raw_tokenizer={},
                raw_ai=None,
                country_references=(),
                negation_cues=(),
                risk_signals=(),
                power_indices={},
                topic_result=None,
                frame_detection=None,
                frame_cues=[],
                frame_salience=None,
                stance_density=0.0,
                engagement_score=0.0,
                llm_position=None,
                semantic_shift=None,
                errors=[],
            )

        # ─────────────────────────────────────────
        # AŞAMA 2: ASSEMBLE
        # ─────────────────────────────────────────
        if "assemble" in active_stages:
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
        else:
            analysis = Analysis(source_text=text, language=detected_language)

        # ─────────────────────────────────────────
        # AŞAMA 3: DETECT (Immutable update)
        # ─────────────────────────────────────────
        if "detect" in active_stages:
            try:
                detect_config = config.get("detect", {})
                fail_fast = detect_config.get(
                    "fail_fast_on_missing_ai", self.fail_fast_on_missing_ai
                )
                if self.fail_fast_on_missing_ai and not (metadata or {}).get(
                    "pipeline_variant"
                ):
                    fail_fast = True

                if fail_fast and not analysis.has_ai_output:
                    if analysis.prompt_version not in ("bypassed", "disabled"):
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
        # AŞAMA 3.5: DUAL GATE CONSENSUS
        # ─────────────────────────────────────────
        if (
            "dual_gate" in active_stages
            and self.dual_gate_layer
            and self.anomaly_controller
        ):
            try:
                # 1. Deterministik sonucu hazırla (AIAnomalyController beklediği format)
                has_anomaly = (analysis.anomaly_score or 0) > 0.0 or len(
                    analysis.anomaly_flags
                ) > 0
                det_result = AnomalyResult(
                    has_anomaly=has_anomaly,
                    triggered_rules=[
                        RuleIndicator(value=flag) for flag in analysis.anomaly_flags
                    ],
                    anomaly_score=analysis.anomaly_score or 0.0,
                    confidence=analysis.anomaly_confidence or 0.0,
                )

                # 2. Sentence nesnesi oluştur
                sentence = Sentence(
                    id=analysis.sentence_id or analysis.id,
                    text=analysis.source_text,
                    speaker_id=analysis.speaker_id,
                    segment_id=analysis.segment_id,
                )

                # 3. AI ile Doğrula
                context_window: list[Sentence] = []
                dual_gate_config = config.get("dual_gate", {})
                window_size = dual_gate_config.get("context_window_size", 5)

                if window_size > 0 and historical_analyses:
                    for hist in historical_analyses[-window_size:]:
                        context_window.append(
                            Sentence(
                                id=hist.sentence_id or hist.id,
                                text=hist.source_text,
                                speaker_id=hist.speaker_id,
                                segment_id=hist.segment_id,
                            )
                        )

                ai_validation = await self.anomaly_controller.validate(
                    sentence=sentence,
                    deterministic_result=det_result,
                    context_sentences=context_window,
                )

                # 4. Consensus Kararını Al
                consensus = self.dual_gate_layer.decide(
                    deterministic=det_result,
                    ai_validation=ai_validation,
                )

                # 5. HITL Yönlendirme (mevcut mekanizmayı log ile simüle et)
                if consensus.send_to_hitl:
                    logger.warning(
                        f"[HITL QUEUE] Sentence {sentence.id} queued. Trigger: CONSENSUS_ANOMALY. Level: {consensus.level.value}. Reason: {consensus.final_reasoning}"
                    )

                # 6. Sonucu Analysis'e yaz (immutable copy)
                analysis = analysis.model_copy(
                    update={
                        "coherence_score": consensus.coherence_score,
                        "consensus_result": consensus,
                    }
                )
            except Exception as e:
                errors.append(f"[DUAL_GATE] {e}")
                logger.error(f"DualGateConsensusLayer başarısız: {e}")

        # ─────────────────────────────────────────
        # AŞAMA 4: FINALIZE
        # ─────────────────────────────────────────
        if "finalize" in active_stages and self.finalize_stage:
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
