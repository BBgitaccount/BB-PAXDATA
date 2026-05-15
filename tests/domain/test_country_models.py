# tests/domain/test_country_models.py
import pytest
from bb_paxdata.domain.enums.country_enums import RelationshipType
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.topic_synthesis import TopicSynthesis


def test_bilateral_sentiment_immutability() -> None:
    """Model frozen=True olduğu için doğrudan atama exception fırlatmalı."""
    sentiment = BilateralSentiment(
        panel_id="panel_001",
        from_country="TR",
        to_country="US",
    )
    with pytest.raises(Exception):
        sentiment.total_mentions = 99  # type: ignore[misc]


def test_bilateral_sentiment_with_new_reference_returns_new_instance() -> None:
    """with_new_reference orijinal nesneyi değiştirmemeli."""
    original = BilateralSentiment(
        panel_id="panel_001",
        from_country="TR",
        to_country="US",
        total_mentions=0,
        affinity_score=0.0,
    )
    updated = original.with_new_reference(sentiment=0.8, power_level=0.9)

    assert original.total_mentions == 0  # orijinal değişmemiş
    assert updated.total_mentions == 1
    assert updated.avg_sentiment == pytest.approx(0.8)
    assert updated is not original


def test_effective_relationship_classification() -> None:
    """effective_relationship computed_field doğru sınıflandırma yapmalı."""
    ally = BilateralSentiment(
        panel_id="p", from_country="AA", to_country="BB", affinity_score=0.7
    )
    adversary = BilateralSentiment(
        panel_id="p", from_country="AA", to_country="CC", affinity_score=-0.6
    )
    neutral = BilateralSentiment(
        panel_id="p", from_country="AA", to_country="DD", affinity_score=0.1
    )

    assert ally.effective_relationship == RelationshipType.ALLY
    assert adversary.effective_relationship == RelationshipType.ADVERSARY
    assert neutral.effective_relationship == RelationshipType.NEUTRAL


def test_topic_synthesis_from_scores_normalizes() -> None:
    """from_scores metodu toplam 1.0'a normalize etmeli."""
    raw = {"economy": 10.0, "security": 30.0, "diplomacy": 60.0}
    synthesis = TopicSynthesis.from_scores("panel_001", "TR", raw)

    assert synthesis.dominant_topic == "diplomacy"
    assert abs(sum(synthesis.topic_scores.values()) - 1.0) < 1e-5


def test_topic_synthesis_from_scores_empty() -> None:
    """Tüm skorlar 0.0 ise dominant_topic None olmalı."""
    synthesis = TopicSynthesis.from_scores("panel_001", "TR", {"a": 0.0, "b": 0.0})
    assert synthesis.dominant_topic is None
