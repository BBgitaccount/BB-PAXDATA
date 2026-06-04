# tests/unit/application/test_lazy_ai_evaluation.py
"""
Faz 2.2 Lazy AI Evaluation — Birim Testleri

CollectStage'in iki aşamalı (Phase 1 Local / Phase 2 Heavy) çalışmasını
ve deterministic risk skoru bazlı bypass mantığını doğrular.
Tüm bağımlılıklar mock'lanır; gerçek AI/NLP çağrısı yapılmaz.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bb_paxdata.application.pipeline.stages.collect_stage import CollectStage
from bb_paxdata.domain.enums.signal_type import SignalType
from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.domain.models.risk_signal import RiskSignal
from bb_paxdata.domain.services.risk_scoring import DeterministicRiskScorer, RiskFormula

# ───────────────────────────────────────────────────────────────────
# HELPERS — Mock factory
# ───────────────────────────────────────────────────────────────────


def _make_risk_signal(credibility: float, escalation: float = 1.0) -> RiskSignal:
    return RiskSignal(
        signal_text="test signal",
        signal_start=0,
        signal_end=11,
        signal_type=SignalType.RED_LINE,
        credibility_score=credibility,
        escalation_multiplier=escalation,
        sentence_id="test-s0",
    )


def _build_collect_stage(
    risk_signals: tuple = (),
    negation_cues: tuple = (),
    ai_result: AIAnalysisResult | None = None,
    ai_call_track: list | None = None,
) -> CollectStage:
    """
    Tüm servisleri mock'layarak minimalist bir CollectStage oluşturur.
    `ai_call_track` listesi verilirse, analyze() çağrıldığında içine 1 eklenir.
    """
    if ai_result is None:
        ai_result = AIAnalysisResult(
            prompt_version="real@v1",
            sentiment_score=-0.8,
            risk_score=0.9,
        )

    async def _mock_analyze(
        text, *, prompt_id=None, forced_version=None, language=None
    ):
        if ai_call_track is not None:
            ai_call_track.append(1)
        return ai_result

    mock_ai = MagicMock()
    mock_ai.analyze = AsyncMock(side_effect=_mock_analyze)
    mock_ai.increment_bypass = MagicMock()

    mock_ner = MagicMock()
    mock_ner.extract = AsyncMock(return_value={"entities": []})

    mock_tokenizer = MagicMock()
    mock_tokenizer.tokenize = AsyncMock(return_value={"sentences": ["test sentence"]})

    mock_negation = MagicMock()
    mock_negation.detect = AsyncMock(return_value=negation_cues)

    mock_risk = MagicMock()
    mock_risk.detect = AsyncMock(return_value=risk_signals)

    mock_power = MagicMock()
    mock_power.calculate = AsyncMock(return_value=None)

    mock_lexicon = MagicMock()
    mock_lexicon.detect_cues = AsyncMock(return_value=[])

    mock_stance = MagicMock()
    mock_stance.calculate = AsyncMock(return_value=0.3)

    mock_engagement = MagicMock()
    mock_engagement.score = AsyncMock(return_value=0.5)

    mock_country_collector = MagicMock()
    mock_country_result = MagicMock()
    mock_country_result.succeeded = True
    mock_country_result.references = ()
    mock_country_collector.collect = AsyncMock(return_value=mock_country_result)

    mock_topic = MagicMock()
    mock_topic.extract_topics = AsyncMock(return_value=None)

    mock_frame_pipeline = MagicMock()
    mock_frame_pipeline.analyze = AsyncMock(return_value=None)

    mock_episodic = MagicMock()
    mock_episodic.classify = AsyncMock(return_value=None)

    mock_frame_assembler = MagicMock()
    mock_frame_assembler.assemble_frame_salience = AsyncMock(return_value=None)

    return CollectStage(
        ner_service=mock_ner,
        tokenizer_service=mock_tokenizer,
        ai_analyst=mock_ai,
        country_collector=mock_country_collector,
        negation_detector=mock_negation,
        risk_detector=mock_risk,
        power_calculator=mock_power,
        topic_modeling_service=mock_topic,
        frame_pipeline=mock_frame_pipeline,
        lexicon_service=mock_lexicon,
        episodic_classifier=mock_episodic,
        frame_assembler=mock_frame_assembler,
        stance_calculator=mock_stance,
        engagement_scorer=mock_engagement,
    )


# ───────────────────────────────────────────────────────────────────
# DeterministicRiskScorer — Birim Testleri
# ───────────────────────────────────────────────────────────────────


class TestDeterministicRiskScorer:
    def test_empty_signals_returns_zero(self) -> None:
        score = DeterministicRiskScorer.calculate([], formula=RiskFormula.MAX)
        assert score == 0.0

    def test_max_formula_returns_highest_signal(self) -> None:
        signals = [
            _make_risk_signal(credibility=0.4, escalation=1.0),  # 0.4
            _make_risk_signal(credibility=0.8, escalation=1.5),  # 1.2 → capped later
            _make_risk_signal(credibility=0.6, escalation=1.2),  # 0.72
        ]
        score = DeterministicRiskScorer.calculate(
            signals, formula=RiskFormula.MAX, negation_dampening=0.0
        )
        assert score == pytest.approx(0.8 * 1.5, rel=1e-4)

    def test_weighted_avg_formula(self) -> None:
        signals = [
            _make_risk_signal(credibility=0.4, escalation=1.0),  # 0.4
            _make_risk_signal(credibility=0.6, escalation=1.0),  # 0.6
        ]
        score = DeterministicRiskScorer.calculate(
            signals, formula=RiskFormula.WEIGHTED_AVG, negation_dampening=0.0
        )
        assert score == pytest.approx(0.5, rel=1e-4)

    def test_sum_formula_capped_at_one(self) -> None:
        signals = [
            _make_risk_signal(credibility=0.8, escalation=1.5),  # 1.2 → capped to 1.0
            _make_risk_signal(credibility=0.7, escalation=1.5),  # 1.05
        ]
        score = DeterministicRiskScorer.calculate(
            signals, formula=RiskFormula.SUM, negation_dampening=0.0
        )
        # sum = 1.2 + 1.05 = 2.25 → min(2.25, 1.0) = 1.0
        assert score == pytest.approx(1.0, rel=1e-4)

    def test_negation_dampening_reduces_score(self) -> None:
        signals = [_make_risk_signal(credibility=1.0, escalation=1.0)]
        score_no_dampening = DeterministicRiskScorer.calculate(
            signals, formula=RiskFormula.MAX, negation_dampening=0.0
        )
        score_with_dampening = DeterministicRiskScorer.calculate(
            signals, formula=RiskFormula.MAX, negation_dampening=0.3
        )
        assert score_with_dampening < score_no_dampening
        assert score_with_dampening == pytest.approx(0.7, rel=1e-4)

    def test_full_dampening_zeroes_score(self) -> None:
        signals = [_make_risk_signal(credibility=1.0, escalation=2.0)]
        score = DeterministicRiskScorer.calculate(
            signals, formula=RiskFormula.MAX, negation_dampening=1.0
        )
        assert score == pytest.approx(0.0, abs=1e-6)


# ───────────────────────────────────────────────────────────────────
# CollectStage — Lazy AI Bypass Testleri
# ───────────────────────────────────────────────────────────────────


class TestCollectStageLazyAIEvaluation:
    """
    Phase 1 / Phase 2 ayrımını ve bypass mantığını test eder.
    Gerçek LLM/servis çağrısı yoktur.
    """

    @pytest.mark.asyncio
    async def test_low_risk_bypasses_ai(self) -> None:
        """
        Risk sinyali olmayan (sıfır risk skoru) metin için AI bypass edilmeli.
        CollectResult.raw_ai.prompt_version == 'bypassed' olmalı.
        """
        ai_calls: list = []
        stage = _build_collect_stage(risk_signals=(), ai_call_track=ai_calls)

        result = await stage.run(
            text="This is a routine diplomatic exchange.",
            panel_id="p-001",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        assert len(ai_calls) == 0, "AI hiç çağrılmamalıydı"
        assert result.raw_ai is not None
        assert result.raw_ai.prompt_version == "bypassed"
        assert result.raw_ai.error is not None
        assert "Bypassed" in result.raw_ai.error

    @pytest.mark.asyncio
    async def test_high_risk_triggers_ai(self) -> None:
        """
        Yüksek risk skoru (threshold üzeri) olan cümlelerde AI çağrılmalı.
        """
        high_risk_signals = (
            _make_risk_signal(
                credibility=0.9, escalation=1.5
            ),  # score: 1.35 → 1.0 after max
        )
        ai_calls: list = []
        expected_result = AIAnalysisResult(
            prompt_version="real@v1",
            sentiment_score=-0.9,
            risk_score=0.95,
        )
        stage = _build_collect_stage(
            risk_signals=high_risk_signals,
            ai_call_track=ai_calls,
            ai_result=expected_result,
        )

        result = await stage.run(
            text="We will not tolerate this unacceptable threat on our borders.",
            panel_id="p-002",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        assert len(ai_calls) == 1, "AI tam olarak bir kere çağrılmalıydı"
        assert result.raw_ai.prompt_version == "real@v1"

    @pytest.mark.asyncio
    async def test_threshold_boundary_exactly_at_threshold_triggers_ai(self) -> None:
        """
        Skor eşiğe tam eşit olduğunda (score == threshold) AI çağrılmalı.
        Bypass koşulu: score < threshold (strict less than).
        """
        # Skor = 0.5 * 1.0 = 0.5 (threshold'a eşit)
        signals = (_make_risk_signal(credibility=0.5, escalation=1.0),)
        ai_calls: list = []
        stage = _build_collect_stage(risk_signals=signals, ai_call_track=ai_calls)

        result = await stage.run(
            text="Diplomatic tension is rising.",
            panel_id="p-003",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        # score (0.5) == threshold (0.5) → NOT < threshold → AI çalışmalı
        assert len(ai_calls) == 1
        assert result.raw_ai.prompt_version != "bypassed"

    @pytest.mark.asyncio
    async def test_threshold_boundary_just_below_threshold_bypasses_ai(self) -> None:
        """
        Skor eşiğin tam altında olduğunda bypass tetiklenmeli.
        """
        # Skor = 0.49 * 1.0 = 0.49 < 0.5 threshold
        signals = (_make_risk_signal(credibility=0.49, escalation=1.0),)
        ai_calls: list = []
        stage = _build_collect_stage(risk_signals=signals, ai_call_track=ai_calls)

        result = await stage.run(
            text="Minor diplomatic discussion.",
            panel_id="p-004",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        assert len(ai_calls) == 0
        assert result.raw_ai.prompt_version == "bypassed"

    @pytest.mark.asyncio
    async def test_negation_dampening_can_flip_decision(self) -> None:
        """
        Negation bulunduğunda risk skoru %30 azalır ve bypass tetiklenebilir.
        Başlangıçta threshold üzerinde olan skor, negation sonrası altında kalmalı.
        """
        from bb_paxdata.domain.enums.negation_type import NegationType
        from bb_paxdata.domain.models.negation_cue import NegationCue

        # Skor = 0.6 * 1.0 = 0.6 (threshold 0.5 üzeri → AI olmalı)
        # Negation dampening 0.3 → 0.6 * (1-0.3) = 0.42 < 0.5 → bypass
        signals = (_make_risk_signal(credibility=0.6, escalation=1.0),)
        negation_cues = (
            NegationCue(
                cue_text="not",
                cue_start=0,
                cue_end=3,
                negation_type=NegationType.SURFACE,
                sentence_id="p-005",
            ),
        )

        ai_calls: list = []
        stage = _build_collect_stage(
            risk_signals=signals,
            negation_cues=negation_cues,
            ai_call_track=ai_calls,
        )

        result = await stage.run(
            text="This is not a threat.",
            panel_id="p-005",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        assert len(ai_calls) == 0, "Negation dampening bypass'a yol açmalıydı"
        assert result.raw_ai.prompt_version == "bypassed"

    @pytest.mark.asyncio
    async def test_bypass_triggers_telemetry(self) -> None:
        """
        Bypass gerçekleştiğinde LimitedAIAnalyst.increment_bypass() çağrılmalı.
        """
        stage = _build_collect_stage(risk_signals=())

        await stage.run(
            text="Routine diplomatic update.",
            panel_id="p-006",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        stage._ai_analyst.increment_bypass.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_bypass_no_telemetry(self) -> None:
        """
        Bypass gerçekleşmediğinde increment_bypass() çağrılmamalı.
        """
        high_signals = (_make_risk_signal(credibility=0.9, escalation=1.5),)
        stage = _build_collect_stage(risk_signals=high_signals)

        await stage.run(
            text="We will not tolerate this threat.",
            panel_id="p-007",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        stage._ai_analyst.increment_bypass.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_threshold_always_triggers_ai(self) -> None:
        """
        Threshold 0.0 ise skor her zaman >= 0.0 olacağı için AI hep çalışmalı.
        """
        ai_calls: list = []
        # Sıfır risk sinyalı bile olsa skor (0.0) == threshold (0.0) → AI çalışmalı
        stage = _build_collect_stage(risk_signals=(), ai_call_track=ai_calls)

        await stage.run(
            text="Neutral statement.",
            panel_id="p-008",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.0,
        )

        assert len(ai_calls) == 1

    @pytest.mark.asyncio
    async def test_very_high_threshold_always_bypasses(self) -> None:
        """
        Threshold 2.0 ise maksimum skor bile (1.0 veya 2.0) < 2.05 olacağı için her zaman bypass.
        """
        high_signals = (_make_risk_signal(credibility=1.0, escalation=2.0),)
        ai_calls: list = []
        stage = _build_collect_stage(risk_signals=high_signals, ai_call_track=ai_calls)

        result = await stage.run(
            text="We will retaliate with full force.",
            panel_id="p-009",
            speaker_country="TR",
            lazy_ai_risk_threshold=2.05,
        )

        assert len(ai_calls) == 0
        assert result.raw_ai.prompt_version == "bypassed"

    @pytest.mark.asyncio
    async def test_bypass_result_has_no_frame_or_topic(self) -> None:
        """
        Bypass sonucunda frame_detection, topic_result ve frame_salience None olmalı.
        """
        stage = _build_collect_stage(risk_signals=())

        result = await stage.run(
            text="Routine diplomatic meeting.",
            panel_id="p-010",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        assert result.frame_detection is None
        assert result.topic_result is None
        assert result.frame_salience is None
        assert result.llm_position is None
        assert result.semantic_shift is None

    @pytest.mark.asyncio
    async def test_phase1_results_always_present(self) -> None:
        """
        Bypass durumunda bile Phase 1 (NER, tokenizer, risk_signals) sonuçları dolu olmalı.
        """
        signals = ()  # low risk → bypass
        stage = _build_collect_stage(risk_signals=signals)

        result = await stage.run(
            text="A routine diplomatic message.",
            panel_id="p-011",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        # Phase 1 çıktıları her zaman mevcut olmalı
        assert result.raw_ner is not None
        assert result.raw_tokenizer is not None
        assert result.stance_density is not None
        assert result.engagement_score is not None

    @pytest.mark.asyncio
    async def test_weighted_avg_formula_via_parameter(self) -> None:
        """
        `lazy_ai_risk_formula='weighted_avg'` parametresiyle skor hesaplanmalı.
        """
        # weighted_avg ile skor = (0.3 + 0.3) / 2 = 0.3 < 0.5 → bypass
        signals = (
            _make_risk_signal(credibility=0.3, escalation=1.0),
            _make_risk_signal(credibility=0.3, escalation=1.0),
        )
        ai_calls: list = []
        stage = _build_collect_stage(risk_signals=signals, ai_call_track=ai_calls)

        result = await stage.run(
            text="Some diplomatic language.",
            panel_id="p-012",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
            lazy_ai_risk_formula="weighted_avg",
        )

        assert len(ai_calls) == 0
        assert result.raw_ai.prompt_version == "bypassed"

    @pytest.mark.asyncio
    async def test_errors_are_empty_on_clean_bypass(self) -> None:
        """
        Temiz bir bypass işleminde hata listesi boş olmalı.
        """
        stage = _build_collect_stage(risk_signals=())

        result = await stage.run(
            text="A peaceful statement.",
            panel_id="p-013",
            speaker_country="TR",
            lazy_ai_risk_threshold=0.5,
        )

        assert result.errors == []


# ───────────────────────────────────────────────────────────────────
# LimitedAIAnalyst — Telemetri Testleri
# ───────────────────────────────────────────────────────────────────


class TestLimitedAIAnalystBypassTracking:
    def test_increment_bypass_increases_count(self) -> None:
        from unittest.mock import MagicMock

        from bb_paxdata.infrastructure.nlp.limited_ai_analyst import LimitedAIAnalyst

        mock_delegate = MagicMock()
        analyst = LimitedAIAnalyst(delegate=mock_delegate, limit=5)

        assert analyst.get_bypass_count() == 0
        analyst.increment_bypass()
        assert analyst.get_bypass_count() == 1
        analyst.increment_bypass()
        analyst.increment_bypass()
        assert analyst.get_bypass_count() == 3

    def test_bypass_count_in_usage_summary(self) -> None:
        from unittest.mock import MagicMock

        from bb_paxdata.infrastructure.nlp.limited_ai_analyst import LimitedAIAnalyst

        mock_delegate = MagicMock()
        analyst = LimitedAIAnalyst(delegate=mock_delegate, limit=10)

        analyst.increment_bypass()
        analyst.increment_bypass()

        summary = analyst.get_usage_summary()
        assert "bypassed_analyze_calls" in summary
        assert summary["bypassed_analyze_calls"] == 2

    def test_bypass_count_is_thread_safe(self) -> None:
        """Thread güvenliğini doğrular: 100 thread'den 100 bypass çağrısı."""
        import threading
        from unittest.mock import MagicMock

        from bb_paxdata.infrastructure.nlp.limited_ai_analyst import LimitedAIAnalyst

        mock_delegate = MagicMock()
        analyst = LimitedAIAnalyst(delegate=mock_delegate, limit=50)

        def call_bypass() -> None:
            analyst.increment_bypass()

        threads = [threading.Thread(target=call_bypass) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert analyst.get_bypass_count() == 100

    def test_efficiency_ratio_in_summary(self) -> None:
        """Bypass oranı (efficiency_ratio) doğru hesaplanmalı."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from bb_paxdata.infrastructure.nlp.limited_ai_analyst import LimitedAIAnalyst

        mock_delegate = MagicMock()
        mock_delegate.analyze = AsyncMock(
            return_value=AIAnalysisResult(prompt_version="real@v1")
        )
        analyst = LimitedAIAnalyst(delegate=mock_delegate, limit=10)

        # 4 analyze çağrısı yap
        async def _run():
            analyst.begin_sentence()
            await analyst.analyze("text 1")
            analyst.begin_sentence()
            await analyst.analyze("text 2")
            analyst.begin_sentence()
            await analyst.analyze("text 3")
            analyst.begin_sentence()
            await analyst.analyze("text 4")

        asyncio.run(_run())

        # 2 bypass ekle
        analyst.increment_bypass()
        analyst.increment_bypass()

        summary = analyst.get_usage_summary()
        # efficiency_ratio = bypassed / total = 2 / 4 = 0.5
        assert summary["efficiency_ratio"] == pytest.approx(0.5, rel=1e-4)
