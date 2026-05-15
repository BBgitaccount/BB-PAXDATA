# tests/application/test_aggregate_bilateral_sentiment.py
from unittest.mock import AsyncMock

import pytest
from bb_paxdata.application.use_cases.aggregate_bilateral_sentiment import (
    AggregateBilateralSentimentInput,
    AggregateBilateralSentimentUseCase,
)
from bb_paxdata.domain.enums.country_enums import ReferenceContext
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.country_reference import CountryReference


def _make_ref(
    speaker: str, referenced: str, sentiment: float, power: float = 0.7
) -> CountryReference:
    return CountryReference(
        panel_id="p001",
        speaker_country=speaker,
        referenced_country=referenced,
        sentence_index=0,
        reference_context=ReferenceContext.NEUTRAL_MENTION,
        raw_sentiment_score=sentiment,
        speaker_power_level=power,
    )


@pytest.mark.asyncio
async def test_creates_new_bilateral_sentiment_for_new_pair() -> None:
    ref_repo = AsyncMock()
    sentiment_repo = AsyncMock()
    ref_repo.get_by_panel.return_value = [_make_ref("TR", "US", 0.6)]
    sentiment_repo.get_by_pair.return_value = None  # Yeni çift
    sentiment_repo.upsert.side_effect = lambda x: x  # Return the object passed

    use_case = AggregateBilateralSentimentUseCase(ref_repo, sentiment_repo)
    output = await use_case.execute(AggregateBilateralSentimentInput(panel_id="p001"))

    assert output.created_count == 1
    assert output.updated_count == 0
    assert output.succeeded


@pytest.mark.asyncio
async def test_updates_existing_bilateral_sentiment() -> None:
    existing = BilateralSentiment(
        panel_id="p001",
        from_country="TR",
        to_country="US",
        total_mentions=2,
        avg_sentiment=0.3,
        affinity_score=0.2,
    )
    ref_repo = AsyncMock()
    sentiment_repo = AsyncMock()
    ref_repo.get_by_panel.return_value = [
        _make_ref("TR", "US", 0.8),
        _make_ref("TR", "US", 0.4),
    ]
    sentiment_repo.get_by_pair.return_value = existing
    sentiment_repo.upsert.side_effect = lambda x: x

    use_case = AggregateBilateralSentimentUseCase(ref_repo, sentiment_repo)
    output = await use_case.execute(AggregateBilateralSentimentInput(panel_id="p001"))

    assert output.updated_count == 1
    # upsert'in aldığı argümanı kontrol et — total_mentions artmış olmalı
    upserted_sentiment = sentiment_repo.upsert.call_args[0][0]
    assert upserted_sentiment.total_mentions == 4  # existing(2) + 2 yeni atıf


@pytest.mark.asyncio
async def test_partial_failure_does_not_abort_all_pairs() -> None:
    ref_repo = AsyncMock()
    sentiment_repo = AsyncMock()
    ref_repo.get_by_panel.return_value = [
        _make_ref("TR", "US", 0.5),
        _make_ref("TR", "DE", 0.3),
    ]
    sentiment_repo.get_by_pair.return_value = None

    call_count = 0

    async def upsert_side_effect(s: BilateralSentiment) -> BilateralSentiment:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("DB timeout")
        return s

    sentiment_repo.upsert.side_effect = upsert_side_effect

    use_case = AggregateBilateralSentimentUseCase(ref_repo, sentiment_repo)
    output = await use_case.execute(AggregateBilateralSentimentInput(panel_id="p001"))

    assert len(output.errors) == 1  # Bir hata var
    assert output.created_count == 1  # Diğeri başarılı
    assert not output.succeeded  # Genel başarı false
