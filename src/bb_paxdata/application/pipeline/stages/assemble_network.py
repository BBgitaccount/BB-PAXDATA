# src/bb_paxdata/application/pipeline/stages/assemble_network.py
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import structlog

from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
    COUNTRY_BLOC_MAP,
    normalize_country,
)
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.pipeline.stages.base import BaseAssemblyStage
from bb_paxdata.infrastructure.nlp.fischer_dna_service import (
    ActorConceptProfile,
    FischerDNAService,
)
from bb_paxdata.infrastructure.nlp.maoz_dyadic_service import MaozDyadicService

logger = structlog.get_logger()


@dataclass
class ActionTriplet:
    """
    Immutable Actor→Predicate→Target triplet with aggregation metadata.
    Used as intermediate representation before network edge creation.
    """

    actor: str  # ARG0 / from_country
    predicate: str  # Verb / action
    target: str  # ARG1 / to_country
    is_negated: bool  # ARGM-NEG
    modal: str | None  # ARGM-MOD
    confidence: float  # Frame confidence
    source_sentence_idx: int
    count: int = 1  # Aggregation count

    @property
    def key(self) -> tuple[str, str, str]:
        """Hashable key for deduplication (ignores modifiers)."""
        return (
            self.actor.lower().strip(),
            self.predicate.lower().strip(),
            self.target.lower().strip(),
        )

    def merge_with(self, other: ActionTriplet) -> ActionTriplet:
        """Merge duplicate triplet, averaging confidence and incrementing count."""
        if self.key != other.key:
            raise ValueError("Cannot merge triplets with different keys")

        return ActionTriplet(
            actor=self.actor,
            predicate=self.predicate,
            target=self.target,
            is_negated=self.is_negated or other.is_negated,
            modal=self.modal or other.modal,
            confidence=(self.confidence + other.confidence) / 2,
            source_sentence_idx=min(
                self.source_sentence_idx, other.source_sentence_idx
            ),
            count=self.count + other.count,
        )


def calculate_alliance_score(country_a: str, country_b: str) -> Decimal:
    """
    İki ülke arasındaki ittifak yoğunluğunu (0-1) hesaplar.
    NATO üyeleri, bloc üyeliği ve diğer diplomatik ilişkiler üzerinden proxy oluşturulur.
    """
    iso_a, _, bloc_a = normalize_country(country_a)
    iso_b, _, bloc_b = normalize_country(country_b)

    # NATO Üyeleri listesi (Standardized ISO3 codes)
    NATO_MEMBERS = {
        "USA",
        "CAN",
        "GBR",
        "FRA",
        "DEU",
        "ITA",
        "ESP",
        "POL",
        "SWE",
        "NOR",
        "GRC",
        "LVA",
        "LTU",
        "MKD",
        "TUR",
    }

    # 1. Her iki ülke de NATO üyesi -> 1.0
    if iso_a in NATO_MEMBERS and iso_b in NATO_MEMBERS:
        return Decimal("1.0")

    # 2. Biri NATO üyesi, diğeri Rusya/Doğu Bloku -> 0.0
    is_a_nato = iso_a in NATO_MEMBERS
    is_b_nato = iso_b in NATO_MEMBERS
    is_a_east = bloc_a == "Eastern Bloc / Russian Sphere" or iso_a in {
        "RUS",
        "BLR",
        "PRK",
    }
    is_b_east = bloc_b == "Eastern Bloc / Russian Sphere" or iso_b in {
        "RUS",
        "BLR",
        "PRK",
    }

    if (is_a_nato and is_b_east) or (is_b_nato and is_a_east):
        return Decimal("0.0")

    # 3. Her iki ülke de Non-Aligned / tarafsız veya bölgesel paktlar -> 0.5
    non_aligned_blocs = {
        "Non-Aligned / Global South",
        "African Union Aligned",
        "Arab League",
        "ASEAN Aligned",
        "Central Asian Sphere",
        "Other",
        "unknown",
    }
    if bloc_a in non_aligned_blocs and bloc_b in non_aligned_blocs:
        return Decimal("0.5")

    # 4. Aynı diplomatik blok -> 0.8
    if bloc_a == bloc_b and bloc_a != "unknown":
        return Decimal("0.8")

    # 5. Diğer durumlar için default -> 0.5
    return Decimal("0.5")


class NetworkAssemblyStage(BaseAssemblyStage):
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
        # Verify narrative fields exist (FINDING I-03)
        for sentiment in analysis.bilateral_metrics or []:
            if not hasattr(sentiment, "narrative_layer"):
                logger.warning(
                    "narrative_fields_missing",
                    sentiment_from=sentiment.from_country,
                    sentiment_to=sentiment.to_country,
                    msg="BilateralSentiment has no narrative fields; NarrativeClassifierStage may have been skipped",
                )

        # --- 4.1 Fischer DNA Network Build ---
        segments = analysis.segments or []
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

        dyadic_map = {
            (metric.actor_a_id, metric.actor_b_id): metric for metric in dyadic_metrics
        }

        # --- SRL Triplet Extraction and Aggregation ---
        triplet_aggregator: dict[tuple[str, str, str], ActionTriplet] = {}
        for segment in segments:
            for sentence in segment.sentences or []:
                if not hasattr(sentence, "srl_frames") or not sentence.srl_frames:
                    continue
                for frame in sentence.srl_frames:
                    if not frame.has_complete_triplet:
                        continue
                    # Narrow str | None → str (has_complete_triplet guarantees these)
                    if not frame.actor_text or not frame.target_text:
                        continue
                    triplet = ActionTriplet(
                        actor=frame.actor_text,
                        predicate=frame.verb,
                        target=frame.target_text,
                        is_negated=frame.argm_neg,
                        modal=frame.argm_mod,
                        confidence=frame.frame_confidence,
                        source_sentence_idx=frame.source_sentence_idx or 0,
                    )
                    key = triplet.key
                    if key in triplet_aggregator:
                        triplet_aggregator[key] = triplet_aggregator[key].merge_with(
                            triplet
                        )
                    else:
                        triplet_aggregator[key] = triplet

        enriched_bilateral_metrics: list[BilateralSentiment] = []
        seen_pairs: set[tuple[str, str]] = set()

        for sentiment in analysis.bilateral_metrics or []:
            dyadic = dyadic_map.get((sentiment.from_country, sentiment.to_country))
            if dyadic is None:
                dyadic = dyadic_map.get((sentiment.to_country, sentiment.from_country))

            # Match SRL triplet
            matching_triplets = [
                t
                for t in triplet_aggregator.values()
                if t.actor.lower() == sentiment.from_country.lower()
                and t.target.lower() == sentiment.to_country.lower()
            ]

            srl_update: dict[str, Any] = {}
            if matching_triplets:
                rep = max(matching_triplets, key=lambda t: t.confidence)
                srl_update = {
                    "srl_predicate": rep.predicate,
                    "srl_arg0_entity": rep.actor,
                    "srl_arg1_entity": rep.target,
                    "srl_is_negated": rep.is_negated,
                    "srl_modal": rep.modal,
                    "srl_confidence": rep.confidence,
                    "srl_mention_count": rep.count,
                }

            if dyadic is None:
                if srl_update:
                    for k, v in srl_update.items():
                        setattr(sentiment, k, v)
                enriched_bilateral_metrics.append(sentiment)
                continue

            seen_pairs.add((dyadic.actor_a_id, dyadic.actor_b_id))

            update_fields: dict[str, Any] = {
                "dyadic_metrics": dyadic,
                "diplomatic_distance": float(
                    dyadic.diplomatic_distance
                    if dyadic.diplomatic_distance is not None
                    else sentiment.diplomatic_distance
                ),
                "affinity_score": float(
                    dyadic.affinity_score
                    if dyadic.affinity_score is not None
                    else sentiment.affinity_score
                ),
            }
            update_fields.update(srl_update)

            for k, v in update_fields.items():
                setattr(sentiment, k, v)
            enriched_bilateral_metrics.append(sentiment)

        for dyadic in dyadic_metrics:
            pair = (dyadic.actor_a_id, dyadic.actor_b_id)
            if pair in seen_pairs:
                continue

            # Match SRL triplet for new dyadic pair
            matching_triplets = [
                t
                for t in triplet_aggregator.values()
                if t.actor.lower() == dyadic.actor_a_id.lower()
                and t.target.lower() == dyadic.actor_b_id.lower()
            ]

            srl_fields: dict[str, Any] = {}
            if matching_triplets:
                rep = max(matching_triplets, key=lambda t: t.confidence)
                srl_fields = {
                    "srl_predicate": rep.predicate,
                    "srl_arg0_entity": rep.actor,
                    "srl_arg1_entity": rep.target,
                    "srl_is_negated": rep.is_negated,
                    "srl_modal": rep.modal,
                    "srl_confidence": rep.confidence,
                    "srl_mention_count": rep.count,
                }

            enriched_bilateral_metrics.append(
                BilateralSentiment(
                    panel_id=analysis.id,
                    from_country=dyadic.actor_a_id,
                    to_country=dyadic.actor_b_id,
                    dyadic_metrics=dyadic,
                    diplomatic_distance=float(dyadic.diplomatic_distance or 0.0),
                    affinity_score=float(dyadic.affinity_score or 0.0),
                    **srl_fields,
                )
            )

        # Update analysis (in-place mutation)
        analysis.discourse_flow = discourse_flow
        analysis.bilateral_metrics = enriched_bilateral_metrics
        enriched = analysis

        logger.info(
            "network_assemble_complete",
            session_id=analysis.id,
            actors=len(actor_ids),
            edges=discourse_flow.edge_count,
            dyadic_pairs=len(dyadic_metrics),
        )

        # CORRECTED (E04-M-06): Event node integration gated on GAP-06 resolution
        # GAP-06: Edge weight normalization absent from Fischer DNA graph
        # Event nodes should only be added after GAP-06 is resolved to ensure
        # edge weights are normalized before adding event-to-actor edges.
        # When GAP-06 is resolved, add event node integration here with:
        # - Event nodes from CanonicalEvent registry
        # - Normalized edge weights using the same normalization function as existing edges
        # - Event-to-actor edges with PARTICIPATES_IN edge type
        # See: https://github.com/BBgitaccount/BB-PAXDATA/issues/GAP-06

        return enriched

    def _extract_actor_profiles(
        self, segments: Sequence[Segment]
    ) -> Sequence[ActorConceptProfile]:
        """Aggregate concepts per actor from segments."""
        actor_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        actor_tokens: dict[str, int] = defaultdict(int)
        actor_concept_segments: dict[str, dict[str, str]] = defaultdict(dict)

        # Sort segments to determine the first mention in temporal/logical order
        sorted_segs = sorted(segments, key=lambda s: (s.start_time or 0.0, s.id or ""))

        for seg in sorted_segs:
            actor = seg.primary_speaker_id or "unknown"
            actor_tokens[actor] += len(seg.tokens)
            # Concepts extracted during COLLECT
            for concept in seg.key_concepts:
                actor_data[actor][concept] += 1
                if concept not in actor_concept_segments[actor]:
                    actor_concept_segments[actor][concept] = seg.id

        return [
            ActorConceptProfile(
                actor_id=aid,
                concept_counts=dict(counts),
                total_tokens=actor_tokens[aid],
                concept_segments=actor_concept_segments[aid],
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
        existing = analysis.bilateral_metrics or []
        existing_map = {(b.from_country, b.to_country): b for b in existing}

        for i, a in enumerate(actor_ids):
            for b in actor_ids[i + 1 :]:
                bil_ab = existing_map.get((a, b))
                bil_ba = existing_map.get((b, a))

                # signed discourse_sentiment_delta = avg_sentiment(A talking about B) - avg_sentiment(B talking about A)
                if bil_ab is not None or bil_ba is not None:
                    avg_a_b = bil_ab.avg_sentiment if bil_ab is not None else 0.0
                    avg_b_a = bil_ba.avg_sentiment if bil_ba is not None else 0.0
                    delta = Decimal(str(avg_a_b - avg_b_a))
                else:
                    delta = None

                # Calculate structural_distance from standard country power levels
                iso_a, _, _ = normalize_country(a)
                iso_b, _, _ = normalize_country(b)
                info_a = COUNTRY_BLOC_MAP.get(iso_a)
                info_b = COUNTRY_BLOC_MAP.get(iso_b)
                power_a = info_a["power_level"] if info_a else 0.5
                power_b = info_b["power_level"] if info_b else 0.5
                structural = Decimal(str(abs(power_a - power_b)))

                # Calculate alliance_score using our dynamic helper
                alliance = calculate_alliance_score(a, b)

                pairwise[(a, b)] = {
                    "vote_affinity": None,  # TODO: UN voting dataset integration required (Maoz academic metric)
                    "alliance_score": alliance,
                    "structural_distance": structural,
                    "discourse_sentiment_delta": delta,
                }

        return pairwise

    def _get_actor_sentiment(self, analysis: Analysis, actor_id: str) -> Decimal | None:
        """Extract effective sentiment for actor from Faz 1 results."""
        # Aggregate per-segment sentence sentiment for the given actor.
        actor_sentences: list[float] = []
        for seg in analysis.segments or []:
            if seg.primary_speaker_id != actor_id:
                continue
            for s in seg.sentences:
                # Domain `Sentence.sentiment_score` may be None
                val = getattr(s, "sentiment_score", None)
                if val is not None:
                    actor_sentences.append(float(val))

        if not actor_sentences:
            return None

        avg = sum(actor_sentences) / len(actor_sentences)
        return Decimal(str(avg))
