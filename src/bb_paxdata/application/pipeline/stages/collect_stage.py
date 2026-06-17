# src/bb_paxdata/application/pipeline/stages/collect_stage.py
"""
Pipeline COLLECT aşaması.
Tüm alt-servisleri paralel/iki aşamalı (Phase 1 Local ve Phase 2 Heavy) çalıştırır.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

import structlog
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.domain.services.risk_scoring import (
    DeterministicRiskScorer,
    RiskFormula,
)
from bb_paxdata.application.pipeline.models.collect_result import (
    CollectResult,
    CountryCollectResult,
)

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.appraisal_vector import (
        AppraisalVector,
    )
    from bb_paxdata.application.domain.models.dki import SegmentWindow
    from bb_paxdata.application.domain.services.negation_detector_protocol import (
        NegationDetectorProtocol,
    )
    from bb_paxdata.application.domain.services.power_calculator_protocol import (
        PowerCalculatorProtocol,
    )
    from bb_paxdata.application.domain.services.protocols import (
        AIAnalystProtocol,
        LLMPositionEstimator,
        NERServiceProtocol,
        SemanticShiftCalculator,
        TokenizerProtocol,
    )
    from bb_paxdata.application.domain.services.risk_detector_protocol import (
        RiskSignalDetectorProtocol,
    )
    from bb_paxdata.application.domain.services.sbi_protocols import (
        EngagementScorerProtocol,
        StanceDensityProtocol,
    )
    from bb_paxdata.application.domain.services.topic_modeling_protocol import (
        TopicModelingProtocol,
    )
    from bb_paxdata.application.pipeline.frame.episodic_themetic_classifier import (
        EpisodicThematicClassifier,
    )
    from bb_paxdata.application.pipeline.frame.frame_assembler import FrameAssembler
    from bb_paxdata.application.pipeline.stages.country_reference_collector import (
        CountryReferenceCollector,
    )
    from bb_paxdata.application.protocols import AppraisalServiceProtocol
    from bb_paxdata.infrastructure.ai.frame_detection.frame_detection_pipeline import (
        FrameDetectionPipeline,
    )
    from bb_paxdata.infrastructure.ai.frame_detection.frame_lexicon_service import (
        FrameLexiconService,
    )

logger = structlog.get_logger(__name__)


class ExecutionPhase(str, Enum):
    LOCAL = "local"
    HEAVY = "heavy"


@dataclass
class _LocalResults:
    """Phase 1 çıktılarının tip-güvenli container'ı."""

    ner: dict
    tokenizer: dict
    negation_cues: tuple
    risk_signals: tuple
    power_indices: dict
    frame_cues: list
    stance_density: float
    engagement_score: float
    country_references: tuple
    errors: list[str]
    appraisal_vector: AppraisalVector | None = None


@dataclass
class _HeavyResults:
    """Phase 2 çıktılarının tip-güvenli container'ı."""

    raw_ai: Any
    frame_detection: Any | None
    dominant_iyengar: Any | None
    llm_position: Any | None
    semantic_shift: Any | None
    topic_result: Any | None
    frame_salience: Any | None
    errors: list[str]


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
        appraisal_service: AppraisalServiceProtocol | None = None,
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
        self._appraisal_service = appraisal_service

    async def run(
        self,
        text: str,
        panel_id: str,
        speaker_country: str,
        speaker_power_level: float = 0.5,
        language: str | None = None,
        historical_segments: list[SegmentWindow] | None = None,
        speaker_id: str | None = None,
        sentence_index: int = 0,
        services_config: list[str] | None = None,
        lazy_ai_risk_threshold: float = 0.5,
        lazy_ai_risk_formula: str = "max",
    ) -> CollectResult:
        """
        Tüm servisleri paralel/iki aşamalı çalıştırır.
        Hataları toplar ama pipeline'ı durdurmaz (graceful degradation).
        """
        logger.info(
            "collect_stage.started",
            panel_id=panel_id,
            language=language,
            threshold=lazy_ai_risk_threshold,
        )

        # ── PHASE 1: Local Fast-Path ──
        local = await self._execute_phase_local(
            text=text,
            panel_id=panel_id,
            speaker_country=speaker_country,
            speaker_power_level=speaker_power_level,
            speaker_id=speaker_id,
            sentence_index=sentence_index,
            language=language,
            services_config=services_config,
        )

        # ── DECISION GATE ──
        det_risk_score = self._calculate_deterministic_risk(
            risk_signals=local.risk_signals,
            formula=RiskFormula(lazy_ai_risk_formula),
            negation_cues=local.negation_cues,
        )

        should_bypass_ai = det_risk_score < lazy_ai_risk_threshold

        logger.info(
            "collect_stage.lazy_ai_eval",
            det_risk_score=det_risk_score,
            threshold=lazy_ai_risk_threshold,
            should_bypass=should_bypass_ai,
            formula=lazy_ai_risk_formula,
        )

        # ── PHASE 2: Heavy LLM-Path (Conditional) ──
        if should_bypass_ai:
            heavy = self._build_bypass_results(
                reason=f"det_risk_score ({det_risk_score}) < threshold ({lazy_ai_risk_threshold})"
            )
            # If AI is disabled via config, ensure the status reflects "disabled" instead of "bypassed"
            if services_config is not None and "ai_analyst" not in services_config:
                from bb_paxdata.application.domain.models.ai_analysis import (
                    AIAnalysisResult,
                )

                heavy.raw_ai = AIAnalysisResult(
                    prompt_version="disabled",
                    error="AI analysis is disabled in configuration",
                )
            else:
                self._telemetry_bypass(panel_id=panel_id)
        else:
            heavy = await self._execute_phase_heavy(
                text=text,
                panel_id=panel_id,
                speaker_country=speaker_country,
                language=language,
                historical_segments=historical_segments,
                local_results=local,
                services_config=services_config,
            )

        # ── APPRAISAL DOCUMENT AGGREGATION ──
        # Use the document-level appraisal from Phase 1 (no duplicate calculation)
        appraisal_document = None
        if self._appraisal_service is not None and local.appraisal_vector is not None:
            from bb_paxdata.application.domain.models.appraisal_vector import (
                AppraisalDocumentResult,
            )

            appraisal_document = AppraisalDocumentResult(
                vectors=[(panel_id, local.appraisal_vector)]
            )

        # ── MERGE & RETURN ──
        all_errors = local.errors + heavy.errors

        return CollectResult(
            raw_ner=local.ner,
            raw_tokenizer=local.tokenizer,
            raw_ai=heavy.raw_ai,
            country_references=local.country_references,
            negation_cues=local.negation_cues,
            risk_signals=local.risk_signals,
            power_indices=local.power_indices,
            topic_result=heavy.topic_result,
            frame_detection=heavy.frame_detection,
            frame_cues=local.frame_cues,
            frame_salience=heavy.frame_salience,
            stance_density=local.stance_density,
            engagement_score=local.engagement_score,
            llm_position=heavy.llm_position,
            semantic_shift=heavy.semantic_shift,
            appraisal_vector=local.appraisal_vector,
            appraisal_document=appraisal_document,
            errors=all_errors,
        )

    # ───────────────────────────────────────────────
    # PHASE 1 IMPLEMENTATION
    # ───────────────────────────────────────────────
    async def _execute_phase_local(
        self,
        text: str,
        panel_id: str,
        speaker_country: str,
        speaker_power_level: float,
        speaker_id: str | None,
        sentence_index: int,
        language: str | None,
        services_config: list[str] | None,
    ) -> _LocalResults:
        """Run all CPU-based services concurrently."""

        async def _run(name: str, coro_factory) -> Any:
            if services_config is not None and name not in services_config:
                return None
            try:
                return await coro_factory()
            except Exception as exc:
                return exc

        async def _run_appraisal_coro():
            if self._appraisal_service is None:
                return None
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, self._appraisal_service.analyze, text, panel_id, None, None
            )

        results = await asyncio.gather(
            _run("ner", lambda: self._ner_service.extract(text, language=language)),
            _run(
                "tokenizer",
                lambda: self._tokenizer_service.tokenize(text, language=language),
            ),
            _run(
                "negation_detector",
                lambda: self._negation_detector.detect(text, sentence_id=panel_id),
            ),
            _run(
                "risk_detector",
                lambda: self._risk_detector.detect(text, sentence_id=panel_id),
            ),
            _run(
                "power_calculator",
                lambda: self._power_calculator.calculate(
                    text, speaker_id=speaker_country, segment_id=panel_id
                ),
            ),
            _run("lexicon_service", lambda: self._lexicon_service.detect_cues(text)),
            _run(
                "stance_calculator",
                lambda: self._stance_calculator.calculate(
                    text.split(), speaker_country
                ),
            ),
            _run(
                "engagement_scorer",
                lambda: self._engagement_scorer.score([text], speaker_country),
            ),
            _run(
                "country_collector",
                lambda: self._country_collector.collect(
                    text=text,
                    panel_id=panel_id,
                    speaker_country=speaker_country,
                    speaker_power_level=speaker_power_level,
                    speaker_id=speaker_id,
                    sentence_index=sentence_index,
                ),
            ),
            _run("appraisal_service", _run_appraisal_coro),
            return_exceptions=False,
        )

        raw_ner = self._safe_extract(results[0], {})
        raw_tokenizer = self._safe_extract(results[1], {})

        neg_res = self._safe_extract(results[2], None)
        from bb_paxdata.application.domain.models.negation_cue import NegationResult

        if isinstance(neg_res, NegationResult):
            negation_cues = tuple(neg_res.cues)
        else:
            negation_cues = tuple(neg_res) if neg_res else ()
        risk_signals = self._safe_extract(results[3], ())
        raw_power = self._safe_extract(results[4], None)
        frame_cues = self._safe_extract(results[5], [])
        stance_density = self._safe_extract(results[6], 0.0)
        engagement_score = self._safe_extract(results[7], 0.0)
        country_result = results[8]
        appraisal_vector = self._safe_extract(results[9], None)

        # Error aggregation
        errors = []
        for idx, val in enumerate(results):
            if isinstance(val, BaseException):
                name_map = {
                    0: "NER",
                    1: "TOKENIZER",
                    2: "NEGATION",
                    3: "RISK",
                    4: "POWER",
                    5: "CUES",
                    6: "STANCE",
                    7: "ENGAGEMENT",
                    8: "COUNTRY",
                    9: "APPRAISAL",
                }
                errors.append(f"[COLLECT/{name_map.get(idx, 'LOCAL')}] {val}")

        power_indices = {}
        if raw_power is not None and not isinstance(raw_power, BaseException):
            power_indices[speaker_country] = raw_power

        country_references = ()
        if country_result is not None and not isinstance(country_result, BaseException):
            country_result = cast(CountryCollectResult, country_result)
            if country_result.succeeded:
                country_references = country_result.references

        return _LocalResults(
            ner=raw_ner,
            tokenizer=raw_tokenizer,
            negation_cues=negation_cues,
            risk_signals=risk_signals,
            power_indices=power_indices,
            frame_cues=frame_cues,
            stance_density=stance_density,
            engagement_score=engagement_score,
            country_references=country_references,
            errors=errors,
            appraisal_vector=appraisal_vector,
        )

    # ───────────────────────────────────────────────
    # DECISION LOGIC
    # ───────────────────────────────────────────────
    def _calculate_deterministic_risk(
        self,
        risk_signals: tuple,
        formula: RiskFormula,
        negation_cues: tuple,
    ) -> float:
        """Deterministic risk score for bypass decision."""
        if not risk_signals:
            return 0.0

        negation_dampening = 0.3 if negation_cues else 0.0

        return DeterministicRiskScorer.calculate(
            risk_signals=risk_signals,
            formula=formula,
            negation_dampening=negation_dampening,
        )

    # ───────────────────────────────────────────────
    # BYPASS RESULT BUILDER
    # ───────────────────────────────────────────────
    def _build_bypass_results(self, reason: str) -> _HeavyResults:
        """Construct placeholder results when AI is bypassed."""
        from bb_paxdata.application.domain.models.ai_analysis import AIAnalysisResult

        return _HeavyResults(
            raw_ai=AIAnalysisResult(
                prompt_version="bypassed",
                error=f"Bypassed due to low deterministic risk score. Reason: {reason}",
                sentiment_score=None,
                risk_score=None,
            ),
            frame_detection=None,
            dominant_iyengar=None,
            llm_position=None,
            semantic_shift=None,
            topic_result=None,
            frame_salience=None,
            errors=[],
        )

    def _telemetry_bypass(self, panel_id: str) -> None:
        """Telemetry reporting for bypass events."""
        if hasattr(self._ai_analyst, "increment_bypass"):
            try:
                self._ai_analyst.increment_bypass()
            except Exception:
                logger.warning(
                    "collect_stage.bypass_telemetry_failed", panel_id=panel_id
                )

        logger.info("collect_stage.ai_bypassed", panel_id=panel_id)

    # ───────────────────────────────────────────────
    # PHASE 2 IMPLEMENTATION
    # ───────────────────────────────────────────────
    async def _execute_phase_heavy(
        self,
        text: str,
        panel_id: str,
        speaker_country: str,
        language: str | None,
        historical_segments: list[SegmentWindow] | None,
        local_results: _LocalResults,
        services_config: list[str] | None,
    ) -> _HeavyResults:
        """Run all LLM/AI services concurrently."""
        from bb_paxdata.application.domain.models.ai_analysis import AIAnalysisResult
        from bb_paxdata.application.domain.models.sentence import Sentence

        async def _wrap_none(coro_or_none) -> Any:
            if coro_or_none is None:
                return None
            return await coro_or_none

        async def _run(name: str, coro_factory) -> Any:
            if services_config is not None and name not in services_config:
                return None
            try:
                return await coro_factory()
            except Exception as exc:
                return exc

        # AI/LLM çağrıları (paralel)
        ai_results = await asyncio.gather(
            _run(
                "ai_analyst",
                lambda: self._ai_analyst.analyze(
                    text, language=language, file_id=panel_id
                ),
            ),
            _run(
                "frame_pipeline",
                lambda: self._frame_pipeline.analyze(
                    Segment(
                        id=panel_id,
                        sentences=[Sentence(id=f"{panel_id}-s0", text=text)],
                    )
                ),
            ),
            _run(
                "episodic_classifier",
                lambda: self._episodic_classifier.classify(
                    Segment(
                        id=panel_id,
                        sentences=[Sentence(id=f"{panel_id}-s0", text=text)],
                    )
                ),
            ),
            _run(
                "llm_position_estimator",
                lambda: _wrap_none(
                    self._llm_position_estimator.estimate_position(
                        text, "general_policy"
                    )
                    if self._llm_position_estimator
                    else None
                ),
            ),
            _run(
                "semantic_shift_calculator",
                lambda: _wrap_none(
                    self._semantic_shift_calculator.calculate_shift(
                        SegmentWindow(
                            segment_ids=[panel_id],
                            texts=[text],
                            speaker_id=speaker_country,
                        ),
                        historical_segments or [],
                    )
                    if self._semantic_shift_calculator
                    and historical_segments is not None
                    else None
                ),
            ),
            return_exceptions=False,
        )

        raw_ai = ai_results[0]
        frame_detection = self._safe_extract(ai_results[1], None)
        dominant_iyengar = self._safe_extract(ai_results[2], None)
        llm_position = self._safe_extract(ai_results[3], None)
        semantic_shift = self._safe_extract(ai_results[4], None)

        errors = []

        # AI Analyst error handling
        if isinstance(raw_ai, BaseException):
            errors.append(f"[COLLECT/AI] {raw_ai}")
            raw_ai = AIAnalysisResult(
                prompt_version="unknown@error",
                error=str(raw_ai),
            )
        elif raw_ai is None:
            raw_ai = AIAnalysisResult(
                prompt_version="disabled",
                error="AI analysis is disabled in configuration",
            )
        else:
            raw_ai = cast(AIAnalysisResult, raw_ai)

        # Diğer AI hataları
        for idx, name in [
            (1, "FRAME"),
            (2, "EPISODIC"),
            (3, "LLM_POS"),
            (4, "SEM_SHIFT"),
        ]:
            if isinstance(ai_results[idx], BaseException):
                errors.append(f"[COLLECT/{name}] {ai_results[idx]}")

        # ── Dependent Local Assemblies ──
        # Topic Modeling (Tokenizer bağımlı, local)
        topic_result = None
        if services_config is None or "topic_modeling" in services_config:
            if local_results.tokenizer and "sentences" in local_results.tokenizer:
                sentences = [
                    Sentence(id=f"{panel_id}-s{i}", text=s_text)
                    for i, s_text in enumerate(local_results.tokenizer["sentences"])
                ]
                main_segment = Segment(
                    id=panel_id, panel_id=panel_id, sentences=sentences
                )
                try:
                    topic_result = await self._topic_modeling_service.extract_topics(
                        segments=[main_segment],
                        language=language or "en",
                        min_topic_size=2,
                    )
                except Exception as e:
                    errors.append(f"[COLLECT/TOPIC] {e}")

        # Frame Salience (Frame detection + frame cues bağımlı)
        frame_salience = None
        if services_config is None or "frame_assembler" in services_config:
            if frame_detection and local_results.frame_cues:
                try:
                    frame_salience = (
                        await self._frame_assembler.assemble_frame_salience(
                            segment=Segment(id=panel_id, text=text),
                            annotations=frame_detection.frame_annotations,
                            cues=local_results.frame_cues,
                        )
                    )
                except Exception as e:
                    errors.append(f"[COLLECT/SALIENCE] {e}")

        return _HeavyResults(
            raw_ai=raw_ai,
            frame_detection=frame_detection,
            dominant_iyengar=dominant_iyengar,
            llm_position=llm_position,
            semantic_shift=semantic_shift,
            topic_result=topic_result,
            frame_salience=frame_salience,
            errors=errors,
        )

    # ───────────────────────────────────────────────
    # UTILITIES
    # ───────────────────────────────────────────────
    @staticmethod
    def _safe_extract(value: Any, default: Any) -> Any:
        """Extract value if not exception, else return default."""
        if isinstance(value, BaseException):
            return default
        if value is None:
            return default
        return value
