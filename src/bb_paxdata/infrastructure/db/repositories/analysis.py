from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import delete, func, select

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.ai.prompt_registry import PromptRegistry

from bb_paxdata.domain.models.analysis import Analysis as AnalysisDomain
from bb_paxdata.domain.models.analysis import SentenceAnalysis
from bb_paxdata.infrastructure.db.models import (
    AICache,
    AIFailAnalysis,
    AIFailPattern,
    AISentenceAnalysis,
    AIValidationLog,
)
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


class AnalysisRepository(BaseRepository[AISentenceAnalysis]):
    """Async repository for AISentenceAnalysis ORM model."""

    model_class = AISentenceAnalysis

    async def get_failures(self, panel_id: str | None = None) -> list[AnalysisDomain]:
        """Get analysis failures."""
        fail = func.lower(AISentenceAnalysis.overall_logic_check) == "fail"
        stmt = select(AISentenceAnalysis).where(fail)
        if panel_id is not None:
            stmt = stmt.where(AISentenceAnalysis.panel_id == panel_id)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [r.to_domain() for r in rows]

    async def insert_sentence_analysis(
        self,
        analysis: SentenceAnalysis,
        prompt_name: str = "sentence_analysis",
    ) -> None:
        """
        Cümle analizini DB'ye yazar.
        prompt_version otomatik olarak PromptRegistry'den alınır.
        """
        if getattr(analysis, "prompt_version", None) is None:
            try:
                analysis = analysis.model_copy(
                    update={
                        "prompt_version": get_prompt_registry().get_version_string(
                            prompt_name
                        )
                    }
                )
            except (KeyError, Exception):
                pass  # Registry erişilemezse prompt_version NULL kalır

        await self.save_sentence_analysis(analysis)

    async def save_sentence_analysis(self, analysis: Any) -> None:
        """Save sentence analysis (supports domain model or ORM model)."""
        from bb_paxdata.domain.models.analysis import Analysis as AnalysisDomain

        if isinstance(analysis, AnalysisDomain):
            if analysis.sentence_id is None:
                raise ValueError("sentence_id cannot be None")
            orm = AISentenceAnalysis.from_domain(analysis, sent_id=analysis.sentence_id)
        else:
            orm = analysis
        self._session.add(orm)
        await self._session.flush()

    async def get_sentence_analysis(self, sent_id: str) -> AnalysisDomain | None:
        """Get analysis for a sentence."""
        stmt = select(AISentenceAnalysis).where(AISentenceAnalysis.sent_id == sent_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm else None

    async def save_validation_log(self, validation: Any) -> None:
        """Save validation log."""
        from bb_paxdata.domain.models.validation_result import (
            ValidationResult as ValidationDomain,
        )

        if isinstance(validation, ValidationDomain):
            orm = AIValidationLog.from_domain(validation, sent_id=validation.entity_id)
        else:
            orm = validation
        self._session.add(orm)
        await self._session.flush()

    async def get_validation_log(self, sent_id: str) -> list[Any]:
        """Get validation logs for a sentence."""
        stmt = select(AIValidationLog).where(AIValidationLog.sent_id == sent_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_cache(self, cache_hash: str) -> Any | None:
        """Get cached AI response."""
        stmt = select(AICache).where(AICache.hash == cache_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm else None

    async def set_cache(
        self, cache_hash: str, result_json: str, model_used: str, backend_used: str
    ) -> None:
        """Set cached AI response."""
        stmt = select(AICache).where(AICache.hash == cache_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.result_json = result_json
            orm.model_used = model_used
            orm.backend_used = backend_used
        else:
            orm = AICache(
                hash=cache_hash,
                result_json=result_json,
                model_used=model_used,
                backend_used=backend_used,
            )
            self._session.add(orm)
        await self._session.flush()

    async def upsert(self, record: AISentenceAnalysis) -> AISentenceAnalysis:
        """Insert or replace a record (INSERT OR REPLACE semantics)."""
        # Delete existing record with same sent_id and prompt_version
        stmt = delete(AISentenceAnalysis).where(
            AISentenceAnalysis.sent_id == record.sent_id,
            AISentenceAnalysis.prompt_version == record.prompt_version,
        )
        await self._session.execute(stmt)

        # Insert new record
        self._session.add(record)
        await self._session.flush()
        return record

    async def bulk_upsert(self, records: list[AISentenceAnalysis]) -> int:
        """Bulk upsert records and return count of inserted records."""
        if not records:
            return 0

        # Group records by sent_id and prompt_version for efficient deletion
        unique_keys = {(r.sent_id, r.prompt_version) for r in records}

        # Delete existing records
        for sent_id, prompt_version in unique_keys:
            stmt = delete(AISentenceAnalysis).where(
                AISentenceAnalysis.sent_id == sent_id,
                AISentenceAnalysis.prompt_version == prompt_version,
            )
            await self._session.execute(stmt)

        # Insert new records
        self._session.add_all(records)
        await self._session.flush()
        return len(records)

    async def get_latest_by_sentence(self, sent_id: str) -> AISentenceAnalysis | None:
        """Get the latest analysis for a sentence by prompt_version."""
        stmt = (
            select(AISentenceAnalysis)
            .where(AISentenceAnalysis.sent_id == sent_id)
            .order_by(AISentenceAnalysis.prompt_version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_fail_analyses(
        self, panel_id: str | None = None, check_type: str | None = None
    ) -> Sequence[AISentenceAnalysis]:
        """Get analyses that failed logic checks."""
        stmt = select(AISentenceAnalysis).where(
            AISentenceAnalysis.logic_result == "FAIL"
        )
        if panel_id:
            stmt = stmt.where(AISentenceAnalysis.panel_id == panel_id)

        result = await self._session.execute(stmt)
        return cast(Sequence[AISentenceAnalysis], result.scalars().all())

    async def get_backend_stats(self) -> dict[str, Any]:
        """Get backend statistics: total requests, avg latency, error rate."""
        # Total requests by backend
        total_requests_stmt = (
            select(
                AISentenceAnalysis.backend,
                func.count(AISentenceAnalysis.ai_id).label("total_requests"),
            )
            .where(AISentenceAnalysis.backend.is_not(None))
            .group_by(AISentenceAnalysis.backend)
        )

        # Average latency by backend
        avg_latency_stmt = (
            select(
                AISentenceAnalysis.backend,
                func.avg(AISentenceAnalysis.latency_ms).label("avg_latency"),
            )
            .where(
                AISentenceAnalysis.backend.is_not(None),
                AISentenceAnalysis.latency_ms.is_not(None),
            )
            .group_by(AISentenceAnalysis.backend)
        )

        # Error count by backend (logic_result = 'FAIL')
        error_count_stmt = (
            select(
                AISentenceAnalysis.backend,
                func.count(AISentenceAnalysis.ai_id).label("error_count"),
            )
            .where(
                AISentenceAnalysis.backend.is_not(None),
                AISentenceAnalysis.logic_result == "FAIL",
            )
            .group_by(AISentenceAnalysis.backend)
        )

        # Execute all queries
        total_result = await self._session.execute(total_requests_stmt)
        latency_result = await self._session.execute(avg_latency_stmt)
        error_result = await self._session.execute(error_count_stmt)

        # Build stats dictionary
        stats: dict[str, Any] = {}

        # Process total requests
        for row in total_result:
            backend = row.backend
            if backend not in stats:
                stats[backend] = {}
            stats[backend]["total_requests"] = row.total_requests

        # Process average latency
        for row in latency_result:
            backend = row.backend
            if backend not in stats:
                stats[backend] = {}
            stats[backend]["avg_latency_ms"] = (
                float(row.avg_latency) if row.avg_latency else 0
            )

        # Process error counts and calculate error rates
        for row in error_result:
            backend = row.backend
            if backend not in stats:
                stats[backend] = {}
            stats[backend]["error_count"] = row.error_count

            # Calculate error rate
            total_requests = stats[backend].get("total_requests", 0)
            if total_requests > 0:
                stats[backend]["error_rate"] = row.error_count / total_requests
            else:
                stats[backend]["error_rate"] = 0

        # Fill missing error counts and rates
        for _, backend_stats in stats.items():
            if "error_count" not in backend_stats:
                backend_stats["error_count"] = 0
                backend_stats["error_rate"] = 0

        return stats

    async def save_fail_analysis(self, fail_analysis: AIFailAnalysis) -> None:
        """Save AI failure analysis and update patterns."""
        self._session.add(fail_analysis)
        await self._session.flush()

        # Update pattern registry
        await self.update_fail_patterns(fail_analysis)

    async def update_fail_patterns(self, fail_analysis: AIFailAnalysis) -> None:
        """Update or create a failure pattern in the registry.

        Logic:
        - Match on (fail_category, check_type, negation_type, speaker_name)
        - If exists: update recurrence_count, averages, and last_seen_at
        - If not: create new pattern
        """
        # Search for existing pattern
        stmt = select(AIFailPattern).where(
            AIFailPattern.fail_category == fail_analysis.fail_category,
            AIFailPattern.check_type == fail_analysis.check_type,
            AIFailPattern.negation_type == fail_analysis.negation_type,
            AIFailPattern.speaker_name == fail_analysis.speaker_name,
        )
        result = await self._session.execute(stmt)
        pattern = result.scalar_one_or_none()

        if pattern:
            # Update existing pattern
            pattern.recurrence_count += 1
            # Update rolling averages (simplified)
            pattern.avg_discrepancy = (
                (pattern.avg_discrepancy * (pattern.recurrence_count - 1))
                + (fail_analysis.discrepancy_score or 0.0)
            ) / pattern.recurrence_count
            pattern.avg_ai_confidence = (
                (pattern.avg_ai_confidence * (pattern.recurrence_count - 1))
                + (fail_analysis.confidence_score or 0.0)
            ) / pattern.recurrence_count

            # Update panel list
            panels = set((pattern.affected_panels or "").split(","))
            if fail_analysis.panel_id:
                panels.add(fail_analysis.panel_id)
            pattern.affected_panels = ",".join(filter(None, panels))

            pattern.last_seen_at = func.now()
        else:
            # Create new pattern
            new_pattern = AIFailPattern(
                fail_category=fail_analysis.fail_category or "diger",
                negation_type=fail_analysis.negation_type,
                check_type=fail_analysis.check_type,
                speaker_name=fail_analysis.speaker_name,
                country=fail_analysis.country,
                power_level_avg=float(fail_analysis.power_level or 0),
                avg_discrepancy=fail_analysis.discrepancy_score or 0.0,
                avg_ai_confidence=fail_analysis.confidence_score or 0.0,
                dominant_negation_type=fail_analysis.negation_type,
                affected_panels=fail_analysis.panel_id,
                example_sent_id=fail_analysis.sent_id,
                example_sentence=fail_analysis.original_sentence,
                example_explanation=fail_analysis.fail_reason,
                recurrence_count=1,
                first_seen_at=func.now(),
                last_seen_at=func.now(),
            )
            self._session.add(new_pattern)

        await self._session.flush()
