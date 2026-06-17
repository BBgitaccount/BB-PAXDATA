from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.application.domain.models.country_reference import CountryReference
from bb_paxdata.application.domain.models.discourse_flow import (
    DiscourseFlow,
    DyadicMetrics,
)
from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.application.domain.services.compare_sessions_protocols import (
    IDiscourseFlowRepository,
)
from bb_paxdata.infrastructure.db.country_models import (
    BilateralSentimentTable,
    CountryReferenceTable,
    DiscourseFlowTable,
    TopicMatrixTable,
)


class CountryReferenceRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "Database session is not set on CountryReferenceRepository"
            )
        return self._session

    async def save(self, reference: CountryReference) -> None:
        row = CountryReferenceTable.from_domain(reference)
        self.session.add(row)
        await self.session.flush()

    async def save_batch(self, references: Sequence[CountryReference]) -> None:
        rows = [CountryReferenceTable.from_domain(r) for r in references]
        self.session.add_all(rows)
        await self.session.flush()

    async def get_by_panel(self, panel_id: str) -> list[CountryReference]:
        result = await self.session.execute(
            select(CountryReferenceTable).where(
                CountryReferenceTable.file_id == panel_id
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def get_by_pair(
        self, speaker: str, referenced: str, panel_id: str
    ) -> list[CountryReference]:
        result = await self.session.execute(
            select(CountryReferenceTable).where(
                CountryReferenceTable.file_id == panel_id,
                CountryReferenceTable.speaker_country == speaker,
                CountryReferenceTable.referenced_country == referenced,
            )
        )
        return [row.to_domain() for row in result.scalars().all()]


class BilateralSentimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, sentiment: BilateralSentiment) -> BilateralSentiment:
        existing = await self.get_by_pair(
            sentiment.from_country, sentiment.to_country, sentiment.panel_id
        )
        if existing is not None:
            result = await self._session.execute(
                select(BilateralSentimentTable).where(
                    BilateralSentimentTable.file_id == sentiment.panel_id,
                    BilateralSentimentTable.from_country == sentiment.from_country,
                    BilateralSentimentTable.to_country == sentiment.to_country,
                )
            )
            row = result.scalar_one()
            row.total_mentions = sentiment.total_mentions
            row.avg_sentiment = sentiment.avg_sentiment
            row.interaction_count = sentiment.interaction_count
            row.relationship_type = sentiment.relationship_type.value
            row.affinity_score = sentiment.affinity_score
            row.power_weighted_score = sentiment.power_weighted_score
            row.diplomatic_distance = sentiment.diplomatic_distance
            row.last_updated = (
                sentiment.last_updated.replace(tzinfo=None)
                if sentiment.last_updated
                else None
            )
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
        stmt = select(BilateralSentimentTable).where(
            BilateralSentimentTable.file_id == metrics.session_id,
            or_(
                and_(
                    BilateralSentimentTable.from_country == metrics.actor_a_id,
                    BilateralSentimentTable.to_country == metrics.actor_b_id,
                ),
                and_(
                    BilateralSentimentTable.from_country == metrics.actor_b_id,
                    BilateralSentimentTable.to_country == metrics.actor_a_id,
                ),
            ),
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.vote_affinity = metrics.vote_affinity
            row.alliance_score = metrics.alliance_score
            row.structural_distance = metrics.structural_distance
            row.discourse_sentiment_delta = metrics.discourse_sentiment_delta
            row.diplomatic_distance = float(metrics.diplomatic_distance or 0.0)
            row.maoz_diplomatic_distance = metrics.diplomatic_distance
            row.maoz_affinity_score = metrics.affinity_score
            await session.flush()
        else:
            pass

    async def get_by_pair(
        self, from_country: str, to_country: str, panel_id: str
    ) -> BilateralSentiment | None:
        result = await self._session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.file_id == panel_id,
                BilateralSentimentTable.from_country == from_country,
                BilateralSentimentTable.to_country == to_country,
            )
        )
        row = result.scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def get_all_for_panel(self, panel_id: str) -> list[BilateralSentiment]:
        result = await self._session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.file_id == panel_id
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def rebuild_global_country_pair_sentiments(self) -> None:
        from sqlalchemy import delete, func

        from bb_paxdata.application.domain.enums.country_enums import RelationshipType
        from bb_paxdata.infrastructure.db.models import CountryPairSentiment

        await self._session.execute(delete(CountryPairSentiment))
        stmt = select(
            BilateralSentimentTable.from_country,
            BilateralSentimentTable.to_country,
            func.sum(BilateralSentimentTable.total_mentions).label("total_mentions"),
            func.avg(BilateralSentimentTable.avg_sentiment).label("avg_sentiment"),
            func.sum(BilateralSentimentTable.interaction_count).label(
                "interaction_count"
            ),
            func.avg(BilateralSentimentTable.affinity_score).label("affinity_score"),
            func.avg(BilateralSentimentTable.power_weighted_score).label(
                "power_weighted_score"
            ),
            func.avg(BilateralSentimentTable.diplomatic_distance).label(
                "diplomatic_distance"
            ),
        ).group_by(
            BilateralSentimentTable.from_country, BilateralSentimentTable.to_country
        )
        res = await self._session.execute(stmt)
        rows = res.all()
        for r in rows:
            aff = r.affinity_score or 0.0
            if aff > 0.5:
                rel_type = RelationshipType.ALLY
            elif aff > 0.2:
                rel_type = RelationshipType.PARTNER
            elif aff < -0.5:
                rel_type = RelationshipType.ADVERSARY
            elif aff < -0.2:
                rel_type = RelationshipType.CAUTIOUS
            else:
                rel_type = RelationshipType.NEUTRAL
            cp = CountryPairSentiment(
                from_country=r.from_country,
                to_country=r.to_country,
                total_mentions=int(r.total_mentions or 0),
                avg_sentiment=(
                    float(r.avg_sentiment) if r.avg_sentiment is not None else None
                ),
                interaction_count=int(r.interaction_count or 0),
                relationship_type=rel_type,
                affinity_score=float(aff),
                power_weighted_score=float(r.power_weighted_score or 0.0),
                diplomatic_distance=float(r.diplomatic_distance or 0.0),
            )
            self._session.add(cp)
        await self._session.flush()


class DiscourseFlowRepository(IDiscourseFlowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_session(self, session_id: str) -> list[DiscourseFlow]:
        result = await self._session.execute(
            select(DiscourseFlowTable).where(DiscourseFlowTable.file_id == session_id)
        )
        return [row.to_domain() for row in result.scalars().all()]

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
            select(DiscourseFlowTable).where(DiscourseFlowTable.file_id == panel_id)
        )
        return [row.to_domain() for row in result.scalars().all()]


class TopicSynthesisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, synthesis: TopicSynthesis) -> TopicSynthesis:
        existing = await self.get_by_country(synthesis.panel_id, synthesis.country)
        if existing is not None:
            result = await self._session.execute(
                select(TopicMatrixTable).where(
                    TopicMatrixTable.file_id == synthesis.panel_id,
                    TopicMatrixTable.country == synthesis.country,
                )
            )
            row = result.scalar_one()
            row.topic_scores = synthesis.topic_scores or {}
            row.dominant_topic = synthesis.topic_label
        else:
            row = TopicMatrixTable.from_domain(synthesis)
            self._session.add(row)
        from sqlalchemy import delete

        from bb_paxdata.infrastructure.db.models import TopicMatrix as TopicMatrixORM

        await self._session.execute(
            delete(TopicMatrixORM).where(
                TopicMatrixORM.file_id == synthesis.panel_id,
                TopicMatrixORM.country == synthesis.country,
            )
        )
        if synthesis.topic_scores:
            for topic, score in synthesis.topic_scores.items():
                db_tm = TopicMatrixORM(
                    file_id=synthesis.panel_id,
                    country=synthesis.country,
                    topic=topic,
                    score=score,
                )
                self._session.add(db_tm)
        await self._session.flush()
        return row.to_domain()

    async def get_by_country(
        self, panel_id: str, country: str
    ) -> TopicSynthesis | None:
        result = await self._session.execute(
            select(TopicMatrixTable).where(
                TopicMatrixTable.file_id == panel_id,
                TopicMatrixTable.country == country,
            )
        )
        row = result.scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def get_all_for_panel(self, panel_id: str) -> list[TopicSynthesis]:
        result = await self._session.execute(
            select(TopicMatrixTable).where(TopicMatrixTable.file_id == panel_id)
        )
        return [row.to_domain() for row in result.scalars().all()]
