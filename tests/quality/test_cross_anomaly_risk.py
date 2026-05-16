import pytest
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.power_index import PowerIndex


@pytest.mark.asyncio
async def test_high_asymmetry_logic():
    # Güçlü aktör zayıfa tehdit -> anomaly check logic in BilateralSentiment
    bilateral = BilateralSentiment(
        from_country="USA",
        to_country="SmallState",
        panel_id="p1",
        sentiment_delta=-0.5,
        power_index_a=PowerIndex(
            speaker_id="USA",
            segment_id="s1",
            authority_markers=0.8,
            dominance_patterns=0.6,
        ),
        power_index_b=PowerIndex(
            speaker_id="SmallState",
            segment_id="s1",
            authority_markers=0.1,
            dominance_patterns=0.05,
        ),
    )

    assert bilateral.asymmetry_score > 0.5
    assert bilateral.dominant_actor == "USA"
