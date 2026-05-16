# tests/infrastructure/nlp/test_topic_modeling.py
import pytest
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.nlp.topic_modeling import TopicModelingService


@pytest.mark.asyncio
async def test_topic_modeling_service_basic():
    service = TopicModelingService(
        embedding_model="all-MiniLM-L6-v2",
        umap_n_neighbors=2,  # Test için küçük
        hdbscan_min_cluster_size=2,
    )

    segments = [
        Segment(
            id="s1",
            sentences=[
                Sentence(
                    id="s1-1",
                    text="Diplomatic negotiations on trade tariffs between nations.",
                )
            ],
            order=1,
        ),
        Segment(
            id="s2",
            sentences=[
                Sentence(
                    id="s2-1",
                    text="Economic sanctions and their impact on bilateral relations.",
                )
            ],
            order=2,
        ),
        Segment(
            id="s3",
            sentences=[
                Sentence(
                    id="s3-1",
                    text="Climate change agreements and environmental policy frameworks.",
                )
            ],
            order=3,
        ),
        Segment(
            id="s4",
            sentences=[
                Sentence(
                    id="s4-1",
                    text="Trade agreements and tariff reductions in international markets.",
                )
            ],
            order=4,
        ),
        Segment(
            id="s5",
            sentences=[
                Sentence(
                    id="s5-1",
                    text="Environmental protection and carbon emission targets.",
                )
            ],
            order=5,
        ),
    ]

    result = await service.extract_topics(segments, min_topic_size=2)

    assert len(result.assignments) == 5
    assert all(a.topic_scores for a in result.assignments)

    # Olasılıklar normalize edilmiş mi?
    for assignment in result.assignments:
        total_prob = sum(assignment.topic_scores.values())
        assert abs(total_prob - 1.0) < 1e-6 or assignment.primary_topic == "-1"

    # c-TF-IDF skorları var mı?
    assert len(result.topic_keywords) > 0
    for topic_id, keywords in result.topic_keywords.items():
        assert len(keywords) <= 10  # Top-10 limit
        assert all(isinstance(v, float) and v >= 0 for v in keywords.values())


@pytest.mark.asyncio
async def test_custom_ctfidf_formula():
    """c-TF-IDF(w, c) = tf(w,c) × log(1 + A / tf(w)) formülünü validate et."""
    service = TopicModelingService()

    # Mock data
    docs = ["trade war economic impact", "trade negotiation diplomatic solution"]
    topics = [0, 0]

    # Manual calculation
    # topic_docs[0] = ["trade war economic impact", "trade negotiation diplomatic solution"]
    # topic_word_freq[0] = {"trade": 2, "war": 1, "economic": 1, "impact": 1, "negotiation": 1, "diplomatic": 1, "solution": 1}
    # global_word_freq = topic_word_freq[0]
    # total_words = 4 + 4 = 8
    # A = 8 / 1 = 8
    # c-TF-IDF("trade", 0) = tf("trade", 0) * log(1 + A / tf("trade"))
    #                     = 2 * log(1 + 8 / 2) = 2 * log(5) ≈ 2 * 1.609 = 3.218

    ctfidf = await service._calculate_custom_ctfidf(
        topic_model=None,  # Not used in calculation
        docs=docs,
        topics=topics,
    )

    assert "trade" in ctfidf[0]
    # 2 * np.log(5) = 3.21887...
    assert abs(ctfidf[0]["trade"] - 3.21887) < 0.01
