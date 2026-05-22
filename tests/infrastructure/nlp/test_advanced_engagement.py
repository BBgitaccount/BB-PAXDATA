import pytest
from bb_paxdata.infrastructure.nlp.engagement_analyzer import (
    DetailedEngagementScore,
    EngagementAnalyzer,
)


@pytest.mark.asyncio
async def test_engagement_analyzer_advanced_metrics():
    analyzer = EngagementAnalyzer()

    sentences = [
        "We are thinking about the dialogue although the conflict is severe.",
        "We must demand a solution immediately.",
        "Therefore, we propose a new framework.",
        "[...]",
        "No comment.",
    ]

    score = await analyzer.score(
        sentences=sentences,
        speaker_id="speaker1",
        timestamps=[0.0, 10.0, 20.0, 30.0, 40.0],
        speaker_timestamps=[0.0, 40.0, 80.0],
    )

    assert isinstance(score, DetailedEngagementScore)
    assert score >= 0.0
    assert score <= 1.0

    # Velocity: polygloss count > 0.
    assert score.velocity > 0.0

    # Density: "must", "demand" keywords exist.
    assert score.density > 0.0

    # Referential cohesion
    assert score.referential_cohesion >= 0.0

    # RST metrics: depth should be >= 1.0
    assert score.rst_depth >= 1.0
    assert score.nucleus_ratio >= 0.0
    assert score.nucleus_ratio <= 1.0

    # Silence: [...], No comment. exist.
    assert score.silence_density > 0.0
    assert score.evasion_flag is True
    assert score.pressure_index > 0.0

    # Intervention timing CV: speaker_timestamps is [0.0, 40.0, 80.0]. diffs are [40.0, 40.0]. CV should be 0.0.
    assert score.intervention_timing_cv == 0.0


@pytest.mark.asyncio
async def test_engagement_analyzer_empty():
    analyzer = EngagementAnalyzer()
    score = await analyzer.score([], "speaker1")
    assert isinstance(score, DetailedEngagementScore)
    assert score == 0.0
    assert score.velocity == 0.0
    assert score.density == 0.0
