# src/bb_paxdata/infrastructure/nlp/maoz_dyadic_service.py
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import structlog

from bb_paxdata.application.domain.models.discourse_flow import DyadicMetrics

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
        citations_a_to_b: int | None = None,
        citations_b_to_a: int | None = None,
    ) -> DyadicMetrics:
        """
        Maoz formulas:
        - diplomatic_distance = 1 − (vote_affinity × alliance_score)
        - affinity_score = discourse_sentiment_delta × (1 / structural_distance)
        - citation_asymmetry_ratio = Count(A->B) / (Count(B->A) + 1)
        """
        asymmetry_ratio = None
        obsession = False
        ignore = False

        if citations_a_to_b is not None and citations_b_to_a is not None:
            asymmetry_ratio = float(citations_a_to_b) / (float(citations_b_to_a) + 1.0)
            obsession = asymmetry_ratio > 3.0
            ignore = asymmetry_ratio < 0.33

        metrics = DyadicMetrics(
            actor_a_id=actor_a_id,
            actor_b_id=actor_b_id,
            session_id=session_id,
            vote_affinity=vote_affinity,
            alliance_score=alliance_score,
            structural_distance=structural_distance,
            discourse_sentiment_delta=discourse_sentiment_delta,
            citation_asymmetry_ratio=asymmetry_ratio,
            obsession_flag=obsession,
            ignore_flag=ignore,
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
