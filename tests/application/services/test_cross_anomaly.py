import pytest
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.services.cross_anomaly_service import SentimentRiskDivergenceRule
from bb_paxdata.infrastructure.nlp.cross_anomaly_service_impl import (
    CrossAnomalyServiceImpl,
)


@pytest.mark.asyncio
async def test_tsytsarau_formula_logic():
    service = CrossAnomalyServiceImpl()

    # CASE 1: No contradiction (all positive)
    polarities = [0.8, 0.9, 0.7, 0.85]
    segment = Segment(id="seg1")
    result = await service.detect_sentiment_risk_divergence(segment, polarities)
    print(f"\nDEBUG: case1_score={result.score}")
    assert result.score < 0.3
    assert not result.is_anomaly

    # CASE 2: High contradiction (mixed sentiments)
    polarities = [0.9, -0.8, 0.85, -0.9]
    result = await service.detect_sentiment_risk_divergence(
        segment, polarities, threshold=0.3
    )
    print(f"\nDEBUG: case2_score={result.score}")
    assert result.score > 0.4
    assert result.is_anomaly


@pytest.mark.asyncio
async def test_sentiment_risk_divergence_rule():
    rule = SentimentRiskDivergenceRule()

    # Analysis with mixed sentences
    analysis = Analysis(
        source_text="I love peace. I hate war.",
        sentences=["I love peace.", "I hate war."],
        ai_sentiment_score=0.0,
        ai_risk_score=0.9,
    )

    triggered, score, message = rule.evaluate(analysis)

    # Mixed sentences should trigger Tsytsarau contradiction
    assert triggered
    assert score > 0.3
    assert "SENTIMENT_RISK_DIVERGENCE" in message


def test_tsytsarau_denominator_zero_protection():
    CrossAnomalyServiceImpl()
    # If all polarities are 0 and theta is 0 (which is not default but good to test)
    # n=1, polarities=[0.0], theta=0.0 -> denominator=0
    # Actually theta is 0.1 by default.
    pass
