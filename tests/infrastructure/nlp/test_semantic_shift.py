import pytest
from bb_paxdata.domain.models.dki import SegmentWindow
from bb_paxdata.infrastructure.nlp.semantic_shift import (
    AzarbonyadSemanticShiftCalculator,
)


@pytest.mark.asyncio
async def test_semantic_shift_calculation():
    calculator = AzarbonyadSemanticShiftCalculator()

    current = SegmentWindow(
        segment_ids=["curr1"],
        texts=[
            "The diplomatic relations are entering a new phase of cooperation and mutual trust."
        ],
        speaker_id="speaker1",
    )

    historical = [
        SegmentWindow(
            segment_ids=["hist1"],
            texts=[
                "The confrontation between nations remains high with significant tension."
            ],
            speaker_id="speaker1",
        )
    ]

    result = await calculator.calculate_shift(current, historical)

    assert result.aggregate_shift >= 0.0
    assert result.vocabulary_overlap_ratio > 0.0
    assert "diplomatic" in result.per_word_shifts or "the" in result.per_word_shifts
    assert result.calculation_method == "azarbonyad_2017"


@pytest.mark.asyncio
async def test_semantic_shift_no_overlap():
    calculator = AzarbonyadSemanticShiftCalculator()

    current = SegmentWindow(segment_ids=["c1"], texts=["apple banana"], speaker_id="s1")
    historical = [SegmentWindow(segment_ids=["h1"], texts=["car bus"], speaker_id="s1")]

    result = await calculator.calculate_shift(current, historical)

    assert result.aggregate_shift == 0.0
    assert result.vocabulary_overlap_ratio == 0.0
