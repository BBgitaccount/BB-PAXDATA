# src/bb_paxdata/infrastructure/db/repositories/visualization_repository.py

from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)
from bb_paxdata.infrastructure.db.country_models import (
    BilateralSentimentTable,
    CountryReferenceTable,
)
from bb_paxdata.infrastructure.db.models import (
    CountryPairSentiment,
    CountryStat,
    File,
)


class VisualizationRepository(IVisualizationRepository):
    """
    SQLAlchemy 2.0 concrete implementation of IVisualizationRepository.
    Uses async session and groups queries to prevent N+1 queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_country_reference_aggregates(
        self, session_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            CountryReferenceTable.speaker_country,
            func.count(CountryReferenceTable.id).label("total_refs"),
            func.avg(CountryReferenceTable.speaker_power_level).label("avg_power"),
            func.sum(
                case((CountryReferenceTable.reference_context == "PRAISE", 1), else_=0)
            ).label("praise_cnt"),
            func.sum(
                case(
                    (CountryReferenceTable.reference_context == "ACCUSATION", 1),
                    else_=0,
                )
            ).label("accusation_cnt"),
            func.sum(
                case(
                    (CountryReferenceTable.reference_context == "NEUTRAL_MENTION", 1),
                    else_=0,
                )
            ).label("neutral_cnt"),
        )
        if session_ids:
            stmt = stmt.where(CountryReferenceTable.file_id.in_(session_ids))
        stmt = stmt.group_by(CountryReferenceTable.speaker_country)

        res = await self.session.execute(stmt)
        return [
            {
                "speaker_country": r.speaker_country,
                "total_refs": r.total_refs,
                "avg_power": float(r.avg_power or 0.5),
                "praise_cnt": int(r.praise_cnt or 0),
                "accusation_cnt": int(r.accusation_cnt or 0),
                "neutral_cnt": int(r.neutral_cnt or 0),
            }
            for r in res.all()
        ]

    async def get_country_stats(
        self, session_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            CountryStat.country,
            CountryStat.file_id,
            CountryStat.avg_sentiment,
            CountryStat.dominant_emotion,
        )
        if session_ids:
            stmt = stmt.where(CountryStat.file_id.in_(session_ids))

        res = await self.session.execute(stmt)
        return [
            {
                "country": r.country,
                "file_id": r.file_id,
                "avg_sentiment": (
                    float(r.avg_sentiment or 0.0)
                    if r.avg_sentiment is not None
                    else 0.0
                ),
                "dominant_emotion": r.dominant_emotion,
            }
            for r in res.all()
        ]

    async def get_bilateral_sentiment_aggregates(
        self,
        session_ids: list[str] | None = None,
        relationship_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(
            BilateralSentimentTable.from_country,
            BilateralSentimentTable.to_country,
            BilateralSentimentTable.file_id,
            BilateralSentimentTable.interaction_count,
            BilateralSentimentTable.avg_sentiment,
            BilateralSentimentTable.affinity_score,
            BilateralSentimentTable.power_weighted_score,
            BilateralSentimentTable.relationship_type,
        )
        conditions = []
        if session_ids:
            conditions.append(BilateralSentimentTable.file_id.in_(session_ids))
        if relationship_types:
            conditions.append(
                BilateralSentimentTable.relationship_type.in_(relationship_types)
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        res = await self.session.execute(stmt)
        return [
            {
                "from_country": r.from_country,
                "to_country": r.to_country,
                "file_id": r.file_id,
                "interaction_count": int(r.interaction_count or 0),
                "avg_sentiment": float(r.avg_sentiment or 0.0),
                "affinity_score": float(r.affinity_score or 0.0),
                "power_weighted_score": float(r.power_weighted_score or 0.0),
                "relationship_type": (
                    r.relationship_type.value
                    if hasattr(r.relationship_type, "value")
                    else r.relationship_type
                ),
            }
            for r in res.all()
        ]

    async def get_global_pair_sentiments(self) -> list[dict[str, Any]]:
        stmt = select(
            CountryPairSentiment.from_country,
            CountryPairSentiment.to_country,
            CountryPairSentiment.total_mentions,
            CountryPairSentiment.avg_sentiment,
            CountryPairSentiment.interaction_count,
            CountryPairSentiment.relationship_type,
            CountryPairSentiment.affinity_score,
        )
        res = await self.session.execute(stmt)
        return [
            {
                "from_country": r.from_country,
                "to_country": r.to_country,
                "total_mentions": int(r.total_mentions or 0),
                "avg_sentiment": (
                    float(r.avg_sentiment or 0.0)
                    if r.avg_sentiment is not None
                    else None
                ),
                "interaction_count": int(r.interaction_count or 0),
                "relationship_type": (
                    r.relationship_type.value
                    if hasattr(r.relationship_type, "value")
                    else r.relationship_type
                ),
                "affinity_score": (
                    float(r.affinity_score or 0.0)
                    if r.affinity_score is not None
                    else 0.0
                ),
            }
            for r in res.all()
        ]

    async def get_sessions_list(self) -> list[dict[str, Any]]:
        stmt = select(
            File.file_id,
            File.title,
            File.file_name,
            File.imported_at,
        ).order_by(File.imported_at.asc())
        res = await self.session.execute(stmt)
        return [
            {
                "file_id": r.file_id,
                "title": r.title,
                "file_name": r.file_name,
                "imported_at": r.imported_at,
            }
            for r in res.all()
        ]

    async def get_all_reference_counts(self) -> list[dict[str, Any]]:
        stmt = select(
            CountryReferenceTable.file_id,
            func.sum(
                case((CountryReferenceTable.reference_context == "PRAISE", 1), else_=0)
            ).label("praise_cnt"),
            func.sum(
                case(
                    (CountryReferenceTable.reference_context == "ACCUSATION", 1),
                    else_=0,
                )
            ).label("accusation_cnt"),
        ).group_by(CountryReferenceTable.file_id)

        res = await self.session.execute(stmt)
        return [
            {
                "file_id": r.file_id,
                "praise_cnt": int(r.praise_cnt or 0),
                "accusation_cnt": int(r.accusation_cnt or 0),
            }
            for r in res.all()
        ]

    async def get_reference_flows(
        self, session_id: str | None = None, context_type: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            CountryReferenceTable.speaker_country,
            CountryReferenceTable.referenced_country,
            CountryReferenceTable.reference_context,
            CountryReferenceTable.file_id,
            func.count(CountryReferenceTable.id).label("cnt"),
            func.avg(CountryReferenceTable.raw_sentiment_score).label("avg_sent"),
        )
        conditions = []
        if session_id:
            conditions.append(CountryReferenceTable.file_id == session_id)
        if context_type:
            conditions.append(CountryReferenceTable.reference_context == context_type)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.group_by(
            CountryReferenceTable.speaker_country,
            CountryReferenceTable.referenced_country,
            CountryReferenceTable.reference_context,
            CountryReferenceTable.file_id,
        )
        res = await self.session.execute(stmt)
        return [
            {
                "speaker_country": r.speaker_country,
                "referenced_country": r.referenced_country,
                "reference_context": r.reference_context,
                "file_id": r.file_id,
                "cnt": int(r.cnt or 0),
                "avg_sent": float(r.avg_sent or 0.0),
            }
            for r in res.all()
        ]

    async def get_pair_sentiments_for_country(
        self, country: str
    ) -> list[dict[str, Any]]:
        stmt = select(
            CountryPairSentiment.from_country,
            CountryPairSentiment.to_country,
            CountryPairSentiment.total_mentions,
            CountryPairSentiment.avg_sentiment,
            CountryPairSentiment.interaction_count,
            CountryPairSentiment.relationship_type,
            CountryPairSentiment.affinity_score,
        ).where(
            or_(
                CountryPairSentiment.from_country == country,
                CountryPairSentiment.to_country == country,
            )
        )
        res = await self.session.execute(stmt)
        return [
            {
                "from_country": r.from_country,
                "to_country": r.to_country,
                "total_mentions": int(r.total_mentions or 0),
                "avg_sentiment": (
                    float(r.avg_sentiment or 0.0)
                    if r.avg_sentiment is not None
                    else 0.0
                ),
                "interaction_count": int(r.interaction_count or 0),
                "relationship_type": (
                    r.relationship_type.value
                    if hasattr(r.relationship_type, "value")
                    else r.relationship_type
                ),
                "affinity_score": (
                    float(r.affinity_score or 0.0)
                    if r.affinity_score is not None
                    else 0.0
                ),
            }
            for r in res.all()
        ]

    async def get_country_stats_for_country(self, country: str) -> list[dict[str, Any]]:
        stmt = select(
            CountryStat.file_id,
            CountryStat.avg_sentiment,
            CountryStat.dominant_emotion,
        ).where(CountryStat.country == country)

        res = await self.session.execute(stmt)
        return [
            {
                "file_id": r.file_id,
                "avg_sentiment": (
                    float(r.avg_sentiment or 0.0)
                    if r.avg_sentiment is not None
                    else 0.0
                ),
                "dominant_emotion": r.dominant_emotion,
            }
            for r in res.all()
        ]

    async def get_speaker_references_summary(self, country: str) -> dict[str, Any]:
        stmt = select(
            func.avg(CountryReferenceTable.raw_sentiment_score).label("avg_sent"),
            func.count(CountryReferenceTable.id).label("cnt"),
        ).where(CountryReferenceTable.speaker_country == country)

        res = await self.session.execute(stmt)
        row = res.first()
        if row and row.cnt:
            return {
                "avg_sentiment": float(row.avg_sent or 0.0),
                "count": int(row.cnt or 0),
            }
        return {"avg_sentiment": 0.0, "count": 0}

    async def get_target_references_summary(self, country: str) -> list[dict[str, Any]]:
        stmt = (
            select(
                CountryReferenceTable.speaker_country,
                CountryReferenceTable.reference_context,
                func.avg(CountryReferenceTable.raw_sentiment_score).label("avg_sent"),
                func.count(CountryReferenceTable.id).label("cnt"),
            )
            .where(CountryReferenceTable.referenced_country == country)
            .group_by(
                CountryReferenceTable.speaker_country,
                CountryReferenceTable.reference_context,
            )
        )

        res = await self.session.execute(stmt)
        return [
            {
                "speaker_country": r.speaker_country,
                "reference_context": r.reference_context,
                "avg_sentiment": float(r.avg_sent or 0.0),
                "count": int(r.cnt or 0),
            }
            for r in res.all()
        ]
