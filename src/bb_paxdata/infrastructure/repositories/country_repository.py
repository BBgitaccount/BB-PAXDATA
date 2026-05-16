# src/bb_paxdata/infrastructure/repositories/country_repository.py
"""
Concrete repository implementasyonları.

Her class, domain/services/country_repositories.py'daki Protocol'ü implemente eder.
SQLAlchemy 2.0 async session kullanılır.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.country_reference import CountryReference
from bb_paxdata.domain.models.discourse_flow import DiscourseFlow
from bb_paxdata.domain.models.discourse_network import DyadicMetrics
from bb_paxdata.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.infrastructure.db.country_models import (
    BilateralSentimentTable,
    CountryReferenceTable,
    DiscourseFlowTable,
    TopicMatrixTable,
)


class CountryReferenceRepository:
    """ICountryReferenceRepository Protocol'ünün SQLAlchemy implementasyonu."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, reference: CountryReference) -> None:
        row = CountryReferenceTable.from_domain(reference)
        self._session.add(row)
        await self._session.flush()

    async def save_batch(self, references: Sequence[CountryReference]) -> None:
        rows = [CountryReferenceTable.from_domain(r) for r in references]
        self._session.add_all(rows)
        await self._session.flush()

    async def get_by_panel(self, panel_id: str) -> list[CountryReference]:
        result = await self._session.execute(
            select(CountryReferenceTable).where(
                CountryReferenceTable.panel_id == panel_id
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def get_by_pair(
        self, speaker: str, referenced: str, panel_id: str
    ) -> list[CountryReference]:
        result = await self._session.execute(
            select(CountryReferenceTable).where(
                CountryReferenceTable.panel_id == panel_id,
                CountryReferenceTable.speaker_country == speaker,
                CountryReferenceTable.referenced_country == referenced,
            )
        )
        return [row.to_domain() for row in result.scalars().all()]


class BilateralSentimentRepository:
    """IBilateralSentimentRepository Protocol'ünün SQLAlchemy implementasyonu."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, sentiment: BilateralSentiment) -> BilateralSentiment:
        """
        Upsert: (panel_id, from_country, to_country) unique constraint'e göre
        kayıt varsa günceller, yoksa ekler.
        """
        existing = await self.get_by_pair(
            sentiment.from_country, sentiment.to_country, sentiment.panel_id
        )
        if existing is not None:
            # Mevcut kaydı bul ve güncelle
            result = await self._session.execute(
                select(BilateralSentimentTable).where(
                    BilateralSentimentTable.panel_id == sentiment.panel_id,
                    BilateralSentimentTable.from_country == sentiment.from_country,
                    BilateralSentimentTable.to_country == sentiment.to_country,
                )
            )
            row = result.scalar_one()
            # Alan alan güncelle (ORM nesnesini mutate etmek burada meşru —
            # bu infra katmanı, domain immutability kuralı domain modelleri için geçerli)
            row.total_mentions = sentiment.total_mentions
            row.avg_sentiment = sentiment.avg_sentiment
            row.interaction_count = sentiment.interaction_count
            row.relationship_type = sentiment.relationship_type.value
            row.affinity_score = sentiment.affinity_score
            row.power_weighted_score = sentiment.power_weighted_score
            row.diplomatic_distance = sentiment.diplomatic_distance
            row.last_updated = sentiment.last_updated

            # Phase 4 Extensions
            if sentiment.dyadic_metrics:
                m = sentiment.dyadic_metrics
                row.vote_affinity = m.vote_affinity
                row.alliance_score = m.alliance_score
                row.structural_distance = m.structural_distance
                row.discourse_sentiment_delta = m.discourse_sentiment_delta
                row.maoz_diplomatic_distance = m.diplomatic_distance
                row.maoz_affinity_score = m.affinity_score
        else:
            row = BilateralSentimentTable.from_domain(sentiment)
            self._session.add(row)

        await self._session.flush()
        return row.to_domain()

    async def save_dyadic(self, session: AsyncSession, metrics: DyadicMetrics) -> None:
        """Persist Maoz dyadic metrics into bilateral_sentiments table."""
        # Find existing bilateral record for this pair and session
        # session_id here maps to panel_id in BilateralSentimentTable
        stmt = select(BilateralSentimentTable).where(
            BilateralSentimentTable.panel_id == metrics.session_id,
            BilateralSentimentTable.from_country == metrics.actor_a_id,
            BilateralSentimentTable.to_country == metrics.actor_b_id,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            row.vote_affinity = metrics.vote_affinity
            row.alliance_score = metrics.alliance_score
            row.structural_distance = metrics.structural_distance
            row.discourse_sentiment_delta = metrics.discourse_sentiment_delta
            row.maoz_diplomatic_distance = metrics.diplomatic_distance
            row.maoz_affinity_score = metrics.affinity_score
            await session.flush()
        else:
            # If no bilateral record exists, we might need to create a stub or log a warning.
            # In Phase 4, assemble_network should ensure bilateral records exist from Faz 3.
            pass

    async def get_by_pair(
        self, from_country: str, to_country: str, panel_id: str
    ) -> BilateralSentiment | None:
        result = await self._session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.panel_id == panel_id,
                BilateralSentimentTable.from_country == from_country,
                BilateralSentimentTable.to_country == to_country,
            )
        )
        row = result.scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def get_all_for_panel(self, panel_id: str) -> list[BilateralSentiment]:
        result = await self._session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.panel_id == panel_id
            )
        )
        return [row.to_domain() for row in result.scalars().all()]


class DiscourseFlowRepository:
    """IDiscourseFlowRepository Protocol'ünün SQLAlchemy implementasyonu."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, flow: DiscourseFlow) -> None:
        row = DiscourseFlowTable.from_domain(flow)
        self._session.add(row)
        await self._session.flush()

    async def save_batch(self, flows: Sequence[DiscourseFlow]) -> None:
        rows = [DiscourseFlowTable.from_domain(f) for f in flows]
        self._session.add_all(rows)
        await self._session.flush()

    async def get_edges_for_panel(self, panel_id: str) -> list[DiscourseFlow]:
        result = await self._session.execute(
            select(DiscourseFlowTable).where(DiscourseFlowTable.panel_id == panel_id)
        )
        return [row.to_domain() for row in result.scalars().all()]


class TopicSynthesisRepository:
    """ITopicSynthesisRepository Protocol'ünün SQLAlchemy implementasyonu."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, synthesis: TopicSynthesis) -> TopicSynthesis:
        existing = await self.get_by_country(synthesis.panel_id, synthesis.country)
        if existing is not None:
            result = await self._session.execute(
                select(TopicMatrixTable).where(
                    TopicMatrixTable.panel_id == synthesis.panel_id,
                    TopicMatrixTable.country == synthesis.country,
                )
            )
            row = result.scalar_one()
            row.topic_scores = synthesis.topic_scores or {}
            row.dominant_topic = synthesis.topic_label
        else:
            row = TopicMatrixTable.from_domain(synthesis)
            self._session.add(row)

        await self._session.flush()
        return row.to_domain()

    async def get_by_country(
        self, panel_id: str, country: str
    ) -> TopicSynthesis | None:
        result = await self._session.execute(
            select(TopicMatrixTable).where(
                TopicMatrixTable.panel_id == panel_id,
                TopicMatrixTable.country == country,
            )
        )
        row = result.scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def get_all_for_panel(self, panel_id: str) -> list[TopicSynthesis]:
        result = await self._session.execute(
            select(TopicMatrixTable).where(TopicMatrixTable.panel_id == panel_id)
        )
        return [row.to_domain() for row in result.scalars().all()]
