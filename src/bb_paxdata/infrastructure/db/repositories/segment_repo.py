"""Segment persistence with eager loading where lists are needed."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from bb_paxdata.domain.models.segment import Segment, TemporalSegmentAnalysis
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.repositories.base import AbstractRepository


class SegmentRepository(AbstractRepository[Segment]):
    """Read/write segments as domain models."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, seg_id: str) -> Segment | None:
        stmt = select(m.Segment).where(m.Segment.seg_id == seg_id)
        orm = self._session.execute(stmt).scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    def get_by_panel(self, panel_id: str) -> list[Segment]:
        stmt = (
            select(m.Segment)
            .where(m.Segment.panel_id == panel_id)
            .order_by(m.Segment.seq_order, m.Segment.global_sent_start)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_speaker(self, speaker_id: str) -> list[Segment]:
        stmt = (
            select(m.Segment)
            .where(m.Segment.speaker_id == speaker_id)
            .order_by(m.Segment.panel_id, m.Segment.seq_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_country(self, country: str) -> list[Segment]:
        stmt = (
            select(m.Segment)
            .where(m.Segment.country == country)
            .order_by(m.Segment.panel_id, m.Segment.seq_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_with_sentences(self, seg_id: str) -> Segment | None:
        stmt = (
            select(m.Segment)
            .where(m.Segment.seg_id == seg_id)
            .options(joinedload(m.Segment.sentences))
        )
        orm = self._session.execute(stmt).unique().scalar_one_or_none()
        if orm is None:
            return None
        base = orm.to_domain()
        sentences = [s.to_domain() for s in orm.sentences]
        merged: Segment = base.model_copy(update={"sentences": sentences})
        return merged

    def get_temporal_analysis(self, seg_id: str) -> TemporalSegmentAnalysis | None:
        orm = self._session.get(m.Segment, seg_id)
        if orm is None:
            return None
        return TemporalSegmentAnalysis(
            segment_id=orm.seg_id,
            intro_sentiment=float(orm.intro_sentiment),
            develop_sentiment=float(orm.develop_sentiment),
            concl_sentiment=float(orm.concl_sentiment),
            risk_trend=orm.risk_trend,
            risk_trajectory=orm.risk_trajectory,
        )

    def get_by_topic(self, topic: str) -> list[Segment]:
        stmt = select(m.Segment).where(m.Segment.dominant_topic == topic)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_high_pressure(self, min_sbi: float = 7.0) -> list[Segment]:
        stmt = (
            select(m.Segment)
            .where(m.Segment.sbi_score >= min_sbi)
            .order_by(m.Segment.sbi_score.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def add(self, segment: Segment) -> None:
        self._session.add(
            m.Segment.from_domain(segment, panel_id=segment.panel_id),
        )

    def remove(self, entity: Segment) -> None:
        orm = self._session.get(m.Segment, entity.id)
        if orm is not None:
            self._session.delete(orm)

    def update_dynamics(self, seg_id: str, sbi_score: float, dki_score: float) -> None:
        orm = self._session.get(m.Segment, seg_id)
        if orm is None:
            return
        orm.sbi_score = sbi_score
        orm.dki_score = dki_score

    def count_by_panel(self, panel_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(m.Segment)
            .where(m.Segment.panel_id == panel_id)
        )
        return int(self._session.execute(stmt).scalar_one())
