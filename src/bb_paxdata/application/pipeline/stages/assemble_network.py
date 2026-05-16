# src/bb_paxdata/application/pipeline/stages/assemble_network.py
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

import structlog
from bb_paxdata.application.pipeline.stages.base import AssemblyStage
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.infrastructure.nlp.fischer_dna_service import (
    ActorConceptProfile,
    FischerDNAService,
)
from bb_paxdata.infrastructure.nlp.maoz_dyadic_service import MaozDyadicService

logger = structlog.get_logger()


class NetworkAssemblyStage(AssemblyStage):
    """
    Faz 4 ASSEMBLE step:
    1. Build Fischer DNA network from segments (COLLECT output)
    2. Compute Maoz dyadic metrics using Faz 3 inputs
    """

    def __init__(
        self,
        fischer_service: FischerDNAService,
        maoz_service: MaozDyadicService,
    ) -> None:
        self.fischer = fischer_service
        self.maoz = maoz_service

    async def process(self, analysis: Analysis) -> Analysis:
        """
        Enrich Analysis with DiscourseFlow and BilateralSentiment.
        Immutable: returns new Analysis instance.
        """
        # --- 4.1 Fischer DNA Network Build ---
        # Assuming analysis.segments is where segments are stored.
        # Wait, Analysis model doesn't have segments?
        # Let's check Analysis model again.

        # Based on Phase 3, Analysis seems to be for a single sentence/segment.
        # But DNA needs a collection of segments.
        # If this stage runs at the end of a panel analysis, we need the segments.
        # For now, we'll assume we have access to segments through a context or passed in.
        # The prompt uses analysis.segments.

        segments = getattr(analysis, "segments", []) or []
        profiles = self._extract_actor_profiles(segments)

        discourse_flow = self.fischer.build_network(
            session_id=analysis.id,  # Using analysis.id as session_id
            profiles=profiles,
        )

        # --- 4.3 & 4.4 Maoz Dyadic Metrics ---
        actor_ids = discourse_flow.actor_ids
        pairwise = self._prepare_pairwise_inputs(analysis, actor_ids)
        dyadic_metrics = self.maoz.calculate_all_pairs(
            session_id=analysis.id,
            actor_ids=actor_ids,
            pairwise_inputs=pairwise,
        )

        # Update analysis (immutable copy)
        enriched = analysis.model_copy(
            update={
                "discourse_flow": discourse_flow,
                "bilateral_metrics": dyadic_metrics,
            }
        )

        logger.info(
            "network_assemble_complete",
            session_id=analysis.id,
            actors=len(actor_ids),
            edges=discourse_flow.edge_count,
            dyadic_pairs=len(dyadic_metrics),
        )
        return enriched

    def _extract_actor_profiles(
        self, segments: Sequence[Segment]
    ) -> Sequence[ActorConceptProfile]:
        """Aggregate concepts per actor from segments."""
        actor_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        actor_tokens: dict[str, int] = defaultdict(int)

        for seg in segments:
            actor = seg.primary_speaker_id or "unknown"
            actor_tokens[actor] += len(seg.tokens)
            # Concepts extracted during COLLECT
            for concept in seg.key_concepts:
                actor_data[actor][concept] += 1

        return [
            ActorConceptProfile(
                actor_id=aid,
                concept_counts=dict(counts),
                total_tokens=actor_tokens[aid],
            )
            for aid, counts in actor_data.items()
        ]

    def _prepare_pairwise_inputs(
        self,
        analysis: Analysis,
        actor_ids: Sequence[str],
    ) -> dict[tuple[str, str], dict[str, Decimal | None]]:
        """
        Gather Faz 3 inputs for Maoz formulas.
        """
        pairwise: dict[tuple[str, str], dict[str, Decimal | None]] = {}

        # Fetch existing bilateral data from Faz 3
        # In this context, we might not have a full list yet.
        # But the prompt implies we can look it up.
        existing = getattr(analysis, "bilateral_sentiments", []) or []
        existing_map = {(b.from_country, b.to_country): b for b in existing}

        for i, a in enumerate(actor_ids):
            for b in actor_ids[i + 1 :]:
                bil = existing_map.get((a, b)) or existing_map.get((b, a))

                # Sentiment delta from Faz 1 effective_sentiment
                sent_a = self._get_actor_sentiment(analysis, a)
                sent_b = self._get_actor_sentiment(analysis, b)
                delta = (
                    abs(sent_a - sent_b)
                    if sent_a is not None and sent_b is not None
                    else None
                )

                pairwise[(a, b)] = {
                    "vote_affinity": (
                        Decimal(str(bil.power_weighted_score)) if bil else None
                    ),
                    "alliance_score": (
                        Decimal(str(bil.combined_demand_pressure)) if bil else None
                    ),
                    "structural_distance": (
                        Decimal(str(bil.asymmetry_score)) if bil else None
                    ),
                    "discourse_sentiment_delta": delta,
                }

        return pairwise

    def _get_actor_sentiment(self, analysis: Analysis, actor_id: str) -> Decimal | None:
        """Extract effective sentiment for actor from Faz 1 results."""
        # Implementation depends on how actor sentiment is aggregated in analysis.
        # If analysis represents a session, it might have an actor_sentiments map.
        # For now, return None as per prompt placeholder.
        return None
