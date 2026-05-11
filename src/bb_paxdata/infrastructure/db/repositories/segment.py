from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.ai.prompt_registry import PromptRegistry

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from bb_paxdata.domain.models.analysis import SegmentInsight
from bb_paxdata.infrastructure.db.models import AISegmentInsight, Segment
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

try:
    from bb_paxdata.infrastructure.ai import get_prompt_registry
except ImportError:
    # Fallback if registry is not yet available
    def get_prompt_registry() -> PromptRegistry:
        class DummyRegistry:
            def get_version_string(self, name: str) -> str | None:
                return None

        return DummyRegistry()  # type: ignore


logger = structlog.get_logger(__name__)


class SegmentRepository(BaseRepository[Segment]):
    """Async repository for Segment ORM model."""

    model_class = Segment

    async def get(self, seg_id: str) -> Segment | None:
        """Get a segment by ID."""
        return await self.get_by_id(seg_id)

    async def add(self, entity: Any) -> Segment:
        """Add a segment (supports domain model or ORM model)."""
        from bb_paxdata.domain.models.segment import Segment as SegmentDomain

        if isinstance(entity, SegmentDomain):
            orm = Segment.from_domain(entity)
        else:
            orm = entity
        return await super().add(orm)

    async def insert_segment_insight(
        self,
        seg_id: str,
        insight: SegmentInsight,
        prompt_name: str = "segment_insight",
    ) -> None:
        """
        Segment analizini DB'ye yazar.
        prompt_version otomatik olarak PromptRegistry'den alınır.
        """
        if getattr(insight, "prompt_version", None) is None:
            try:
                insight = insight.model_copy(
                    update={
                        "prompt_version": get_prompt_registry().get_version_string(
                            prompt_name
                        )
                    }
                )
            except (KeyError, Exception):
                pass

        # Use the existing update_insight method to persist
        # Assuming SegmentInsight has ai_insight text field, if not, adapt as needed.
        insight_text = getattr(insight, "segment_summary", str(insight))
        version_str = getattr(insight, "prompt_version", "v1.0") or "v1.0"
        await self.update_insight(seg_id, insight_text, version_str)

    async def get_without_insights(
        self, panel_id: str | None = None
    ) -> Sequence[Segment]:
        """Get segments that don't have AI insights yet."""
        stmt = (
            select(Segment)
            .outerjoin(AISegmentInsight, Segment.seg_id == AISegmentInsight.seg_id)
            .where(AISegmentInsight.seg_id.is_(None))
        )
        if panel_id:
            stmt = stmt.where(Segment.panel_id == panel_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_insight(self, seg_id: str, insight: str, version: str) -> None:
        """Update or create AI insight for a segment."""
        # First try to get existing insight
        stmt = select(AISegmentInsight).where(AISegmentInsight.seg_id == seg_id)
        result = await self._session.execute(stmt)
        insight_record = result.scalar_one_or_none()

        if insight_record:
            insight_record.ai_insight = insight
            insight_record.ai_insight_version = version
            insight_record.insight_generated_at = func.now()
        else:
            # Get segment info for the new insight record
            seg_stmt = select(Segment).where(Segment.seg_id == seg_id)
            seg_result = await self._session.execute(seg_stmt)
            segment = seg_result.scalar_one_or_none()

            if segment:
                insight_record = AISegmentInsight(
                    seg_id=seg_id,
                    panel_id=segment.panel_id,
                    speaker_name=segment.speaker_name,
                    country=segment.country,
                    power_level=segment.power_level,
                    ai_insight=insight,
                    ai_insight_version=version,
                    insight_generated_at=func.now(),
                    prompt_version=version,  # Store version in prompt_version as well
                )
                self._session.add(insight_record)

        await self._session.flush()

    async def get_by_panel(self, panel_id: str) -> Sequence[Segment]:
        """Get all segments for a specific panel."""
        stmt = select(Segment).where(Segment.panel_id == panel_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_speaker_segments(
        self, speaker_name: str, panel_id: str | None = None
    ) -> Sequence[Segment]:
        """Get segments for a specific speaker."""
        stmt = select(Segment).where(Segment.speaker_name == speaker_name)
        if panel_id:
            stmt = stmt.where(Segment.panel_id == panel_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_with_insights(self, panel_id: str | None = None) -> Sequence[Segment]:
        """Get segments that have AI insights."""
        stmt = (
            select(Segment)
            .join(AISegmentInsight, Segment.seg_id == AISegmentInsight.seg_id)
            .options(joinedload(Segment.ai_insight))
        )
        if panel_id:
            stmt = stmt.where(Segment.panel_id == panel_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_with_sentences_eager(self, seg_id: str) -> Segment | None:
        """Get segment with all its sentences loaded."""
        stmt = (
            select(Segment)
            .options(joinedload(Segment.sentences))
            .where(Segment.seg_id == seg_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_with_sentences(self, seg_id: str) -> Segment | None:
        """Alias for get_with_sentences_eager."""
        return await self.get_with_sentences_eager(seg_id)

    async def get_temporal_analysis(self, seg_id: str) -> Segment | None:
        """Get temporal analysis for a segment."""
        # For now, just return the segment as it has the temporal fields
        stmt = select(Segment).where(Segment.seg_id == seg_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
