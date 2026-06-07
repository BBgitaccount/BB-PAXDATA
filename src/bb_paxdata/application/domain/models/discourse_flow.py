# MERGE CONFLICT: DiscourseFlow exists in both discourse_flow.py and discourse_network.py
# with different field definitions. Manual review needed before proceeding.
# discourse_flow.py version: Represents a directed edge in the discourse network (carrying fields like from_country, to_country, panel_id, sentiment_toward, confrontational_count, etc.).
# discourse_network.py version: Represents a complete Fischer DNA discourse flow for a single analysis session (carrying fields like session_id, edges, actor_ids, concept_ids, topic_ids).

"""
Fischer DNA Domain Models — Canonical Module.

All Fischer DNA domain models are defined here:
- DiscourseFlow: Complete discourse flow for a single analysis session.
- NetworkEdge: Bipartite graph edge (Actor → Concept).
- DyadicMetrics: Dyadic relationship metrics between two actors (Maoz 2005).
- ActorConceptProfile: Intermediate aggregation per actor.

Previously, some of these were split across discourse_flow.py and discourse_network.py.
That split was resolved in CIDDI-8.
"""

# src/bb_paxdata/domain/models/discourse_flow.py
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.application.domain.enums.country_enums import EdgeType, NarrativeLayer


class DiscourseFlow(BaseModel):
    """
    Söylem ağındaki yönlü kenar (directed edge).
    Eski 'discourse_network_edges' tablosunun DDD karşılığı.

    Grafiksel analiz (merkezilik, kümeleme vb.) için bu entity'ler
    infrastructure'dan çekilip uygulama katmanında networkx'e yüklenir.
    Bu model sadece veriyi taşır; analiz Application katmanının göredir.

    CORRECTED (E04-M-01): DiscourseFlow mutation gated on GAP-02 resolution.
    GAP-02: DiscourseFlow.actor_ids / .concept_ids attribute verification unresolved.
    Before adding new fields (e.g., referenced_events for TASK-E04), resolve GAP-02 first
    by adding integration test that asserts actor_ids and concept_ids are populated correctly.
    See: https://github.com/BBgitaccount/BB-PAXDATA/issues/GAP-02
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    from_country: str = Field(..., min_length=2, max_length=100)
    to_country: str = Field(..., min_length=2, max_length=100)
    panel_id: str = Field(..., min_length=1)
    edge_type: EdgeType = EdgeType.DIPLOMATIC_REFERENCE
    weight: float = Field(
        default=1.0,
        gt=0.0,
        description="Kenar ağırlığı: bahsetme sıklığı × speaker_power_level",
    )
    sentiment_toward: float = Field(default=0.0, ge=-1.0, le=1.0)
    confrontational_count: int = Field(default=0, ge=0)
    cooperative_count: int = Field(default=0, ge=0)
    narrative_layer: NarrativeLayer | None = Field(
        default=None,
        description="Miskimmon et al. (2013) narrative layer classification",
    )
    narrative_target_actor: str | None = Field(
        default=None,
        description="The country or actor target of this narrative segment",
    )
    narrative_salience: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Per-document narrative salience score"
    )

    @property
    def tension_ratio(self) -> float:
        """Çatışma / işbirliği oranı. Sıfır bölme korumalı."""
        total = self.confrontational_count + self.cooperative_count
        if total == 0:
            return 0.0
        return self.confrontational_count / total


# ---------------------------------------------------------------------------
# Fischer DNA Network Models (merged from discourse_network.py — CIDDI-8)
# ---------------------------------------------------------------------------


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
    citation_asymmetry_ratio: float | None = Field(default=None, ge=0.0)
    obsession_flag: bool = Field(default=False)
    ignore_flag: bool = Field(default=False)

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
