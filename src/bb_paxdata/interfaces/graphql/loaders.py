# src/bb_paxdata/interfaces/graphql/loaders.py
from __future__ import annotations

import strawberry
from aiodataloader import DataLoader
from bb_paxdata.infrastructure.db.models import Segment, Sentence
from bb_paxdata.interfaces.graphql.types import SegmentType, SentenceType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


class SegmentLoader(DataLoader):
    """
    N+1 problemini çözer: Analysis → Segment ilişkisinde
    N ayrı SELECT yerine tek bir SELECT ... WHERE file_id IN (...) çağrısı yapılır.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        super().__init__(max_batch_size=100)
        self.db_session = db_session

    async def batch_load_fn(
        self, analysis_ids: list[str]
    ) -> list[list[SegmentType] | Exception]:
        try:
            query = (
                select(Segment)
                .where(Segment.file_id.in_(analysis_ids))
                .order_by(Segment.seq_order)
            )
            result = await self.db_session.execute(query)
            segments = result.scalars().all()

            mapping: dict[str, list[SegmentType]] = {aid: [] for aid in analysis_ids}
            for seg in segments:
                mapping[str(seg.file_id)].append(
                    SegmentType(
                        id=strawberry.ID(seg.seg_id),
                        segment_index=seg.seq_order or 0,
                        summary=seg.text or "",
                        risk_level=str(seg.risk_score),
                    )
                )
            return [mapping[aid] for aid in analysis_ids]
        except Exception as exc:
            return [exc] * len(analysis_ids)


class SentenceLoader(DataLoader):
    """Segment → Sentence ilişkisi için DataLoader."""

    def __init__(self, db_session: AsyncSession) -> None:
        super().__init__(max_batch_size=500)
        self.db_session = db_session

    async def batch_load_fn(
        self, segment_ids: list[str]
    ) -> list[list[SentenceType] | Exception]:
        try:
            query = (
                select(Sentence)
                .where(Sentence.seg_id.in_(segment_ids))
                .order_by(Sentence.sent_order)
            )
            result = await self.db_session.execute(query)
            sentences = result.scalars().all()

            mapping: dict[str, list[SentenceType]] = {sid: [] for sid in segment_ids}
            for s in sentences:
                mapping[str(s.seg_id)].append(
                    SentenceType(
                        id=strawberry.ID(s.sent_id),
                        sentence_index=s.sent_order or 0,
                        text=s.text or "",
                        risk_score=float(s.risk_score or 0.0),
                        sentiment_score=float(s.vader_compound or 0.0),
                        power_level=float(s.power_level or 0.0),
                        uncertainty_score=getattr(s, "uncertainty_score", 0.0),
                    )
                )
            return [mapping[sid] for sid in segment_ids]
        except Exception as exc:
            return [exc] * len(segment_ids)
