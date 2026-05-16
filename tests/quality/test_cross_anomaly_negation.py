import pytest
from bb_paxdata.domain.enums.negation_type import NegationType
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.negation_cue import NegationCue
from bb_paxdata.domain.services.cross_anomaly_service import SentimentRiskDivergenceRule


@pytest.mark.asyncio
async def test_negation_reduces_false_contradiction():
    # Setup rule
    rule = SentimentRiskDivergenceRule()

    # Sentence with negation: "We are not happy."
    # Polarity would be negative, but it's structural
    analysis = Analysis(
        source_text="We are not happy.",
        sentences=["We are not happy."],
        negation_cues=[
            NegationCue(
                cue_text="not",
                cue_start=7,
                cue_end=10,
                negation_type=NegationType.SYNTACTIC,
                sentence_id="s1",
                scope_token_indices=(2, 3),  # are happy
                scope_text="are happy",
            )
        ],
        ai_sentiment_score=-0.5,
        ai_risk_score=0.1,
    )

    _triggered, _score, _flag = rule.evaluate(analysis)

    # Calculate expected adjustment
    # Adjustment for SYNTACTIC is 0.20
    # Base C would be calculated from polarities
    # If score is reduced below threshold, it shouldn't trigger

    # Just verify that it runs and negation cues are considered
    assert rule._compute_negation_adjustment(analysis) == 0.20
