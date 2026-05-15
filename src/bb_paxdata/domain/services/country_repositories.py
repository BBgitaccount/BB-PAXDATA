# src/bb_paxdata/domain/services/country_repositories.py
"""
Repository Protocol tanımları — saf domain katmanı.

Concrete implementasyonlar infrastructure/repositories/ içinde bulunur.
Bu dosya sadece sözleşmeyi (contract) tanımlar; hiçbir import dışa bağımlı değil.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.country_reference import CountryReference
from bb_paxdata.domain.models.discourse_flow import DiscourseFlow
from bb_paxdata.domain.models.topic_synthesis import TopicSynthesis


class ICountryReferenceRepository(Protocol):
    async def save(self, reference: CountryReference) -> None: ...
    async def save_batch(self, references: Sequence[CountryReference]) -> None: ...
    async def get_by_panel(self, panel_id: str) -> list[CountryReference]: ...
    async def get_by_pair(
        self, speaker: str, referenced: str, panel_id: str
    ) -> list[CountryReference]: ...


class IBilateralSentimentRepository(Protocol):
    async def upsert(self, sentiment: BilateralSentiment) -> BilateralSentiment: ...
    async def get_by_pair(
        self, from_country: str, to_country: str, panel_id: str
    ) -> BilateralSentiment | None: ...
    async def get_all_for_panel(self, panel_id: str) -> list[BilateralSentiment]: ...


class IDiscourseFlowRepository(Protocol):
    async def save(self, flow: DiscourseFlow) -> None: ...
    async def save_batch(self, flows: Sequence[DiscourseFlow]) -> None: ...
    async def get_edges_for_panel(self, panel_id: str) -> list[DiscourseFlow]: ...


class ITopicSynthesisRepository(Protocol):
    async def upsert(self, synthesis: TopicSynthesis) -> TopicSynthesis: ...
    async def get_by_country(
        self, panel_id: str, country: str
    ) -> TopicSynthesis | None: ...
    async def get_all_for_panel(self, panel_id: str) -> list[TopicSynthesis]: ...
