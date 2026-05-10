"""Sentence persistence: ORM rows mapped to domain ``Sentence`` only."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.repositories.base import AbstractRepository


class SentenceRepository(AbstractRepository[Sentence]):
    """Read/write sentences as domain models (no ORM leakage)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _resolve_panel_and_seg(self, sentence: Sentence) -> tuple[str, str]:
        sid = sentence.segment_id
        if not sid:
            msg = "Sentence.segment_id is required to persist a Sentence"
            raise ValueError(msg)
        row = self._session.execute(
            select(m.Segment.panel_id).where(m.Segment.seg_id == sid)
        ).scalar_one_or_none()
        if row is None:
            msg = f"Unknown segment {sid}; create the Segment first (with panel_id set)"
            raise ValueError(msg)
        return str(row), sid

    def get(self, sent_id: str) -> Sentence | None:
        stmt = select(m.Sentence).where(m.Sentence.sent_id == sent_id)
        orm = self._session.execute(stmt).scalar_one_or_none()
        return orm.to_domain() if orm is not None else None

    def get_by_segment(self, seg_id: str) -> list[Sentence]:
        stmt = (
            select(m.Sentence)
            .where(m.Sentence.seg_id == seg_id)
            .order_by(m.Sentence.global_sent_order, m.Sentence.sent_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_panel(self, panel_id: str) -> list[Sentence]:
        stmt = (
            select(m.Sentence)
            .where(m.Sentence.panel_id == panel_id)
            .order_by(m.Sentence.global_sent_order, m.Sentence.sent_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_speaker(self, speaker_id: str) -> list[Sentence]:
        stmt = (
            select(m.Sentence)
            .where(m.Sentence.speaker_id == speaker_id)
            .order_by(m.Sentence.panel_id, m.Sentence.global_sent_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_country(
        self, country: str, panel_id: str | None = None
    ) -> list[Sentence]:
        stmt = select(m.Sentence).where(m.Sentence.country == country)
        if panel_id is not None:
            stmt = stmt.where(m.Sentence.panel_id == panel_id)
        stmt = stmt.order_by(m.Sentence.panel_id, m.Sentence.global_sent_order)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_high_risk(self, min_risk_score: int = 7) -> list[Sentence]:
        stmt = (
            select(m.Sentence)
            .where(m.Sentence.risk_score >= min_risk_score)
            .order_by(m.Sentence.risk_score.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_with_demands(self) -> list[Sentence]:
        stmt = (
            select(m.Sentence)
            .where(m.Sentence.demand_type.is_not(None))
            .order_by(m.Sentence.panel_id, m.Sentence.global_sent_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_frame(self, frame_type: str) -> list[Sentence]:
        stmt = select(m.Sentence).where(m.Sentence.dominant_frame == frame_type)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_audience(self, audience_type: str) -> list[Sentence]:
        stmt = select(m.Sentence).where(m.Sentence.audience_type == audience_type)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_by_topic(self, topic: str) -> list[Sentence]:
        stmt = select(m.Sentence).where(m.Sentence.dominant_topic == topic)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_with_anomalies(self) -> list[Sentence]:
        stmt = (
            select(m.Sentence)
            .join(
                m.AIContextualFlag,
                m.AIContextualFlag.sent_id == m.Sentence.sent_id,
            )
            .distinct()
        )
        rows = self._session.execute(stmt).unique().scalars().all()
        return [r.to_domain() for r in rows]

    def add(self, sentence: Sentence) -> None:
        pid, sid = self._resolve_panel_and_seg(sentence)
        self._session.add(m.Sentence.from_domain(sentence, seg_id=sid, panel_id=pid))

    def add_many(self, sentences: list[Sentence]) -> None:
        for s in sentences:
            self.add(s)

    def remove(self, entity: Sentence) -> None:
        orm = self._session.get(m.Sentence, entity.id)
        if orm is not None:
            self._session.delete(orm)

    def update_analysis(
        self,
        sent_id: str,
        sentiment_score: float,
        risk_score: int,
        hedging_score: float,
        politeness_ratio: float,
    ) -> None:
        orm = self._session.get(m.Sentence, sent_id)
        if orm is None:
            return
        orm.vader_compound = sentiment_score
        orm.risk_score = risk_score
        orm.hedging_score = hedging_score
        orm.politeness_ratio = politeness_ratio

    def count_by_panel(self, panel_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(m.Sentence)
            .where(m.Sentence.panel_id == panel_id)
        )
        return int(self._session.execute(stmt).scalar_one())
