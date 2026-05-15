# src/bb_paxdata/domain/models/bilateral_sentiment.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field
from pydantic import ConfigDict as model_config

from bb_paxdata.domain.enums.country_enums import RelationshipType


class BilateralSentiment(BaseModel):
    """
    İki ülke arasındaki diplomatik söylem dinamiğinin aggregate modeli.

    Zaman içinde birikerek güncellenen (upsert) bir modeldir.
    Her güncelleme model_copy(update={...}) ile yapılır, mutasyon yoktur.
    """

    model_config = model_config(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    from_country: str = Field(..., min_length=2, max_length=100)
    to_country: str = Field(..., min_length=2, max_length=100)
    panel_id: str = Field(..., min_length=1)
    total_mentions: int = Field(default=0, ge=0)
    avg_sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)
    interaction_count: int = Field(default=0, ge=0)
    relationship_type: RelationshipType = RelationshipType.NEUTRAL
    affinity_score: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Güç ağırlıklı kümülatif yakınlık skoru",
    )
    power_weighted_score: float = Field(default=0.0)
    diplomatic_distance: float = Field(default=0.0, ge=0.0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def effective_relationship(self) -> RelationshipType:
        """
        Affinity score'a göre ilişki tipini hesaplar.
        Bu bir computed_field'dır; sonucu DB'ye yazılmaz, her seferinde hesaplanır.
        """
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
        """
        Yeni bir CountryReference geldiğinde modeli güncelleyen factory method.
        Orijinal nesneyi değiştirmez; güncellenmiş YENİ bir kopya döndürür. (R2)
        """
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
                "last_updated": datetime.utcnow(),
            }
        )
