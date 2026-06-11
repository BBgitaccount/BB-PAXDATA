from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.infrastructure.db.topic_models import TopicAssignmentORM


class TopicAssignmentRepository:
    """SQLAlchemy 2.0 async implementation of ITopicAssignmentRepository.

    Encapsulates all TopicAssignmentORM access so that use cases and pipeline
    stages interact only through the ITopicAssignmentRepository protocol,
    maintaining the ports-and-adapters boundary.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        segment_id: str,
        analysis_id: str,
        synthesis: TopicSynthesis,
        model_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update a TopicAssignmentORM row.

        Uses analysis_id as the unique lookup key. If a row already exists,
        updates topic_scores, topic_label, ctfidf_keywords, and model_metadata
        in-place. Calls session.flush() to propagate within the transaction.
        """
        result = await self._session.execute(
            select(TopicAssignmentORM).where(
                TopicAssignmentORM.analysis_id == analysis_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.primary_topic = synthesis.dominant_topic or "-1"
            existing.topic_scores = synthesis.topic_scores or {}
            existing.topic_label = synthesis.topic_label
            existing.ctfidf_keywords = synthesis.topic_keywords or {}
            existing.model_metadata = model_metadata or {}
        else:
            row = TopicAssignmentORM(
                segment_id=segment_id,
                analysis_id=analysis_id,
                primary_topic=synthesis.dominant_topic or "-1",
                topic_scores=synthesis.topic_scores or {},
                topic_label=synthesis.topic_label,
                ctfidf_keywords=synthesis.topic_keywords or {},
                model_metadata=model_metadata or {},
            )
            self._session.add(row)

        await self._session.flush()

    async def get_by_analysis_id(self, analysis_id: str) -> dict[str, Any] | None:
        """Return raw field dict for the given analysis_id, or None."""
        result = await self._session.execute(
            select(TopicAssignmentORM).where(
                TopicAssignmentORM.analysis_id == analysis_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "segment_id": row.segment_id,
            "analysis_id": row.analysis_id,
            "primary_topic": row.primary_topic,
            "topic_scores": row.topic_scores,
            "topic_label": row.topic_label,
            "ctfidf_keywords": row.ctfidf_keywords,
            "model_metadata": row.model_metadata,
        }

    async def delete_by_segment_prefix(self, file_id: str) -> int:
        """Delete all rows where segment_id starts with 'seg_{file_id}_'."""
        stmt = delete(TopicAssignmentORM).where(
            TopicAssignmentORM.segment_id.like(f"seg_{file_id}_%")
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]
