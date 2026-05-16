# src/bb_paxdata/application/pipeline/stages/collect_stage.py
"""
Pipeline COLLECT aşaması.
Tüm alt-servisleri paralel (asyncio.gather) çalıştırır.
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import TYPE_CHECKING, Any, cast

import structlog
from bb_paxdata.application.pipeline.models.collect_result import (
    CollectResult,
    CountryCollectResult,
)
from bb_paxdata.domain.models.negation_cue import NegationCue
from bb_paxdata.domain.models.power_index import PowerIndex
from bb_paxdata.domain.models.risk_signal import RiskSignal
from bb_paxdata.domain.models.segment import Segment

if TYPE_CHECKING:
    from bb_paxdata.application.pipeline.frame.episodic_themetic_classifier import (
        EpisodicThematicClassifier,
    )
    from bb_paxdata.application.pipeline.frame.frame_assembler import FrameAssembler
    from bb_paxdata.application.pipeline.stages.country_reference_collector import (
        CountryReferenceCollector,
    )
    from bb_paxdata.domain.models.country_reference import CountryReference
    from bb_paxdata.domain.models.dki import SegmentWindow
    from bb_paxdata.domain.services.negation_detector_protocol import (
        NegationDetectorProtocol,
    )
    from bb_paxdata.domain.services.power_calculator_protocol import (
        PowerCalculatorProtocol,
    )
    from bb_paxdata.domain.services.protocols import (
        AIAnalystProtocol,
        LLMPositionEstimator,
        NERServiceProtocol,
        SemanticShiftCalculator,
        TokenizerProtocol,
    )
    from bb_paxdata.domain.services.risk_detector_protocol import (
        RiskSignalDetectorProtocol,
    )
    from bb_paxdata.domain.services.sbi_protocols import (
        EngagementScorerProtocol,
        StanceDensityProtocol,
    )
    from bb_paxdata.domain.services.topic_modeling_protocol import TopicModelingProtocol
    from bb_paxdata.infrastructure.ai.frame_detection.frame_detection_pipeline import (
        FrameDetectionPipeline,
    )
    from bb_paxdata.infrastructure.ai.frame_detection.frame_lexicon_service import (
        FrameLexiconService,
    )

logger = structlog.get_logger(__name__)


class CollectStage:
    def __init__(
        self,
        ner_service: NERServiceProtocol,
        tokenizer_service: TokenizerProtocol,
        ai_analyst: AIAnalystProtocol,
        country_collector: CountryReferenceCollector,
        negation_detector: NegationDetectorProtocol,
        risk_detector: RiskSignalDetectorProtocol,
        power_calculator: PowerCalculatorProtocol,
        topic_modeling_service: TopicModelingProtocol,
        frame_pipeline: FrameDetectionPipeline,
        lexicon_service: FrameLexiconService,
        episodic_classifier: EpisodicThematicClassifier,
        frame_assembler: FrameAssembler,
        stance_calculator: StanceDensityProtocol,
        engagement_scorer: EngagementScorerProtocol,
        llm_position_estimator: LLMPositionEstimator | None = None,
        semantic_shift_calculator: SemanticShiftCalculator | None = None,
    ) -> None:
        self._ner_service = ner_service
        self._tokenizer_service = tokenizer_service
        self._ai_analyst = ai_analyst
        self._country_collector = country_collector
        self._negation_detector = negation_detector
        self._risk_detector = risk_detector
        self._power_calculator = power_calculator
        self._topic_modeling_service = topic_modeling_service
        self._frame_pipeline = frame_pipeline
        self._lexicon_service = lexicon_service
        self._episodic_classifier = episodic_classifier
        self._frame_assembler = frame_assembler
        self._stance_calculator = stance_calculator
        self._engagement_scorer = engagement_scorer
        self._llm_position_estimator = llm_position_estimator
        self._semantic_shift_calculator = semantic_shift_calculator

    async def run(
        self,
        text: str,
        panel_id: str,
        speaker_country: str,
        speaker_power_level: float = 0.5,
        language: str | None = None,
        historical_segments: list[SegmentWindow] | None = None,
    ) -> CollectResult:
        """
        Tüm servisleri paralel çalıştırır.
        Hataları toplar ama pipeline'ı durdurmaz (graceful degradation).
        """
        logger.info("collect_stage.started", panel_id=panel_id, language=language)

        async def _wrap_none(coro_or_none: Coroutine[Any, Any, Any] | None) -> Any:
            if coro_or_none is None:
                return None
            return await coro_or_none

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
            self._negation_detector.detect(text, sentence_id=panel_id),
            self._risk_detector.detect(text, sentence_id=panel_id),
            self._power_calculator.calculate(
                text, speaker_id=speaker_country, segment_id=panel_id
            ),
            self._frame_pipeline.analyze(Segment(id=panel_id, text=text)),
            self._lexicon_service.detect_cues(text),
            self._episodic_classifier.classify(Segment(id=panel_id, text=text)),
            self._stance_calculator.calculate(
                text.split(), speaker_country
            ),  # Simple split for now
            self._engagement_scorer.score(
                [text], speaker_country
            ),  # One sentence for now
            _wrap_none(
                self._llm_position_estimator.estimate_position(text, "general_policy")
                if self._llm_position_estimator
                else None
            ),
            _wrap_none(
                self._semantic_shift_calculator.calculate_shift(
                    SegmentWindow(
                        segment_ids=[panel_id], texts=[text], speaker_id=speaker_country
                    ),
                    historical_segments or [],
                )
                if self._semantic_shift_calculator and historical_segments is not None
                else None
            ),
            return_exceptions=True,
        )

        errors: list[str] = []

        # 1. NER Result
        raw_ner = results[0]
        if isinstance(raw_ner, BaseException):
            errors.append(f"[COLLECT/NER] {raw_ner}")
            logger.warning("collect_stage.ner_failed", error=str(raw_ner))
            raw_ner = {}
        else:
            raw_ner = cast(dict[str, Any], raw_ner)

        # 2. Tokenizer Result
        raw_tokenizer = results[1]
        if isinstance(raw_tokenizer, BaseException):
            errors.append(f"[COLLECT/TOKENIZER] {raw_tokenizer}")
            logger.warning("collect_stage.tokenizer_failed", error=str(raw_tokenizer))
            raw_tokenizer = {}
        else:
            raw_tokenizer = cast(dict[str, Any], raw_tokenizer)

        # 3. AI Result
        raw_ai = results[2]
        if isinstance(raw_ai, BaseException):
            errors.append(f"[COLLECT/AI] {raw_ai}")
            logger.error("collect_stage.ai_failed", error=str(raw_ai))
            from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult

            raw_ai = AIAnalysisResult(prompt_version="unknown@error", error=str(raw_ai))
        else:
            from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult

            raw_ai = cast(AIAnalysisResult, raw_ai)

        # 4. Country Result
        country_result = results[3]
        country_references: tuple[CountryReference, ...] = ()
        if isinstance(country_result, BaseException):
            errors.append(f"[COLLECT/COUNTRY] {country_result}")
            logger.warning("collect_stage.country_failed", error=str(country_result))
        else:
            country_result = cast(CountryCollectResult, country_result)
            if country_result.succeeded:
                country_references = country_result.references

        # 5. Negation Result
        negation_cues: Sequence[NegationCue] = ()
        raw_negation = results[4]
        if isinstance(raw_negation, BaseException):
            errors.append(f"[COLLECT/NEGATION] {raw_negation}")
        else:
            negation_cues = cast(Sequence[NegationCue], raw_negation)

        # 6. Risk Result
        risk_signals: Sequence[RiskSignal] = ()
        raw_risk = results[5]
        if isinstance(raw_risk, BaseException):
            errors.append(f"[COLLECT/RISK] {raw_risk}")
        else:
            risk_signals = cast(Sequence[RiskSignal], raw_risk)

        # 7. Power Result
        power_indices: dict[str, PowerIndex] = {}
        raw_power = results[6]
        if isinstance(raw_power, BaseException):
            errors.append(f"[COLLECT/POWER] {raw_power}")
        else:
            power_idx = cast(PowerIndex, raw_power)
            power_indices[speaker_country] = power_idx

        # 8. YENİ: Topic Modeling (Tokenizer çıktılarını beklemeli)
        topic_result = None
        if raw_tokenizer and "sentences" in raw_tokenizer:
            from bb_paxdata.domain.models.sentence import Sentence

            # Tokenizer'dan gelen cümleleri Segment nesnesine sarıyoruz
            # Not: Gerçek dünyada burada daha karmaşık bir segmentasyon olabilir (ör: her 5 cümle bir segment)
            sentences = [
                Sentence(id=f"{panel_id}-s{i}", text=s_text)
                for i, s_text in enumerate(raw_tokenizer["sentences"])
            ]

            # Tek bir segment olarak ele alıyoruz (şimdilik)
            main_segment = Segment(
                id=panel_id,
                panel_id=panel_id,
                sentences=sentences,
            )

            try:
                topic_result = await self._topic_modeling_service.extract_topics(
                    segments=[main_segment],
                    language=language or "en",
                    min_topic_size=2,  # Küçük metinler için
                )
            except Exception as e:
                errors.append(f"[COLLECT/TOPIC] {e}")
                logger.warning("collect_stage.topic_modeling_failed", error=str(e))

        # 9. Frame Detection Result
        frame_detection = results[7]
        if isinstance(frame_detection, BaseException):
            errors.append(f"[COLLECT/FRAME] {frame_detection}")
            logger.error(
                "collect_stage.frame_detection_failed", error=str(frame_detection)
            )
            frame_detection = None
        else:
            from bb_paxdata.domain.models.frame_annotation import FrameDetectionResult

            frame_detection = cast(FrameDetectionResult, frame_detection)

        # 10. Frame Cues Result
        frame_cues = results[8]
        if isinstance(frame_cues, BaseException):
            errors.append(f"[COLLECT/CUES] {frame_cues}")
            logger.warning("collect_stage.cues_failed", error=str(frame_cues))
            frame_cues = []
        else:
            from bb_paxdata.domain.models.frame_annotation import CueMatch

            frame_cues = cast(list[CueMatch], frame_cues)

        # 11. Episodic/Thematic Result
        dominant_iyengar = results[9]
        if isinstance(dominant_iyengar, BaseException):
            errors.append(f"[COLLECT/IYENGAR] {dominant_iyengar}")
            logger.warning("collect_stage.iyengar_failed", error=str(dominant_iyengar))
            dominant_iyengar = None
        else:
            from bb_paxdata.domain.enums.frame_type import FrameType

            dominant_iyengar = cast(FrameType, dominant_iyengar)

        # 12. Stance Density Result
        stance_density = results[10]
        if isinstance(stance_density, BaseException):
            errors.append(f"[COLLECT/STANCE] {stance_density}")
            stance_density = 0.0

        # 13. Engagement Score Result
        engagement_score = results[11]
        if isinstance(engagement_score, BaseException):
            errors.append(f"[COLLECT/ENGAGEMENT] {engagement_score}")
            engagement_score = 0.0

        # 14. LLM Position Result
        llm_position = results[12] if len(results) > 12 else None
        if isinstance(llm_position, BaseException):
            errors.append(f"[COLLECT/LLM_POS] {llm_position}")
            llm_position = None

        # 15. Semantic Shift Result
        semantic_shift = results[13] if len(results) > 13 else None
        if isinstance(semantic_shift, BaseException):
            errors.append(f"[COLLECT/SHIFT] {semantic_shift}")
            semantic_shift = None

        # 12. Frame Salience Assembly (Requires frame_detection and frame_cues)
        frame_salience = None
        if frame_detection and frame_cues is not None:
            try:
                frame_salience = await self._frame_assembler.assemble_frame_salience(
                    segment=Segment(id=panel_id, text=text),
                    annotations=frame_detection.frame_annotations,
                    cues=frame_cues,
                )
            except Exception as e:
                errors.append(f"[COLLECT/SALIENCE] {e}")
                logger.error("collect_stage.salience_assembly_failed", error=str(e))

        return CollectResult(
            raw_ner=raw_ner,
            raw_tokenizer=raw_tokenizer,
            raw_ai=raw_ai,
            country_references=country_references,
            negation_cues=negation_cues,
            risk_signals=risk_signals,
            power_indices=power_indices,
            topic_result=topic_result,
            frame_detection=frame_detection,
            frame_cues=frame_cues,
            frame_salience=frame_salience,
            stance_density=stance_density,
            engagement_score=engagement_score,
            llm_position=llm_position,
            semantic_shift=semantic_shift,
            errors=errors,
        )
