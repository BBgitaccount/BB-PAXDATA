from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.segment import Segment as SegmentDomain
    from bb_paxdata.infrastructure.ai.prompt_registry import PromptRegistry

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from bb_paxdata.application.domain.models.analysis import SegmentInsight
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

        return cast("PromptRegistry", DummyRegistry())


logger = structlog.get_logger(__name__)


class SegmentRepository(BaseRepository[Segment]):
    """Async repository for Segment ORM model."""

    model_class = Segment

    async def get(self, seg_id: str) -> Segment | None:
        """Get a segment by ID."""
        return await self.get_by_id(seg_id)

    async def add(self, entity: Any) -> Segment:
        """Add a segment (supports domain model or ORM model)."""
        from bb_paxdata.application.domain.models.segment import (
            Segment as SegmentDomain,
        )

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
        self, file_id: str | None = None
    ) -> Sequence[Segment]:
        """Get segments that don't have AI insights yet."""
        stmt = (
            select(Segment)
            .outerjoin(AISegmentInsight, Segment.seg_id == AISegmentInsight.seg_id)
            .where(AISegmentInsight.seg_id.is_(None))
        )
        if file_id:
            stmt = stmt.where(Segment.file_id == file_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

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
                    file_id=segment.file_id,
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

    async def get_by_panel(self, file_id: str) -> Sequence[Segment]:
        """Get all segments for a specific panel."""
        stmt = select(Segment).where(Segment.file_id == file_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_domain_by_panel(self, file_id: str) -> list[SegmentDomain]:
        """Get all segments for a specific panel as domain models, ordered by seq_order."""

        stmt = (
            select(Segment)
            .where(Segment.file_id == file_id)
            .order_by(Segment.seq_order)
        )
        result = await self._session.execute(stmt)
        segments = result.scalars().all()
        return [s.to_domain() for s in segments]

    async def get_speaker_segments(
        self, speaker_name: str, file_id: str | None = None
    ) -> Sequence[Segment]:
        """Get segments for a specific speaker."""
        stmt = select(Segment).where(Segment.speaker_name == speaker_name)
        if file_id:
            stmt = stmt.where(Segment.file_id == file_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_with_insights(self, file_id: str | None = None) -> Sequence[Segment]:
        """Get segments that have AI insights."""
        stmt = (
            select(Segment)
            .join(AISegmentInsight, Segment.seg_id == AISegmentInsight.seg_id)
            .options(joinedload(Segment.ai_insight))
        )
        if file_id:
            stmt = stmt.where(Segment.file_id == file_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

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

    async def search_meilisearch(
        self,
        query: str,
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        limit: int = 20,
    ) -> list[Segment]:
        """Full-text search over segments using Meilisearch."""
        try:
            from bb_paxdata.infrastructure.search.meilisearch_client import (
                search_segments,
            )

            filters = []
            if file_id:
                filters.append(f"file_id = '{file_id}'")
            if country:
                filters.append(f"country = '{country}'")
            if speaker_name:
                filters.append(f"speaker_name = '{speaker_name}'")

            filter_str = " AND ".join(filters) if filters else None

            result = await search_segments(
                query=query,
                filters=filter_str,
                limit=limit,
            )

            hits = result.get("hits", [])
            seg_ids = [hit["seg_id"] for hit in hits]

            # Fetch full Segment objects from database
            stmt = select(Segment).where(Segment.seg_id.in_(seg_ids))
            db_result = await self._session.execute(stmt)
            segments = db_result.scalars().all()

            # Return in the same order as Meilisearch results
            seg_dict = {s.seg_id: s for s in segments}
            return [seg_dict[sid] for sid in seg_ids if sid in seg_dict]

        except Exception as e:
            logger.warning(
                "meilisearch_search_failed",
                query=query[:100],
                error=str(e),
            )
            # Fallback to SQL LIKE search
            stmt = select(Segment).where(Segment.text.ilike(f"%{query}%"))
            if file_id:
                stmt = stmt.where(Segment.file_id == file_id)
            if country:
                stmt = stmt.where(Segment.country == country)
            if speaker_name:
                stmt = stmt.where(Segment.speaker_name == speaker_name)
            stmt = stmt.limit(limit)

            result = await self._session.execute(stmt)
            return result.scalars().all()  # type: ignore[no-any-return]

    async def index_to_meilisearch(self, segments: list[Segment]) -> None:
        """Index segments to Meilisearch for full-text search."""
        try:
            from bb_paxdata.infrastructure.search.meilisearch_client import (
                index_segments,
            )

            documents = []
            for seg in segments:
                documents.append(
                    {
                        "seg_id": seg.seg_id,
                        "file_id": seg.file_id,
                        "text": seg.text,
                        "speaker_name": seg.speaker_name,
                        "country": seg.country,
                        "dominant_topic": seg.dominant_topic,
                        "key_phrases": seg.key_phrases,
                        "emotion_category": seg.emotion_category,
                        "risk_score": seg.risk_score,
                        "duration_sec": seg.duration_sec,
                    }
                )

            await index_segments(documents)
            logger.info(
                "segments_indexed_to_meilisearch",
                count=len(segments),
            )
        except Exception as e:
            logger.warning(
                "segments_index_to_meilisearch_failed",
                error=str(e),
            )
