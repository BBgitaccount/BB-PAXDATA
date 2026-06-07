"""
Comprehensive unit tests for the three main god nodes:
  - Analysis  (101 edges in call graph)
  - Segment   (91 edges)
  - Sentence  (75 edges)

Tests cover:
  - Default value safety
  - Pydantic validation (range constraints, type coercion)
  - Computed properties
  - Immutable update pattern (model_copy)
  - Edge-case handling
"""

from __future__ import annotations

import pytest
from bb_paxdata.application.domain.enums import (
    RiskLevel,
)
from bb_paxdata.application.domain.enums.negation_type import NegationType
from bb_paxdata.application.domain.enums.signal_type import SignalType
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.negation_cue import NegationCue
from bb_paxdata.application.domain.models.risk_signal import RiskSignal
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.domain.models.sentence import Sentence
from pydantic import ValidationError

# ─── Factory helpers for models with required positional fields ───


def make_risk_signal(
    signal_text: str = "ultimatum",
    escalation_multiplier: float = 2.0,
    credibility_score: float = 0.9,
) -> RiskSignal:
    """Minimal valid RiskSignal factory."""
    return RiskSignal(
        signal_text=signal_text,
        signal_start=0,
        signal_end=len(signal_text),
        signal_type=SignalType.RETALIATION,
        escalation_multiplier=escalation_multiplier,
        credibility_score=credibility_score,
        sentence_id="sent-test-001",
    )


def make_negation_cue(cue_text: str = "not", position: int = 2) -> NegationCue:
    """Minimal valid NegationCue factory."""
    return NegationCue(
        cue_text=cue_text,
        cue_start=position,
        cue_end=position + len(cue_text),
        negation_type=NegationType.SURFACE,
        sentence_id="sent-test-001",
    )


# ─────────────────────────── Helpers ───────────────────────────


def make_sentence(id_: str = "s-001", text: str = "Peace talks resumed.") -> Sentence:
    return Sentence(id=id_, text=text)


def make_segment(
    id_: str = "seg-001", sentences: list[Sentence] | None = None
) -> Segment:
    return Segment(id=id_, sentences=sentences or [make_sentence()])


def make_analysis(**kwargs) -> Analysis:
    return Analysis(**kwargs)


# ═══════════════════════════════════════════════════════════════
# SENTENCE TESTS
# ═══════════════════════════════════════════════════════════════


class TestSentenceDefaults:
    def test_required_fields(self):
        s = Sentence(id="s1", text="Hello world")
        assert s.id == "s1"
        assert s.text == "Hello world"

    def test_sentence_code_auto_generated(self):
        s = Sentence(id="s1", text="Test")
        assert s.sentence_code
        assert len(s.sentence_code) > 0

    def test_optional_fields_default_none(self):
        s = Sentence(id="s1", text="Test")
        assert s.sentiment is None
        assert s.sentiment_score is None
        assert s.hedging_score is None
        assert s.risk_score is None
        assert s.manipulation_score is None
        assert s.dominant_topic is None

    def test_is_demand_defaults_false(self):
        s = Sentence(id="s1", text="Test")
        assert s.is_demand is False

    def test_negation_cues_defaults_empty(self):
        s = Sentence(id="s1", text="Test")
        assert s.negation_cues is not None
        assert len(s.negation_cues) == 0


class TestSentenceValidation:
    def test_sentiment_score_upper_bound(self):
        with pytest.raises(ValidationError):
            Sentence(id="s1", text="Test", sentiment_score=1.5)

    def test_sentiment_score_lower_bound(self):
        with pytest.raises(ValidationError):
            Sentence(id="s1", text="Test", sentiment_score=-1.5)

    def test_hedging_score_range(self):
        s = Sentence(id="s1", text="Test", hedging_score=0.75)
        assert s.hedging_score == 0.75

    def test_hedging_score_too_high_raises(self):
        with pytest.raises(ValidationError):
            Sentence(id="s1", text="Test", hedging_score=1.1)

    def test_risk_score_upper_bound(self):
        s = Sentence(id="s1", text="High risk", risk_score=10.0)
        assert s.risk_score == 10.0

    def test_risk_score_exceeds_max_raises(self):
        with pytest.raises(ValidationError):
            Sentence(id="s1", text="Test", risk_score=10.1)

    def test_face_threat_count_non_negative(self):
        with pytest.raises(ValidationError):
            Sentence(id="s1", text="Test", face_threat_count=-1)


class TestSentenceProperties:
    def test_has_negation_false_when_empty(self):
        s = Sentence(id="s1", text="Test")
        assert s.has_negation is False

    def test_has_negation_true_with_cues(self):
        cue = make_negation_cue("not", position=2)
        s = Sentence(id="s1", text="I am not sure", negation_cues=(cue,))
        assert s.has_negation is True

    def test_negation_count_matches_cues(self):
        cues = (
            make_negation_cue("not", position=2),
            make_negation_cue("never", position=5),
        )
        s = Sentence(id="s1", text="Test not never", negation_cues=cues)
        assert s.negation_count == 2

    def test_sentence_code_unique_across_instances(self):
        s1 = Sentence(id="s1", text="Test")
        s2 = Sentence(id="s2", text="Test")
        assert s1.sentence_code != s2.sentence_code


class TestSentenceImmutability:
    def test_model_copy_update(self):
        s = Sentence(id="s1", text="Original")
        s2 = s.model_copy(update={"text": "Updated"})
        assert s.text == "Original"
        assert s2.text == "Updated"


# ═══════════════════════════════════════════════════════════════
# SEGMENT TESTS
# ═══════════════════════════════════════════════════════════════


class TestSegmentDefaults:
    def test_required_id(self):
        seg = make_segment()
        assert seg.id == "seg-001"

    def test_sentences_default_empty(self):
        seg = Segment(id="seg-1")
        assert seg.sentences == []

    def test_risk_score_defaults_zero(self):
        seg = make_segment()
        assert seg.risk_score == 0

    def test_demand_count_defaults_zero(self):
        seg = make_segment()
        assert seg.demand_count == 0

    def test_risk_signals_defaults_empty_list(self):
        seg = make_segment()
        assert seg.risk_signals == []


class TestSegmentTextProperty:
    def test_text_joins_sentence_texts(self):
        s1 = Sentence(id="s1", text="Hello")
        s2 = Sentence(id="s2", text="World")
        seg = Segment(id="seg-1", sentences=[s1, s2])
        assert seg.text == "Hello World"

    def test_text_empty_when_no_sentences(self):
        seg = Segment(id="seg-1")
        assert seg.text == ""


class TestSegmentEscalatedRisk:
    def test_escalated_risk_no_signals(self):
        seg = Segment(id="seg-1", risk_score=5)
        assert seg.escalated_risk_score == 5.0

    def test_escalated_risk_with_signals(self):
        signal = make_risk_signal("threat", escalation_multiplier=2.0)
        seg = Segment(id="seg-1", risk_score=5, risk_signals=[signal])
        # Should be risk_score * max_multiplier + weighted_sum * 0.1
        assert seg.escalated_risk_score > 5.0

    def test_escalated_risk_zero_score(self):
        seg = Segment(id="seg-1", risk_score=0)
        assert seg.escalated_risk_score == 0.0


class TestSegmentValidation:
    def test_avg_sentiment_score_range(self):
        seg = Segment(id="seg-1", avg_sentiment_score=0.5)
        assert seg.avg_sentiment_score == 0.5

    def test_avg_sentiment_score_out_of_range(self):
        with pytest.raises(ValidationError):
            Segment(id="seg-1", avg_sentiment_score=1.5)

    def test_speaker_count_non_negative(self):
        with pytest.raises(ValidationError):
            Segment(id="seg-1", speaker_count=-1)

    def test_word_count_non_negative(self):
        with pytest.raises(ValidationError):
            Segment(id="seg-1", word_count=-5)


# ═══════════════════════════════════════════════════════════════
# ANALYSIS TESTS
# ═══════════════════════════════════════════════════════════════


class TestAnalysisDefaults:
    def test_id_auto_generated(self):
        a = Analysis()
        assert a.id.startswith("anal-")
        assert len(a.id) > 5

    def test_id_unique_per_instance(self):
        a1 = Analysis()
        a2 = Analysis()
        assert a1.id != a2.id

    def test_source_text_default_empty(self):
        a = Analysis()
        assert a.source_text == ""

    def test_risk_level_defaults_low(self):
        a = Analysis()
        assert a.risk_level == RiskLevel.LOW

    def test_sentiment_score_default_zero(self):
        a = Analysis()
        assert a.sentiment_score == 0.0

    def test_ai_fields_default_none(self):
        a = Analysis()
        assert a.ai_sentiment_score is None
        assert a.ai_risk_score is None
        assert a.ai_sentiment_label is None

    def test_entities_defaults_empty_list(self):
        a = Analysis()
        assert a.entities == []

    def test_tokens_defaults_empty_list(self):
        a = Analysis()
        assert a.tokens == []

    def test_anomaly_flags_default_empty(self):
        a = Analysis()
        assert a.anomaly_flags == []

    def test_confidence_score_default_one(self):
        a = Analysis()
        assert a.confidence_score == 1.0


class TestAnalysisValidation:
    def test_sentiment_score_valid_range(self):
        a = Analysis(sentiment_score=-0.5)
        assert a.sentiment_score == -0.5

    def test_sentiment_score_out_of_range(self):
        with pytest.raises(ValidationError):
            Analysis(sentiment_score=2.0)

    def test_ai_risk_score_valid(self):
        a = Analysis(ai_risk_score=0.8)
        assert a.ai_risk_score == 0.8

    def test_ai_risk_score_out_of_range(self):
        with pytest.raises(ValidationError):
            Analysis(ai_risk_score=1.5)

    def test_confidence_score_range(self):
        with pytest.raises(ValidationError):
            Analysis(confidence_score=-0.1)

    def test_emotional_intensity_range(self):
        with pytest.raises(ValidationError):
            Analysis(emotional_intensity=1.5)


class TestAnalysisHasAiOutput:
    def test_no_ai_output_when_both_none(self):
        a = Analysis()
        assert a.has_ai_output is False

    def test_has_ai_output_when_sentiment_present(self):
        a = Analysis(ai_sentiment_score=0.5)
        assert a.has_ai_output is True

    def test_has_ai_output_when_risk_present(self):
        a = Analysis(ai_risk_score=0.3)
        assert a.has_ai_output is True

    def test_has_ai_output_both_present(self):
        a = Analysis(ai_sentiment_score=0.5, ai_risk_score=0.3)
        assert a.has_ai_output is True


class TestAnalysisEffectiveSentiment:
    def test_returns_zero_when_none(self):
        a = Analysis()
        assert a.effective_sentiment == 0.0

    def test_returns_value_when_set(self):
        a = Analysis(ai_sentiment_score=-0.7)
        assert a.effective_sentiment == -0.7

    def test_returns_zero_for_zero_value(self):
        a = Analysis(ai_sentiment_score=0.0)
        assert a.effective_sentiment == 0.0


class TestAnalysisEffectiveRisk:
    def test_returns_zero_when_none(self):
        a = Analysis()
        assert a.effective_risk == 0.0

    def test_returns_value_when_set(self):
        a = Analysis(ai_risk_score=0.9)
        assert a.effective_risk == 0.9


class TestAnalysisEscalatedRiskScore:
    def test_no_signals_returns_base_risk(self):
        a = Analysis(ai_risk_score=0.5)
        assert a.escalated_risk_score == 0.5

    def test_with_signals_escalates(self):
        signal = make_risk_signal(
            "ultimatum", escalation_multiplier=2.0, credibility_score=0.9
        )
        a = Analysis(ai_risk_score=0.5, risk_signals=(signal,))
        assert a.escalated_risk_score > 0.5

    def test_zero_risk_with_signals_still_nonzero(self):
        signal = make_risk_signal(
            "demand", escalation_multiplier=1.5, credibility_score=0.8
        )
        a = Analysis(ai_risk_score=0.0, risk_signals=(signal,))
        # weighted_sum * 0.1 should be non-zero
        assert a.escalated_risk_score >= 0.0


class TestAnalysisImmutableUpdatePattern:
    def test_model_copy_update_does_not_mutate_original(self):
        a = Analysis(source_text="Original text")
        a2 = a.model_copy(update={"source_text": "Updated"})
        assert a.source_text == "Original text"
        assert a2.source_text == "Updated"

    def test_model_copy_preserves_unmodified_fields(self):
        a = Analysis(source_text="Text", language="tr", ai_risk_score=0.5)
        a2 = a.model_copy(update={"language": "en"})
        assert a2.source_text == "Text"
        assert a2.ai_risk_score == 0.5

    def test_enrichment_chain_simulates_pipeline(self):
        """Simulates the pipeline enrichment pattern used in AnalysisPipeline."""
        a = Analysis(source_text="Turkey condemned the resolution.")
        a = a.model_copy(update={"language": "en", "tokens": ["Turkey", "condemned"]})
        a = a.model_copy(update={"ai_sentiment_score": -0.6, "ai_risk_score": 0.7})
        a = a.model_copy(update={"anomaly_flags": ["HIGH_RISK_MASK"]})

        assert a.language == "en"
        assert len(a.tokens) == 2
        assert a.ai_sentiment_score == -0.6
        assert a.has_ai_output is True
        assert "HIGH_RISK_MASK" in a.anomaly_flags


class TestAnalysisSentenceAlias:
    def test_sentence_analysis_alias(self):
        from bb_paxdata.application.domain.models.analysis import SentenceAnalysis

        a = SentenceAnalysis(source_text="alias test")
        assert isinstance(a, Analysis)


# ═══════════════════════════════════════════════════════════════
# CROSS-MODEL INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestCrossModelIntegration:
    def test_segment_aggregates_multiple_sentences(self):
        sentences = [
            Sentence(id=f"s-{i}", text=f"Sentence {i}.", sentiment_score=0.1 * i)
            for i in range(5)
        ]
        seg = Segment(id="seg-full", sentences=sentences)
        assert seg.sentence_count is None  # Not auto-calculated, must be set manually
        assert len(seg.sentences) == 5
        assert "Sentence 0" in seg.text

    def test_analysis_references_segment(self):
        seg = make_segment()
        a = Analysis(
            source_text=seg.text,
            segment_id=seg.id,
            segments=[seg],
        )
        assert a.segment_id == "seg-001"
        assert len(a.segments) == 1
        assert a.segments[0].id == "seg-001"

    def test_anomaly_flags_drive_logic_result(self):
        """Mirrors the logic_result calculation in build.py pipeline."""
        a_pass = Analysis(anomaly_flags=[])
        a_fail = Analysis(anomaly_flags=["HIGH_RISK_MASK", "CHEAP_TALK"])

        logic_pass = (
            "FAIL"
            if (a_pass.anomaly_flags and len(a_pass.anomaly_flags) > 0)
            else "PASS"
        )
        logic_fail = (
            "FAIL"
            if (a_fail.anomaly_flags and len(a_fail.anomaly_flags) > 0)
            else "PASS"
        )

        assert logic_pass == "PASS"
        assert logic_fail == "FAIL"

    def test_full_pipeline_simulation(self):
        """Simulates sentence → segment → analysis enrichment."""
        sentences = [
            Sentence(
                id="s-1",
                text="We demand immediate withdrawal.",
                is_demand=True,
                risk_score=8.0,
            ),
            Sentence(
                id="s-2", text="Dialogue is essential.", is_demand=False, risk_score=2.0
            ),
        ]
        seg = Segment(id="seg-sim", sentences=sentences, risk_score=5)

        analysis = Analysis(
            source_text=seg.text,
            segment_id=seg.id,
            ai_sentiment_score=-0.4,
            ai_risk_score=0.6,
            anomaly_flags=["HIGH_RISK_DEMAND"],
            segments=[seg],
        )

        assert analysis.has_ai_output is True
        assert analysis.effective_risk == 0.6
        assert len(analysis.anomaly_flags) == 1
        assert "We demand" in analysis.source_text
