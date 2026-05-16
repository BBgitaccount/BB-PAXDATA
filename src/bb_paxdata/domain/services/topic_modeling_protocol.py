# src/bb_paxdata/domain/services/topic_modeling_protocol.py
from typing import Protocol, runtime_checkable

from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.topic import TopicResult


@runtime_checkable
class TopicModelingProtocol(Protocol):
    async def extract_topics(
        self,
        segments: list[Segment],
        language: str = "en",
        min_topic_size: int = 5,
        nr_topics: str | int = "auto",
    ) -> TopicResult:
        """Grootendorst (2022) BERTopic pipeline'ını çalıştırır.

        Returns:
            TopicResult: Konu atamaları, olasılıklar ve c-TF-IDF skorları.
        """
        ...

    async def embed_segments(self, segments: list[Segment]) -> dict[str, list[float]]:
        """Segment listesi için embedding vektörleri döner."""
        ...

    async def get_frame_reference_embeddings(self) -> dict[str, list[float]]:
        """Referans frame embedding'lerini döner."""
        ...
