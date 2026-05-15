# src/bb_paxdata/domain/models/country_reference.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from pydantic import ConfigDict as model_config

from bb_paxdata.domain.enums.country_enums import ReferenceContext


class CountryReference(BaseModel):
    """
    Bir diplomatik metinde tespit edilen ülke atıfını temsil eder.

    Kim (speaker_country), kimi (referenced_country), hangi bağlamda
    (reference_context) ve hangi panelde bahsetti bilgisini tutar.
    Bu model immutable'dır; güncelleme için model_copy(update={}) kullanılır.
    """

    model_config = model_config(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    panel_id: str = Field(
        ..., min_length=1, description="Analiz edilen panel/transkript ID'si"
    )
    speaker_country: str = Field(..., min_length=2, max_length=100)
    referenced_country: str = Field(..., min_length=2, max_length=100)
    sentence_index: int = Field(
        ..., ge=0, description="Atıfın yapıldığı cümlenin sıra numarası"
    )
    reference_context: ReferenceContext = ReferenceContext.NEUTRAL_MENTION
    raw_sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    speaker_power_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Konuşmacının panel içindeki güç/otorite ağırlığı (SBI'dan türetilir)",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_hostile(self) -> bool:
        """Atıfın düşmanca bir bağlamda yapılıp yapılmadığını döndürür."""
        return self.reference_context in {
            ReferenceContext.ACCUSATION,
            ReferenceContext.THREAT,
        }

    @property
    def weighted_sentiment(self) -> float:
        """Güç seviyesiyle ağırlıklandırılmış duygu skoru."""
        return self.raw_sentiment_score * self.speaker_power_level
