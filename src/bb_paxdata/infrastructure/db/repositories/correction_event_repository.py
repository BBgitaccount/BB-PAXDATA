"""Repository implementation for Correction Events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.correction_event import (
    CorrectionEvent,
    CorrectionStats,
)
from bb_paxdata.infrastructure.db.correction_event_table import CorrectionEventORM


class CorrectionEventRepository:
    """Repository for append-only correction events."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, event: CorrectionEvent) -> CorrectionEvent:
        """
        Save a new correction event.

        This is append-only - once saved, events cannot be modified or deleted.
        """
        orm = CorrectionEventORM.from_domain_model(event)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_domain_model()

    async def get_by_id(self, event_id: str) -> CorrectionEvent | None:
        """Retrieve a correction event by ID."""
        stmt = select(CorrectionEventORM).where(CorrectionEventORM.id == event_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if orm:
            return orm.to_domain_model()
        return None

    async def get_by_sentence_id(self, sentence_id: str) -> Sequence[CorrectionEvent]:
        """Retrieve all correction events for a specific sentence."""
        stmt = (
            select(CorrectionEventORM)
            .where(CorrectionEventORM.sentence_id == sentence_id)
            .order_by(CorrectionEventORM.timestamp.desc())
        )
        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        return [orm.to_domain_model() for orm in orms]

    async def list(
        self,
        field_corrected: str | None = None,
        prompt_version: str | None = None,
        corrector_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CorrectionEvent]:
        """List correction events with optional filters."""
        conditions = []

        if field_corrected:
            conditions.append(CorrectionEventORM.field_corrected == field_corrected)
        if prompt_version:
            conditions.append(CorrectionEventORM.prompt_version == prompt_version)
        if corrector_id:
            conditions.append(CorrectionEventORM.corrector_id == corrector_id)
        if start_date:
            conditions.append(CorrectionEventORM.timestamp >= start_date)
        if end_date:
            conditions.append(CorrectionEventORM.timestamp <= end_date)

        stmt = (
            select(CorrectionEventORM)
            .where(and_(*conditions) if conditions else True)
            .order_by(CorrectionEventORM.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        return [orm.to_domain_model() for orm in orms]

    async def get_recent(self, limit: int = 100) -> Sequence[CorrectionEvent]:
        """Get the most recent correction events."""
        stmt = (
            select(CorrectionEventORM)
            .order_by(CorrectionEventORM.timestamp.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        return [orm.to_domain_model() for orm in orms]

    async def get_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> CorrectionStats:
        """
        Compute correction statistics.

        Returns total corrections, breakdown by field and prompt version,
        high-confidence error count, average confidence, and correction rate.
        """
        conditions = []
        if start_date:
            conditions.append(CorrectionEventORM.timestamp >= start_date)
        if end_date:
            conditions.append(CorrectionEventORM.timestamp <= end_date)

        base_query = select(CorrectionEventORM).where(
            and_(*conditions) if conditions else True
        )

        # Total corrections
        total_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self._session.execute(total_stmt)
        total_corrections = total_result.scalar() or 0

        if total_corrections == 0:
            return CorrectionStats(
                total_corrections=0,
                by_field={},
                by_prompt_version={},
                high_confidence_errors=0,
                average_confidence=0.0,
                correction_rate=0.0,
            )

        # By field
        field_stmt = (
            select(
                CorrectionEventORM.field_corrected,
                func.count().label("count"),
            )
            .where(and_(*conditions) if conditions else True)
            .group_by(CorrectionEventORM.field_corrected)
        )
        field_result = await self._session.execute(field_stmt)
        by_field = {row.field_corrected: row.count for row in field_result}

        # By prompt version
        prompt_stmt = (
            select(
                CorrectionEventORM.prompt_version,
                func.count().label("count"),
            )
            .where(and_(*conditions) if conditions else True)
            .group_by(CorrectionEventORM.prompt_version)
        )
        prompt_result = await self._session.execute(prompt_stmt)
        by_prompt_version = {row.prompt_version: row.count for row in prompt_result}

        # High confidence errors (confidence > 0.7)
        high_conf_stmt = select(func.count()).select_from(
            select(CorrectionEventORM)
            .where(
                and_(
                    CorrectionEventORM.ai_confidence > 0.7,
                    *(conditions if conditions else []),
                )
            )
            .subquery()
        )
        high_conf_result = await self._session.execute(high_conf_stmt)
        high_confidence_errors = high_conf_result.scalar() or 0

        # Average confidence
        avg_conf_stmt = select(func.avg(CorrectionEventORM.ai_confidence)).where(
            and_(*conditions) if conditions else True
        )
        avg_conf_result = await self._session.execute(avg_conf_stmt)
        average_confidence = avg_conf_result.scalar() or 0.0

        # Correction rate (corrections / total analyzed)
        # This is a placeholder - in production, you'd need to track total analyzed sentences
        correction_rate = 0.0  # TODO: Implement based on actual analyzed count

        return CorrectionStats(
            total_corrections=total_corrections,
            by_field=by_field,
            by_prompt_version=by_prompt_version,
            high_confidence_errors=high_confidence_errors,
            average_confidence=float(average_confidence),
            correction_rate=correction_rate,
        )

    async def get_field_distribution(
        self,
        field: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get correction delta distribution for a specific field.

        Returns statistics about how values are being corrected for this field.
        """
        conditions = [CorrectionEventORM.field_corrected == field]
        if start_date:
            conditions.append(CorrectionEventORM.timestamp >= start_date)
        if end_date:
            conditions.append(CorrectionEventORM.timestamp <= end_date)

        stmt = (
            select(CorrectionEventORM)
            .where(and_(*conditions))
            .order_by(CorrectionEventORM.timestamp.desc())
        )

        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        events = [orm.to_domain_model() for orm in orms]

        # Compute delta distribution
        deltas = []
        for event in events:
            delta = event.compute_delta()
            deltas.append(delta)

        return {
            "field": field,
            "total_corrections": len(events),
            "deltas": deltas[:100],  # Limit to recent 100 for performance
            "average_confidence": (
                sum(e.ai_confidence for e in events) / len(events) if events else 0.0
            ),
        }

    async def get_prompt_version_comparison(
        self, version1: str, version2: str
    ) -> dict[str, Any]:
        """
        Compare correction rates between two prompt versions.

        Returns statistics comparing the error rates and patterns between versions.
        """
        conditions_v1 = [CorrectionEventORM.prompt_version == version1]
        conditions_v2 = [CorrectionEventORM.prompt_version == version2]

        stmt_v1 = select(func.count()).select_from(
            select(CorrectionEventORM).where(and_(*conditions_v1)).subquery()
        )
        stmt_v2 = select(func.count()).select_from(
            select(CorrectionEventORM).where(and_(*conditions_v2)).subquery()
        )

        result_v1 = await self._session.execute(stmt_v1)
        result_v2 = await self._session.execute(stmt_v2)

        count_v1 = result_v1.scalar() or 0
        count_v2 = result_v2.scalar() or 0

        return {
            "version1": version1,
            "version1_corrections": count_v1,
            "version2": version2,
            "version2_corrections": count_v2,
            "difference": count_v2 - count_v1,
            "percent_change": (
                ((count_v2 - count_v1) / count_v1 * 100) if count_v1 > 0 else 0.0
            ),
        }
