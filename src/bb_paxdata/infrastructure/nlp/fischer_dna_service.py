# src/bb_paxdata/infrastructure/nlp/fischer_dna_service.py
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

import structlog
from pydantic import BaseModel

from bb_paxdata.domain.models.discourse_network import DiscourseFlow, NetworkEdge

logger = structlog.get_logger()


class ActorConceptProfile(BaseModel):
    """Intermediate aggregation per actor."""

    actor_id: str
    concept_counts: dict[str, int]
    total_tokens: int


class FischerDNAService:
    """
    Fischer et al. (2012) Discourse Network Analysis implementation.
    Computes bipartite actor-concept edges with tf-idf weighting.
    """

    def __init__(self, epsilon: Decimal = Decimal("0.000001")) -> None:
        self.epsilon = epsilon

    def build_network(
        self,
        session_id: str,
        profiles: Sequence[ActorConceptProfile],
    ) -> DiscourseFlow:
        """
        Build DiscourseFlow from actor-concept co-occurrence profiles.

        Formula: weight(A→C) = tf(A,C) × idf(C)
        """
        n_actors = len(profiles)

        # Phase 1: Compute document frequency (df) per concept
        concept_df: dict[str, int] = defaultdict(int)
        for profile in profiles:
            for concept in profile.concept_counts:
                concept_df[concept] += 1

        # Phase 2: Compute tf-idf per edge
        flow = DiscourseFlow(session_id=session_id)

        for profile in profiles:
            actor_total = max(profile.total_tokens, 1)
            for concept, count in profile.concept_counts.items():
                tf_val = Decimal(count) / Decimal(actor_total)
                df_val = concept_df[concept]
                # idf = log(1 + N_actors / df(concept))
                idf_val = Decimal(str(math.log(1 + n_actors / df_val)))
                weight = (tf_val * idf_val).quantize(Decimal("0.000001"))

                edge = NetworkEdge(
                    actor_id=profile.actor_id,
                    concept_id=concept,
                    tf_score=tf_val.quantize(Decimal("0.000001")),
                    idf_score=idf_val.quantize(Decimal("0.000001")),
                    weight=weight,
                )
                flow = flow.add_edge(edge)

        logger.info(
            "fischer_dna_network_built",
            session_id=session_id,
            actors=n_actors,
            concepts=len(concept_df),
            edges=flow.edge_count,
        )
        return flow

    def get_actor_vector(
        self,
        flow: DiscourseFlow,
        actor_id: str,
    ) -> dict[str, Decimal]:
        """Return concept-weight vector for a given actor (sparse representation)."""
        return {e.concept_id: e.weight for e in flow.edges if e.actor_id == actor_id}

    def calculate_veto_players_and_stability(
        self,
        flow: DiscourseFlow,
        wordfish_thetas: dict[str, float],
        lambda_val: float = 0.5,
    ) -> dict[str, float]:
        """
        Calculate veto player counts, ideological polarization, and policy stability (deadlock probability).
        """
        import statistics

        # Compute degree centrality for each actor in the discourse network
        centralities = {}
        for actor_id in flow.actor_ids:
            centralities[actor_id] = float(
                sum(e.weight for e in flow.edges if e.actor_id == actor_id)
            )

        # Identify Veto Players: actors with degree centrality >= median
        veto_players = []
        if centralities:
            centrality_vals = list(centralities.values())
            median_centrality = statistics.median(centrality_vals)
            veto_players = [
                a for a, c in centralities.items() if c >= median_centrality
            ]

        # Veto Player Distance: maximum ideological distance between veto players
        veto_thetas = [wordfish_thetas[a] for a in veto_players if a in wordfish_thetas]
        if len(veto_thetas) >= 2:
            veto_distance = max(veto_thetas) - min(veto_thetas)
            min_centrality = min(centralities[a] for a in veto_players)
            policy_stability_score = 1.0 - math.exp(
                -lambda_val * veto_distance * min_centrality
            )
        else:
            veto_distance = 0.0
            policy_stability_score = 0.0

        # Ideological Polarization Index: standard deviation of all Wordfish thetas
        theta_vals = list(wordfish_thetas.values())
        if len(theta_vals) >= 2:
            ideological_polarization_index = statistics.stdev(theta_vals)
        else:
            ideological_polarization_index = 0.0

        return {
            "veto_player_count": float(len(veto_players)),
            "ideological_polarization_index": float(ideological_polarization_index),
            "policy_stability_score": float(policy_stability_score),
        }
