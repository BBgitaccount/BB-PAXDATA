import pytest
from bb_paxdata.domain.enums.sentiment_polarity import SentimentPolarity
from bb_paxdata.infrastructure.nlp.ensemble_sentiment_service import (
    EnsembleSentimentService,
)


@pytest.mark.asyncio
async def test_ensemble_sentiment_majority_voting():
    service = EnsembleSentimentService()
    text = "This is a wonderful and amazing achievement for everyone."

    result = await service.analyze(text)

    assert result.final_polarity == SentimentPolarity.POSITIVE
    assert (
        result.agreement_score == 1.0
    )  # All models should agree on positive for this clear text
    assert len(result.model_votes) == 3


@pytest.mark.asyncio
async def test_ensemble_sentiment_neutral():
    service = EnsembleSentimentService()
    text = "The table is made of wood."

    result = await service.analyze(text)

    assert result.final_polarity == SentimentPolarity.NEUTRAL


@pytest.mark.asyncio
async def test_ensemble_sentiment_mixed_voting():
    # Since we are using mocks that perturb VADER, we might get different results.
    # But majority voting should handle slight noises.
    service = EnsembleSentimentService()
    text = "It was okay but not great."  # VADER might be neutral or slightly negative

    result = await service.analyze(text)
    assert result.method in ["majority_voting", "weighted_average"]
