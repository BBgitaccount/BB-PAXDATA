# src/bb_paxdata/domain/services/protocols/few_shot_protocols.py
from __future__ import annotations

from typing import Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field


class HumanReviewExample(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_id: str
    sentence_text: str
    sentence_embedding: list[float] | None = None  # populated by infrastructure
    assigned_sentiment: str
    assigned_risk_score: float = Field(..., ge=0.0, le=10.0)
    assigned_frame: str
    speaker_name: str
    country: str
    panel_id: str


class ExampleStoreProtocol(Protocol):
    async def get_all_gold_standards(self) -> Sequence[HumanReviewExample]: ...
    async def get_by_panel(self, panel_id: str) -> Sequence[HumanReviewExample]: ...
    async def get_by_country(self, country: str) -> Sequence[HumanReviewExample]: ...


class EmbeddingCacheProtocol(Protocol):
    async def get(self, text_hash: str) -> list[float] | None: ...
    async def set(
        self, text_hash: str, vector: list[float], ttl_sec: int = 86400
    ) -> None: ...


class SimilaritySelectorProtocol(Protocol):
    async def select(
        self, target_text: str, n_examples: int, min_similarity: float
    ) -> Sequence[HumanReviewExample]: ...
