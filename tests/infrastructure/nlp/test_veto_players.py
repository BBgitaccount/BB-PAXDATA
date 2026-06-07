from decimal import Decimal

from bb_paxdata.application.domain.models.discourse_flow import NetworkEdge
from bb_paxdata.application.domain.models.discourse_network import DiscourseFlow
from bb_paxdata.infrastructure.nlp.fischer_dna_service import FischerDNAService
from bb_paxdata.infrastructure.nlp.maoz_dyadic_service import MaozDyadicService


def test_veto_players_and_policy_stability():
    service = FischerDNAService()
    flow = DiscourseFlow(session_id="session1")

    # Let's add edges for actor1, actor2, actor3
    # actor1 and actor2 are central, actor3 is marginal
    flow = flow.add_edge(
        NetworkEdge(
            actor_id="actor1",
            concept_id="c1",
            tf_score=Decimal("0.5"),
            idf_score=Decimal("1.0"),
            weight=Decimal("0.5"),
        )
    )
    flow = flow.add_edge(
        NetworkEdge(
            actor_id="actor1",
            concept_id="c2",
            tf_score=Decimal("0.5"),
            idf_score=Decimal("1.0"),
            weight=Decimal("0.5"),
        )
    )
    flow = flow.add_edge(
        NetworkEdge(
            actor_id="actor2",
            concept_id="c1",
            tf_score=Decimal("0.4"),
            idf_score=Decimal("1.0"),
            weight=Decimal("0.4"),
        )
    )
    flow = flow.add_edge(
        NetworkEdge(
            actor_id="actor2",
            concept_id="c2",
            tf_score=Decimal("0.4"),
            idf_score=Decimal("1.0"),
            weight=Decimal("0.4"),
        )
    )
    flow = flow.add_edge(
        NetworkEdge(
            actor_id="actor3",
            concept_id="c1",
            tf_score=Decimal("0.1"),
            idf_score=Decimal("1.0"),
            weight=Decimal("0.1"),
        )
    )

    wordfish_thetas = {
        "actor1": -1.0,
        "actor2": 1.0,
        "actor3": 0.0,
    }

    metrics = service.calculate_veto_players_and_stability(flow, wordfish_thetas)
    assert metrics["veto_player_count"] >= 1
    assert metrics["ideological_polarization_index"] > 0.0
    assert metrics["policy_stability_score"] > 0.0


def test_maoz_dyadic_citation_asymmetry():
    service = MaozDyadicService()
    computed = service.calculate_dyadic_pair(
        actor_a_id="actor1",
        actor_b_id="actor2",
        session_id="session1",
        vote_affinity=Decimal("0.8"),
        alliance_score=Decimal("0.9"),
        structural_distance=Decimal("2.0"),
        discourse_sentiment_delta=Decimal("0.4"),
        citations_a_to_b=10,
        citations_b_to_a=1,
    )
    # asymmetry_ratio = 10 / (1 + 1.0) = 5.0
    assert computed.citation_asymmetry_ratio == 5.0
    assert computed.obsession_flag is True
    assert computed.ignore_flag is False

    computed_ignore = service.calculate_dyadic_pair(
        actor_a_id="actor1",
        actor_b_id="actor2",
        session_id="session1",
        vote_affinity=Decimal("0.8"),
        alliance_score=Decimal("0.9"),
        structural_distance=Decimal("2.0"),
        discourse_sentiment_delta=Decimal("0.4"),
        citations_a_to_b=0,
        citations_b_to_a=4,
    )
    # asymmetry_ratio = 0 / 5 = 0.0
    assert computed_ignore.citation_asymmetry_ratio == 0.0
    assert computed_ignore.obsession_flag is False
    assert computed_ignore.ignore_flag is True
