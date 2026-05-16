# tests/unit/quality/test_topic_coherence.py
from bb_paxdata.quality.metrics.custom.topic_coherence import TopicCoherenceEvaluator


def test_topic_coherence_high():
    evaluator = TopicCoherenceEvaluator(threshold=0.5)
    topic_keywords = {"peace": 0.9, "diplomacy": 0.8, "treaty": 0.7}
    corpus = [
        "peace diplomacy treaty signed today",
        "peace and diplomacy are key",
        "new treaty for peace",
        "diplomacy in peace talks",
        "unrelated text here",
        "some more unrelated words",
        "nothing about politics",
        "completely different subject",
    ]
    result = evaluator.measure(topic_keywords, corpus)
    assert result.score > 0.5
    assert result.passed is True


def test_topic_coherence_low():
    evaluator = TopicCoherenceEvaluator(threshold=0.5)
    topic_keywords = {"apple": 0.9, "galaxy": 0.8, "volcano": 0.7}
    corpus = [
        "apple is a fruit",
        "galaxy is far away",
        "volcano erupted in island",
        "the sun is bright",
    ]
    result = evaluator.measure(topic_keywords, corpus)
    # They never co-occur, so score should be low
    assert result.score < 0.5
    assert result.passed is False


def test_topic_coherence_too_few_words():
    evaluator = TopicCoherenceEvaluator()
    topic_keywords = {"peace": 0.9}
    corpus = ["peace is good"]
    result = evaluator.measure(topic_keywords, corpus)
    assert result.score == 1.0
    assert result.passed is True
    assert result.reason and "Too few words" in result.reason
