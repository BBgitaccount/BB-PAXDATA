import pytest
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.nlp.lodp_service import LODPService


@pytest.mark.asyncio
async def test_lodp_z_score_calculation():
    service = LODPService(alpha=0.01)

    corpus1 = ["peace cooperation peace", "peace development"]
    corpus2 = ["war conflict war", "conflict threat"]

    results = service.analyze(corpus1, corpus2, top_k=10)

    # "peace" should have a high positive z-score (exclusive to corpus1)
    peace_result = next(r for r in results if r.word == "peace")
    assert peace_result.z_score > 0

    # "war" should have a high negative z-score (exclusive to corpus2)
    war_result = next(r for r in results if r.word == "war")
    assert war_result.z_score < 0


@pytest.mark.asyncio
async def test_lodp_top_k():
    service = LODPService()
    corpus1 = ["a b c d e f g"]
    corpus2 = ["h i j k l m n"]

    results = service.analyze(corpus1, corpus2, top_k=5)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_lodp_segment_pair():
    service = LODPService()

    seg1 = Segment(
        id="s1", sentences=[Sentence(id="sen1", text="diplomatic cooperation")]
    )
    seg2 = Segment(
        id="s2", sentences=[Sentence(id="sen2", text="military intervention")]
    )

    results = await service.analyze_segment_pair(seg1, seg2)
    assert len(results) > 0
    assert any(r.word == "diplomatic" for r in results)
