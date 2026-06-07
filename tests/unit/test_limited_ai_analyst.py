from unittest.mock import AsyncMock, MagicMock

import pytest
from bb_paxdata.application.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.infrastructure.nlp.limited_ai_analyst import LimitedAIAnalyst


@pytest.fixture
def mock_real_analyst():
    analyst = AsyncMock()
    # Mocking standard return value of AIAnalyst
    mock_result = AIAnalysisResult(
        sentiment_label="positive",
        sentiment_score=0.8,
        risk_score=0.1,
        tokens=["peace", "talks"],
        topic_synthesis=MagicMock(topic_label="Diplomacy"),
        framing="diagnostic",
        anomaly_flags=[],
        prompt_version="mock_analyst@1.0",
    )
    analyst.analyze.return_value = mock_result
    return analyst


@pytest.mark.asyncio
async def test_limited_ai_analyst_within_limit(mock_real_analyst):
    """Test that LimitedAIAnalyst delegates to real analyst when under the limit."""
    limit_analyst = LimitedAIAnalyst(delegate=mock_real_analyst, limit=2)

    # Process sentence 1
    limit_analyst.begin_sentence()
    result = await limit_analyst.analyze("We want peace.")

    assert result.sentiment_label == "positive"
    assert mock_real_analyst.analyze.call_count == 1

    # Process sentence 2
    limit_analyst.begin_sentence()
    result = await limit_analyst.analyze("Diplomatic efforts are key.")

    assert result.sentiment_label == "positive"
    assert mock_real_analyst.analyze.call_count == 2

    summary = limit_analyst.get_usage_summary()
    assert summary["sentences_processed"] == 2
    assert summary["ai_sentence_limit"] == 2
    assert summary["ai_calls_made"] == 2
    assert summary["remaining"] == 0
    assert summary["is_exhausted"] is True


@pytest.mark.asyncio
async def test_limited_ai_analyst_exceeds_limit(mock_real_analyst):
    """Test that LimitedAIAnalyst falls back to logic-only when limit is exceeded."""
    limit_analyst = LimitedAIAnalyst(delegate=mock_real_analyst, limit=1)

    # Sentence 1: within limit (goes to real AI)
    limit_analyst.begin_sentence()
    await limit_analyst.analyze("We want peace.")
    assert mock_real_analyst.analyze.call_count == 1

    # Sentence 2: exceeds limit (goes to logic-only fallback)
    limit_analyst.begin_sentence()
    result = await limit_analyst.analyze("Military war attack.")

    # Real AI call count should still be 1
    assert mock_real_analyst.analyze.call_count == 1
    # Fallback result should have logic-only outputs (e.g. risk score 0.6)
    assert result.sentiment_label == "confrontational"
    assert result.risk_score == 0.6

    summary = limit_analyst.get_usage_summary()
    assert summary["sentences_processed"] == 2
    assert summary["ai_sentence_limit"] == 1
    assert summary["ai_calls_made"] == 1
    assert summary["remaining"] == 0
    assert summary["is_exhausted"] is True
    assert summary["ai_analyze_calls"] == 1
    assert summary["logic_analyze_calls"] == 1
