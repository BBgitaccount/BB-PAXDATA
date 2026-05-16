# tests/infrastructure/nlp/test_fischer_dna.py
from decimal import Decimal

from bb_paxdata.domain.models.discourse_network import DiscourseFlow
from bb_paxdata.infrastructure.nlp.fischer_dna_service import (
    ActorConceptProfile,
    FischerDNAService,
)


def test_fischer_dna_build_network():
    service = FischerDNAService()

    # Mock profiles: Actor A talks about C1, Actor B talks about C1 and C2
    profiles = [
        ActorConceptProfile(
            actor_id="ActorA", concept_counts={"C1": 10}, total_tokens=100
        ),
        ActorConceptProfile(
            actor_id="ActorB", concept_counts={"C1": 5, "C2": 5}, total_tokens=100
        ),
    ]

    flow = service.build_network(session_id="test_session", profiles=profiles)

    assert isinstance(flow, DiscourseFlow)
    assert flow.session_id == "test_session"
    assert len(flow.edges) == 3  # A->C1, B->C1, B->C2

    # Check A->C1
    edge_a_c1 = next(
        e for e in flow.edges if e.actor_id == "ActorA" and e.concept_id == "C1"
    )
    assert edge_a_c1.tf_score == Decimal("0.1")
    # idf(C1) = log(1 + 2/2) = log(2) ~= 0.693147
    assert edge_a_c1.idf_score > Decimal("0.69")

    # Check B->C2 (Exclusive concept should have higher idf)
    edge_b_c2 = next(
        e for e in flow.edges if e.actor_id == "ActorB" and e.concept_id == "C2"
    )
    # idf(C2) = log(1 + 2/1) = log(3) ~= 1.098612
    assert edge_b_c2.idf_score > edge_a_c1.idf_score

    # Check weight = tf * idf
    assert edge_b_c2.weight == (edge_b_c2.tf_score * edge_b_c2.idf_score).quantize(
        Decimal("0.000001")
    )


def test_actor_vector_sparse():
    service = FischerDNAService()
    profiles = [
        ActorConceptProfile(actor_id="A", concept_counts={"C1": 1}, total_tokens=10)
    ]
    flow = service.build_network("sid", profiles)

    vector = service.get_actor_vector(flow, "A")
    assert "C1" in vector
    assert vector["C1"] > 0
    assert len(vector) == 1
