# src/bb_paxdata/domain/models/topic_synthesis.py
from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from pydantic import ConfigDict as model_config


class TopicSynthesis(BaseModel):
    """
    Panel × ülke bazında konu skorlarını tutan Value Object.

    Bu bir Entity değil, Value Object'tir:
    - Kimliği kendi verisiyle tanımlanır (panel_id + country).
    - DB'de tek bir JSON sütunu olarak veya ayrı satırlar olarak saklanabilir.
    - Hesaplama Application katmanında yapılır; bu model sadece sonucu taşır.
    """

    model_config = model_config(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    panel_id: str = Field(..., min_length=1)
    country: str = Field(..., min_length=2, max_length=100)
    topic_scores: dict[str, float] = Field(
        default_factory=dict,
        description="{'topic_label': normalized_score} formatında konu skorları",
    )
    dominant_topic: str | None = Field(
        default=None,
        description="En yüksek skoru alan konu etiketi",
    )

    @classmethod
    def from_scores(
        cls,
        panel_id: str,
        country: str,
        raw_scores: dict[str, float],
    ) -> TopicSynthesis:
        """
        Ham skorlardan normalize edilmiş bir TopicSynthesis oluşturur.
        Toplam skor sıfırsa tüm değerler 0.0 kalır.
        """
        total = sum(raw_scores.values())
        if total == 0:
            normalized: dict[str, float] = {k: 0.0 for k in raw_scores}
            dominant = None
        else:
            normalized = {k: round(v / total, 6) for k, v in raw_scores.items()}
            dominant = max(normalized, key=lambda k: normalized[k])

        return cls(
            panel_id=panel_id,
            country=country,
            topic_scores=normalized,
            dominant_topic=dominant,
        )
