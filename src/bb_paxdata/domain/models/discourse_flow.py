# src/bb_paxdata/domain/models/discourse_flow.py
from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from pydantic import ConfigDict as model_config

from bb_paxdata.domain.enums.country_enums import EdgeType


class DiscourseFlow(BaseModel):
    """
    Söylem ağındaki yönlü kenar (directed edge).
    Eski 'discourse_network_edges' tablosunun DDD karşılığı.

    Grafiksel analiz (merkezilik, kümeleme vb.) için bu entity'ler
    infrastructure'dan çekilip uygulama katmanında networkx'e yüklenir.
    Bu model sadece veriyi taşır; analiz Application katmanının görevidir.
    """

    model_config = model_config(frozen=True)

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

    @property
    def tension_ratio(self) -> float:
        """Çatışma / işbirliği oranı. Sıfır bölme korumalı."""
        total = self.confrontational_count + self.cooperative_count
        if total == 0:
            return 0.0
        return self.confrontational_count / total
