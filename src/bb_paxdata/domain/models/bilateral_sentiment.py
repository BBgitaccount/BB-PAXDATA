# src/bb_paxdata/domain/models/bilateral_sentiment.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field
from pydantic import ConfigDict as model_config

from bb_paxdata.domain.enums.country_enums import RelationshipType

from .discourse_network import DyadicMetrics
from .power_index import PowerIndex


class BilateralSentiment(BaseModel):
    """
    İki ülke arasındaki diplomatik söylem dinamiğinin aggregate modeli.

    Trager (2010) costly signaling + Zagare (2004) escalation + Van Dijk (1993) Power Index.
    """

    model_config = model_config(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    from_country: str = Field(..., min_length=2, max_length=100)
    to_country: str = Field(..., min_length=2, max_length=100)
    panel_id: str = Field(..., min_length=1)

    # Temel sentiment metrikleri (Faz 1'den)
    total_mentions: int = Field(default=0, ge=0)
    avg_sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)
    sentiment_delta: float = Field(
        default=0.0, description="A→B ve B→A sentiment farkı"
    )
    interaction_count: int = Field(default=0, ge=0)
    relationship_type: RelationshipType = RelationshipType.NEUTRAL

    # Trager (2010) sinyalizasyon metrikleri
    power_level_a: float = Field(
        default=1.0, ge=0.0, description="Aktör A'nın güç seviyesi (Van Dijk CDA)"
    )
    power_level_b: float = Field(
        default=1.0, ge=0.0, description="Aktör B'nın güç seviyesi"
    )

    demand_weight: float = Field(
        default=1.0, ge=0.0, description="Talebin ağırlığı/önemi"
    )
    risk_severity: float = Field(
        default=1.0, ge=0.0, description="Tespit edilen risk şiddeti"
    )

    # Trager formülü: power_weighted_score = power_level × demand_weight × risk_severity
    @property
    def power_weighted_score_a(self) -> float:
        """Aktör A'nın güç ağırlıklı skoru (Trager 2010)."""
        return self.power_level_a * self.demand_weight * self.risk_severity

    @property
    def power_weighted_score_b(self) -> float:
        """Aktör B'nın güç ağırlıklı skoru."""
        return self.power_level_b * self.demand_weight * self.risk_severity

    # SignalCredibility = f(power_level, commitment_cost)
    commitment_cost_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def signal_credibility_a(self) -> float:
        """Aktör A'nın sinyal güvenilirliği (Trager 2010)."""
        return min(1.0, self.power_level_a * 0.6 + self.commitment_cost_ratio * 0.4)

    @property
    def signal_credibility_b(self) -> float:
        """Aktör B'nın sinyal güvenilirliği."""
        return min(1.0, self.power_level_b * 0.6 + self.commitment_cost_ratio * 0.4)

    # Combined demand pressure
    @property
    def combined_demand_pressure(self) -> float:
        """Birleşik talep baskısı: ağırlıklı ortalama."""
        total_power = self.power_level_a + self.power_level_b
        if total_power == 0:
            return 0.0
        return (
            (self.power_weighted_score_a * self.power_level_a)
            + (self.power_weighted_score_b * self.power_level_b)
        ) / total_power

    # Van Dijk (1993) → Maoz (2005) köprüsü
    power_index_a: PowerIndex | None = Field(
        default=None, description="Aktör A PowerIndex"
    )
    power_index_b: PowerIndex | None = Field(
        default=None, description="Aktör B PowerIndex"
    )

    @property
    def asymmetry_score(self) -> float:
        """Güç asimetrisi: |PowerIndex(A) − PowerIndex(B)| (Van Dijk 1993 + Maoz 2005)."""
        if self.power_index_a is None or self.power_index_b is None:
            return 0.0

        idx_a = self.power_index_a.total_power_index
        idx_b = self.power_index_b.total_power_index

        raw_diff = abs(idx_a - idx_b)
        max_possible = max(idx_a, idx_b) if max(idx_a, idx_b) > 0 else 1.0

        return min(1.0, raw_diff / max_possible)

    @property
    def dominant_actor(self) -> str | None:
        """Güçlü aktör kim? (asymmetry > 0.2 ise anlamlı)."""
        if self.power_index_a is None or self.power_index_b is None:
            return None

        idx_a = self.power_index_a.total_power_index
        idx_b = self.power_index_b.total_power_index

        if abs(idx_a - idx_b) < 0.05:  # Eşik: neredeyse eşit
            return None

        return self.from_country if idx_a > idx_b else self.to_country

    affinity_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Güç ağırlıklı kümülatif yakınlık skoru",
    )
    power_weighted_score: float = Field(default=0.0)  # Legacy compatibility
    diplomatic_distance: float = Field(default=0.0, ge=0.0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Faz 4 Extensions
    dyadic_metrics: DyadicMetrics | None = Field(default=None)
    discourse_flow_ref: str | None = Field(
        default=None, description="FK to DiscourseFlow.session_id"
    )

    @computed_field
    @property
    def effective_relationship(self) -> RelationshipType:
        if self.affinity_score > 0.5:
            return RelationshipType.ALLY
        elif self.affinity_score > 0.2:
            return RelationshipType.PARTNER
        elif self.affinity_score < -0.5:
            return RelationshipType.ADVERSARY
        elif self.affinity_score < -0.2:
            return RelationshipType.CAUTIOUS
        return RelationshipType.NEUTRAL

    def with_new_reference(
        self,
        sentiment: float,
        power_level: float,
    ) -> BilateralSentiment:
        new_count = self.total_mentions + 1
        new_avg = (self.avg_sentiment * self.total_mentions + sentiment) / new_count
        new_affinity = (
            self.affinity_score * self.total_mentions + sentiment * power_level
        ) / new_count
        return self.model_copy(
            update={
                "total_mentions": new_count,
                "avg_sentiment": round(new_avg, 6),
                "affinity_score": round(max(-1.0, min(1.0, new_affinity)), 6),
                "interaction_count": self.interaction_count + 1,
                "last_updated": datetime.now(timezone.utc),
            }
        )
