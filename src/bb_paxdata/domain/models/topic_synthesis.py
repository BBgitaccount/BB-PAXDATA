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

    model_config = model_config(frozen=False)  # model_copy için gerekli

    id: UUID = Field(default_factory=uuid4)
    panel_id: str = Field(..., min_length=1)
    country: str = Field(..., min_length=2, max_length=100)

    # ESKİ (deprecated, silinmeyecek ama kullanılmayacak)
    kw_weights: dict[str, float] | None = Field(
        default=None,
        deprecated=True,
        description="IDF tabanlı eski yaklaşım. Faz 5+ kullanılmaz.",
    )

    # YENİ (Faz 5)
    topic_scores: dict[str, float] | None = Field(
        default=None,
        description="P(topic_k | doc) olasılıksal dağılım. Grootendorst 2022.",
    )
    topic_label: str | None = Field(
        default=None, description="BERTopic konu etiketi veya top-3 keyword birleşimi."
    )
    topic_keywords: dict[str, float] | None = Field(
        default=None,
        description="c-TF-IDF skoruyla sıralanmış konu karakteristik kelimeleri.",
    )

    @property
    def effective_topic(self) -> dict[str, float]:
        """None-safe topic scores."""
        return self.topic_scores or {"unknown": 1.0}

    @property
    def dominant_topic_id(self) -> str:
        """En yüksek olasılıklı konu ID'si."""
        scores = self.effective_topic
        return max(scores, key=lambda k: scores[k])

    @property
    def topic_diversity(self) -> float:
        """Konu dağılımının entropisi (ne kadar odaklı/karışık)."""
        import math

        scores = self.effective_topic
        if len(scores) <= 1:
            return 0.0
        total = sum(scores.values())
        probs = [v / total for v in scores.values() if v > 0]
        return -sum(p * math.log2(p) for p in probs if p > 0)

    @classmethod
    def from_scores(
        cls,
        panel_id: str,
        country: str,
        raw_scores: dict[str, float],
    ) -> TopicSynthesis:
        """
        Ham skorlardan normalize edilmiş bir TopicSynthesis oluşturur.
        """
        total = sum(raw_scores.values())
        if total == 0:
            normalized: dict[str, float] = {k: 0.0 for k in raw_scores}
            label = None
        else:
            normalized = {k: round(v / total, 6) for k, v in raw_scores.items()}
            label = max(normalized, key=lambda k: normalized[k])

        return cls(
            panel_id=panel_id,
            country=country,
            topic_scores=normalized,
            topic_label=label,
        )
