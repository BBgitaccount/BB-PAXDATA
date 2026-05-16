# src/bb_paxdata/infrastructure/nlp/maoz_dyadic_service.py
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import structlog

from bb_paxdata.domain.models.discourse_network import DyadicMetrics

logger = structlog.get_logger()


class MaozDyadicService:
    """
    Maoz (2005) Dyadic Metrics implementation.
    Computes diplomatic_distance and affinity_score for actor pairs.
    """

    def calculate_dyadic_pair(
        self,
        actor_a_id: str,
        actor_b_id: str,
        session_id: str,
        *,
        vote_affinity: Decimal | None,
        alliance_score: Decimal | None,
        structural_distance: Decimal | None,
        discourse_sentiment_delta: Decimal | None,
    ) -> DyadicMetrics:
        """
        Maoz formulas:
        - diplomatic_distance = 1 − (vote_affinity × alliance_score)
        - affinity_score = discourse_sentiment_delta × (1 / structural_distance)
        """
        metrics = DyadicMetrics(
            actor_a_id=actor_a_id,
            actor_b_id=actor_b_id,
            session_id=session_id,
            vote_affinity=vote_affinity,
            alliance_score=alliance_score,
            structural_distance=structural_distance,
            discourse_sentiment_delta=discourse_sentiment_delta,
        )
        computed = metrics.compute()

        logger.info(
            "maoz_dyadic_computed",
            session_id=session_id,
            pair=f"{actor_a_id}-{actor_b_id}",
            diplomatic_distance=computed.diplomatic_distance,
            affinity_score=computed.affinity_score,
        )
        return computed

    def calculate_all_pairs(
        self,
        session_id: str,
        actor_ids: Sequence[str],
        pairwise_inputs: dict[tuple[str, str], dict[str, Decimal | None]],
    ) -> Sequence[DyadicMetrics]:
        """Batch computation for all actor pairs in a session."""
        results: list[DyadicMetrics] = []
        for (a, b), inputs in pairwise_inputs.items():
            metric = self.calculate_dyadic_pair(
                actor_a_id=a,
                actor_b_id=b,
                session_id=session_id,
                vote_affinity=inputs.get("vote_affinity"),
                alliance_score=inputs.get("alliance_score"),
                structural_distance=inputs.get("structural_distance"),
                discourse_sentiment_delta=inputs.get("discourse_sentiment_delta"),
            )
            results.append(metric)
        return results
