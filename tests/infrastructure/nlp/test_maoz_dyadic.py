# tests/infrastructure/nlp/test_maoz_dyadic.py
from decimal import Decimal

from bb_paxdata.infrastructure.nlp.maoz_dyadic_service import MaozDyadicService


def test_maoz_dyadic_computation():
    service = MaozDyadicService()

    # Inputs
    va = Decimal("0.8")  # Vote Affinity
    al = Decimal("0.7")  # Alliance Score
    sd = Decimal("2.0")  # Structural Distance
    dsd = Decimal("0.4")  # Discourse Sentiment Delta

    metric = service.calculate_dyadic_pair(
        "ActorA",
        "ActorB",
        "session_1",
        vote_affinity=va,
        alliance_score=al,
        structural_distance=sd,
        discourse_sentiment_delta=dsd,
    )

    # expected diplo_dist = 1 - (0.8 * 0.7) = 1 - 0.56 = 0.44
    assert metric.diplomatic_distance == Decimal("0.440000")

    # expected affinity = 0.4 * (1 / 2.0) = 0.2
    assert metric.affinity_score == Decimal("0.200000")


def test_maoz_missing_inputs():
    service = MaozDyadicService()
    metric = service.calculate_dyadic_pair(
        "A",
        "B",
        "sid",
        vote_affinity=None,
        alliance_score=Decimal("0.5"),
        structural_distance=Decimal("1.0"),
        discourse_sentiment_delta=Decimal("0.1"),
    )
    # Should not compute if inputs are missing
    assert metric.diplomatic_distance is None
    assert metric.affinity_score is None
