# src/bb_paxdata/domain/models/discourse_network.py
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class NetworkEdge(BaseModel):
    """Fischer DNA: Bipartite graph edge (Actor → Concept)."""

    model_config = ConfigDict(frozen=True)

    actor_id: str = Field(..., description="Speaker/Country entity ID")
    concept_id: str = Field(..., description="Extracted concept/topic node ID")
    tf_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"), decimal_places=6)
    idf_score: Decimal = Field(..., ge=Decimal("0"), decimal_places=6)
    weight: Decimal = Field(..., ge=Decimal("0"), description="tf × idf")
    segment_source_id: str | None = Field(default=None)

    def with_weight(self, new_weight: Decimal) -> NetworkEdge:
        return self.model_copy(update={"weight": new_weight})


class DiscourseFlow(BaseModel):
    """Fischer DNA: Complete discourse flow for a single analysis session."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    edges: tuple[NetworkEdge, ...] = Field(default_factory=tuple)
    actor_ids: tuple[str, ...] = Field(default_factory=tuple)
    concept_ids: tuple[str, ...] = Field(default_factory=tuple)
    topic_ids: list[str] = Field(
        default_factory=list, description="IDs of topics present in this flow (Faz 5)"
    )

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def add_edge(self, edge: NetworkEdge) -> DiscourseFlow:
        new_edges = (*self.edges, edge)
        new_actors = tuple(sorted(set(self.actor_ids) | {edge.actor_id}))
        new_concepts = tuple(sorted(set(self.concept_ids) | {edge.concept_id}))
        return self.model_copy(
            update={
                "edges": new_edges,
                "actor_ids": new_actors,
                "concept_ids": new_concepts,
            }
        )


class DyadicMetrics(BaseModel):
    """Maoz (2005): Dyadic relationship metrics between two actors."""

    model_config = ConfigDict(frozen=True)

    actor_a_id: str
    actor_b_id: str
    session_id: str

    # Raw inputs (from Faz 3)
    vote_affinity: Decimal | None = Field(
        default=None, ge=Decimal("0"), le=Decimal("1")
    )
    alliance_score: Decimal | None = Field(
        default=None, ge=Decimal("0"), le=Decimal("1")
    )
    structural_distance: Decimal | None = Field(default=None, ge=Decimal("0"))
    discourse_sentiment_delta: Decimal | None = Field(default=None, ge=Decimal("0"))

    # Computed outputs
    diplomatic_distance: Decimal | None = Field(
        default=None, ge=Decimal("0"), le=Decimal("1")
    )
    affinity_score: Decimal | None = Field(default=None, ge=Decimal("0"))

    @property
    def effective_structural_distance(self) -> Decimal:
        """None-safe structural distance with epsilon guard."""
        if self.structural_distance is None:
            return Decimal("1.0")  # Neutral default
        return max(self.structural_distance, Decimal("0.000001"))

    @property
    def has_required_inputs(self) -> bool:
        return all(
            [
                self.vote_affinity is not None,
                self.alliance_score is not None,
                self.discourse_sentiment_delta is not None,
            ]
        )

    def compute(self) -> DyadicMetrics:
        """Idempotent computation: returns new instance with calculated fields."""
        if not self.has_required_inputs:
            return self

        va = self.vote_affinity
        al = self.alliance_score
        sd = self.effective_structural_distance
        dsd = self.discourse_sentiment_delta

        # Maoz formulas
        # diplomatic_distance = 1 - (vote_affinity × alliance_score)
        diplo_dist = Decimal("1") - (va * al)  # type: ignore[operator]
        # affinity_score = discourse_sentiment_delta × (1 / structural_distance)
        affinity = dsd * (Decimal("1") / sd)  # type: ignore[operator]

        return self.model_copy(
            update={
                "diplomatic_distance": diplo_dist.quantize(Decimal("0.000001")),
                "affinity_score": affinity.quantize(Decimal("0.000001")),
            }
        )
