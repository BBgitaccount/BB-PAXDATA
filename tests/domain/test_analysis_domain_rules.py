"""Unit tests for stateless domain rules in Analysis model."""

import pytest

from bb_paxdata.application.domain.enums import (
    SignalType,
)
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.power_index import PowerIndex
from bb_paxdata.application.domain.models.risk_signal import RiskSignal
from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis


def test_evaluate_high_risk_anomaly():
    """Test high risk threshold rule logic on Analysis model."""
    # Without AI output
    analysis = Analysis()
    triggered, contribution, msg = analysis.evaluate_high_risk_anomaly()
    assert not triggered

    # With AI output, but under threshold
    analysis = Analysis(ai_risk_score=0.5, prompt_version="v1")
    triggered, contribution, msg = analysis.evaluate_high_risk_anomaly()
    assert not triggered

    # With AI output, above threshold (0.8)
    analysis = Analysis(ai_risk_score=0.9, prompt_version="v1")
    triggered, contribution, msg = analysis.evaluate_high_risk_anomaly()
    assert triggered
    assert contribution == pytest.approx(0.9 * 0.6)
    assert "HIGH_RISK_THRESHOLD" in msg


def test_evaluate_negative_sentiment_anomaly():
    """Test negative sentiment anomaly rule logic on Analysis model."""
    # Without AI output
    analysis = Analysis()
    triggered, contribution, msg = analysis.evaluate_negative_sentiment_anomaly()
    assert not triggered

    # With AI output, above threshold (i.e. less negative than -0.7)
    analysis = Analysis(ai_sentiment_score=-0.5, prompt_version="v1")
    triggered, contribution, msg = analysis.evaluate_negative_sentiment_anomaly()
    assert not triggered

    # With AI output, below threshold (i.e. more negative than -0.7)
    analysis = Analysis(ai_sentiment_score=-0.8, prompt_version="v1")
    triggered, contribution, msg = analysis.evaluate_negative_sentiment_anomaly()
    assert triggered
    assert contribution == pytest.approx(0.8 * 0.3)
    assert "EXTREME_NEGATIVE_SENTIMENT" in msg


def test_evaluate_power_asymmetry_anomaly():
    """Test power asymmetry anomaly rule logic on Analysis model."""
    # Under 2 power indices
    analysis = Analysis(ai_sentiment_score=-0.5, prompt_version="v1")
    triggered, contribution, msg = analysis.evaluate_power_asymmetry_anomaly()
    assert not triggered

    # With 2 power indices, but asymmetry under 0.5
    pi_a = PowerIndex(
        speaker_id="A", segment_id="seg1", authority_markers=5.0, alpha=1.0
    )
    pi_b = PowerIndex(
        speaker_id="B", segment_id="seg1", authority_markers=4.0, alpha=1.0
    )
    analysis = Analysis(
        ai_sentiment_score=-0.5,
        prompt_version="v1",
        power_indices={"A": pi_a, "B": pi_b},
    )
    triggered, contribution, msg = analysis.evaluate_power_asymmetry_anomaly()
    assert not triggered

    # High asymmetry, but positive sentiment (above -0.3)
    pi_a = PowerIndex(
        speaker_id="A", segment_id="seg1", authority_markers=9.0, alpha=1.0
    )
    pi_b = PowerIndex(
        speaker_id="B", segment_id="seg1", authority_markers=1.0, alpha=1.0
    )
    analysis = Analysis(
        ai_sentiment_score=0.0,
        prompt_version="v1",
        power_indices={"A": pi_a, "B": pi_b},
    )
    triggered, contribution, msg = analysis.evaluate_power_asymmetry_anomaly()
    assert not triggered

    # High asymmetry and negative sentiment (below -0.3)
    analysis = Analysis(
        ai_sentiment_score=-0.4,
        prompt_version="v1",
        power_indices={"A": pi_a, "B": pi_b},
    )
    triggered, contribution, msg = analysis.evaluate_power_asymmetry_anomaly()
    assert triggered
    # asymmetry = 8 / 9 = 0.8888
    # contribution = asymmetry * 0.5 = 0.4444
    assert contribution == pytest.approx((8.0 / 9.0) * 0.5)
    assert "POWER_ASYMMETRY_ANOMALY" in msg


def test_evaluate_cheap_talk_anomaly():
    """Test cheap talk anomaly rule logic on Analysis model."""
    analysis = Analysis()
    triggered, _contribution, _msg = analysis.evaluate_cheap_talk_anomaly()
    assert not triggered

    # With risk signals and low power
    sig = RiskSignal(
        signal_text="test",
        signal_start=0,
        signal_end=4,
        signal_type=SignalType.CHEAP_TALK,
        sentence_id="1",
    )
    analysis = Analysis(
        risk_signals=[sig],
        speaker_id="A",
        power_indices={
            "A": PowerIndex(speaker_id="A", segment_id="seg1", base_power=0.0)
        },
    )
    triggered, _contribution, _msg = analysis.evaluate_cheap_talk_anomaly()
    assert not triggered


def test_evaluate_topic_diversity_anomaly():
    """Test topic diversity anomaly rule logic on Analysis model."""
    # Without topic synthesis
    analysis = Analysis(ai_risk_score=0.5, prompt_version="v1")
    triggered, _contribution, _msg = analysis.evaluate_topic_diversity_anomaly()
    assert not triggered

    # With low diversity
    ts = TopicSynthesis(
        panel_id="p1",
        country="TR",
        topic_scores={"economy": 0.9, "security": 0.1},
        dominant_topic="economy",
    )
    analysis = Analysis(ai_risk_score=0.5, prompt_version="v1", topic_synthesis=ts)
    triggered, _contribution, _msg = analysis.evaluate_topic_diversity_anomaly()
    assert not triggered
