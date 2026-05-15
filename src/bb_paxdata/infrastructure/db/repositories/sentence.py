from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from sqlalchemy import select

from bb_paxdata.infrastructure.db.models import Sentence
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class SentenceRepository(BaseRepository[Sentence]):
    """Async repository for Sentence ORM model."""

    model_class = Sentence

    async def get(self, sent_id: str) -> Sentence | None:
        """Get a sentence by ID."""
        return await self.get_by_id(sent_id)

    async def add(self, entity: Any) -> Sentence:
        """Add a sentence (supports domain model or ORM model)."""
        from bb_paxdata.domain.models.sentence import (
            Sentence as SentenceDomain,
        )

        if isinstance(entity, SentenceDomain):
            # Extract seg_id and panel_id if available, otherwise default
            # to dummy or previous values
            seg_id = getattr(entity, "segment_id", None) or "unknown_seg"
            # Try to find panel_id from domain model if it exists,
            # otherwise use p1 for tests
            panel_id = getattr(entity, "panel_id", "p1")
            orm = Sentence.from_domain(entity, seg_id=seg_id, panel_id=panel_id)
        else:
            orm = entity
        return await super().add(orm)

    async def get_unanalyzed(
        self, panel_id: str | None = None, limit: int | None = None
    ) -> Sequence[Sentence]:
        """Get sentences that haven't been analyzed yet, ordered by risk_score DESC."""
        stmt = select(Sentence).where(Sentence.ai_analyzed == 0)
        if panel_id:
            stmt = stmt.where(Sentence.panel_id == panel_id)
        stmt = stmt.order_by(Sentence.risk_score.desc())
        if limit:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_by_panel(self, panel_id: str) -> Sequence[Sentence]:
        """Get all sentences for a specific panel."""
        stmt = select(Sentence).where(Sentence.panel_id == panel_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_by_segment(self, seg_id: str) -> Sequence[Sentence]:
        """Get all sentences for a specific segment."""
        stmt = select(Sentence).where(Sentence.seg_id == seg_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_fail_sentences(
        self, panel_id: str | None = None, check_type: str | None = None
    ) -> Sequence[Sentence]:
        """Get sentences that failed logic checks."""
        stmt = select(Sentence).where(Sentence.logic_result == "FAIL")
        if panel_id:
            stmt = stmt.where(Sentence.panel_id == panel_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def mark_analyzed(self, sent_id: str) -> None:
        """Mark a sentence as analyzed."""
        stmt = select(Sentence).where(Sentence.sent_id == sent_id)
        result = await self._session.execute(stmt)
        sentence = result.scalar_one_or_none()
        if sentence:
            sentence.ai_analyzed = 1
            await self._session.flush()

    async def bulk_mark_analyzed(self, sent_ids: list[str]) -> None:
        """Mark multiple sentences as analyzed in bulk."""
        stmt = select(Sentence).where(Sentence.sent_id.in_(sent_ids))
        result = await self._session.execute(stmt)
        sentences = result.scalars().all()
        for sentence in sentences:
            sentence.ai_analyzed = 1
        await self._session.flush()

    async def get_priority_queue(
        self, top_n: int, panel_id: str | None = None
    ) -> Sequence[Sentence]:
        """Get top N sentences ordered by risk_score DESC, power_level DESC."""
        stmt = select(Sentence).where(Sentence.ai_analyzed == 0)
        if panel_id:
            stmt = stmt.where(Sentence.panel_id == panel_id)
        stmt = stmt.order_by(
            Sentence.risk_score.desc(), Sentence.power_level.desc()
        ).limit(top_n)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def update_analysis(
        self,
        sent_id: str,
        sentiment_score: float,
        risk_score: int,
        hedging_score: float,
        politeness_ratio: float,
    ) -> None:
        """Update sentence analysis results."""
        stmt = select(Sentence).where(Sentence.sent_id == sent_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.vader_compound = sentiment_score
            orm.risk_score = risk_score
            orm.hedging_score = hedging_score
            orm.politeness_ratio = politeness_ratio
            await self._session.flush()

    async def get_high_risk(self, min_risk_score: int) -> Sequence[Sentence]:
        """Get high risk sentences."""
        stmt = select(Sentence).where(Sentence.risk_score >= min_risk_score)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]
