from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import delete, func, select

if TYPE_CHECKING:
    from bb_paxdata.application.consensus.dual_gate import ConsensusResult
    from bb_paxdata.infrastructure.ai.prompt_registry import PromptRegistry

from bb_paxdata.application.domain.models.analysis import Analysis as AnalysisDomain
from bb_paxdata.application.domain.models.analysis import SentenceAnalysis
from bb_paxdata.application.domain.services.compare_sessions_protocols import (
    IAnalysisRepository,
)
from bb_paxdata.infrastructure.db.models import (
    AICache,
    AIExplanationsORM,
    AIFailAnalysis,
    AIFailCache,
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


class AnalysisRepository(BaseRepository[AISentenceAnalysis], IAnalysisRepository):
    """Async repository for AISentenceAnalysis ORM model."""

    model_class = AISentenceAnalysis

    def __init__(
        self,
        session: Any,
        ai_cache_service: Any | None = None,
        ai_fail_cache_service: Any | None = None,
    ) -> None:
        super().__init__(session)
        self._ai_cache_service = ai_cache_service
        self._ai_fail_cache_service = ai_fail_cache_service

    async def get_by_session(self, session_id: str) -> list[AnalysisDomain]:
        """Get all analyses for a session."""
        stmt = select(self.model_class).where(self.model_class.file_id == session_id)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [row.to_domain() for row in rows]

    async def get_by_speaker(self, speaker_id: str) -> list[AnalysisDomain]:
        """Get all analyses for a speaker across sessions."""
        stmt = select(self.model_class).where(
            self.model_class.speaker_name == speaker_id
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [row.to_domain() for row in rows]

    async def get_failures(self, file_id: str | None = None) -> list[AnalysisDomain]:
        """Get analysis failures."""
        fail = func.lower(AISentenceAnalysis.overall_logic_check) == "fail"
        stmt = select(AISentenceAnalysis).where(fail)
        if file_id is not None:
            stmt = stmt.where(AISentenceAnalysis.file_id == file_id)
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
                analysis.prompt_version = get_prompt_registry().get_version_string(
                    prompt_name
                )
            except (KeyError, Exception):
                pass  # Registry erişilemezse prompt_version NULL kalır

        await self.save_sentence_analysis(analysis)

    async def save_sentence_analysis(
        self,
        analysis: Any,
        consensus: ConsensusResult | None = None,
    ) -> None:
        """Save sentence analysis (supports domain model or ORM model)."""
        from bb_paxdata.application.domain.models.analysis import (
            Analysis as AnalysisDomain,
        )

        if isinstance(analysis, AnalysisDomain):
            sent_id = analysis.sentence_id
            if sent_id is None:
                raise ValueError("sentence_id cannot be None")
            # If consensus was passed, we assign it to the domain model temporarily
            if consensus:
                analysis.consensus_result = consensus
            orm = AISentenceAnalysis.from_domain(analysis, sent_id=sent_id)
        else:
            orm = analysis
            if consensus:
                orm.coherence_score = consensus.coherence_score
                orm.anomaly_consensus_level = consensus.level.value
                orm.anomaly_ai_decision = consensus.ai_result.decision.value
                orm.anomaly_ai_reasoning = consensus.ai_result.reasoning
                orm.anomaly_detected_subtype = consensus.ai_result.detected_subtype
        self._session.add(orm)
        await self._session.flush()

    async def save_sentence_analysis_with_metadata(
        self,
        analysis: AnalysisDomain,
        *,
        sent_id: str,
        file_id: str | None = None,
        sentence_code: str | None = None,
        speaker_name: str | None = None,
        country: str | None = None,
        power_level: int = 0,
        global_sent_order: int | None = None,
        sentiment_score: float | None = None,
        sentiment_category: str | None = None,
        risk_score: int | None = None,
        ai_sentiment: str | None = None,
        ai_risk_score: float | None = None,
        ai_frame_type: str | None = None,
        hedging_score: float | None = None,
        politeness_score: float | None = None,
        logic_result: str | None = None,
    ) -> AISentenceAnalysis:
        """Save sentence analysis by mapping from domain model and setting metadata fields."""
        orm = AISentenceAnalysis.from_domain(
            analysis,
            sent_id=sent_id,
            file_id=file_id,
            sentence_code=sentence_code,
            speaker_name=speaker_name,
            country=country,
            power_level=power_level,
            global_sent_order=global_sent_order,
            sentiment_score=sentiment_score,
            sentiment_category=sentiment_category,
            risk_score=risk_score,
            ai_sentiment=ai_sentiment,
            ai_risk_score=ai_risk_score,
            ai_frame_type=ai_frame_type,
            hedging_score=hedging_score,
            politeness_score=politeness_score,
            logic_result=logic_result,
        )
        self._session.add(orm)
        await self._session.flush()
        return orm

    async def get_sentence_analysis(self, sent_id: str) -> AnalysisDomain | None:
        """Get analysis for a sentence."""
        stmt = select(AISentenceAnalysis).where(AISentenceAnalysis.sent_id == sent_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm else None

    async def save_validation_log(self, validation: Any) -> None:
        """Save validation log."""
        from bb_paxdata.application.domain.models.validation_result import (
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

    async def get_cache(
        self, cache_hash: str, file_id: str | None = None
    ) -> Any | None:
        """Get cached AI response from Redis (L1) or database (L2)."""
        # Try Redis cache service first if available
        if self._ai_cache_service:
            try:
                cached = await self._ai_cache_service.get(cache_hash, file_id)
                if cached:
                    return cached
            except Exception as e:
                logger.warning(
                    "ai_cache_service_get_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Fallback to database
        import hashlib

        effective_hash = cache_hash
        if file_id:
            effective_hash = hashlib.sha256(
                f"{cache_hash}:{file_id}".encode()
            ).hexdigest()
        stmt = select(AICache).where(AICache.hash == effective_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain() if orm else None

    async def set_cache(
        self,
        cache_hash: str,
        result_json: str,
        model_used: str,
        backend_used: str,
        file_id: str | None = None,
    ) -> None:
        """Set cached AI response in both Redis (L1) and database (L2)."""
        # Write to Redis cache service if available
        if self._ai_cache_service:
            try:
                await self._ai_cache_service.set(
                    cache_hash, result_json, model_used, backend_used, file_id
                )
            except Exception as e:
                logger.warning(
                    "ai_cache_service_set_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Write to database (persistent storage)
        import hashlib

        effective_hash = cache_hash
        if file_id:
            effective_hash = hashlib.sha256(
                f"{cache_hash}:{file_id}".encode()
            ).hexdigest()
        stmt = select(AICache).where(AICache.hash == effective_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.result_json = result_json
            orm.model_used = model_used
            orm.backend_used = backend_used
        else:
            orm = AICache(
                hash=effective_hash,
                result_json=result_json,
                model_used=model_used,
                backend_used=backend_used,
            )
            self._session.add(orm)
        await self._session.flush()

    async def save_rag_explanation(
        self,
        sent_id: str,
        risk_explanation: str,
        sentiment_explanation: str,
        executive_summary: str,
        token_attributions_json: str | None = None,
        grammatical_explanation: str | None = None,
        discrepancy_explanation: str | None = None,
    ) -> AIExplanationsORM:
        """Save RAG query explanation to AIExplanationsORM."""
        # Check if explanation already exists for this sent_id
        stmt = select(AIExplanationsORM).where(AIExplanationsORM.sent_id == sent_id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing explanation
            existing.risk_explanation = risk_explanation
            existing.sentiment_explanation = sentiment_explanation
            existing.executive_summary = executive_summary
            existing.token_attributions_json = token_attributions_json
            existing.grammatical_explanation = grammatical_explanation
            existing.discrepancy_explanation = discrepancy_explanation
            await self._session.flush()
            return existing
        else:
            # Create new explanation
            explanation = AIExplanationsORM(
                sent_id=sent_id,
                risk_explanation=risk_explanation,
                sentiment_explanation=sentiment_explanation,
                executive_summary=executive_summary,
                token_attributions_json=token_attributions_json,
                grammatical_explanation=grammatical_explanation,
                discrepancy_explanation=discrepancy_explanation,
            )
            self._session.add(explanation)
            await self._session.flush()
            return explanation

    async def get_rag_explanation(self, sent_id: str) -> AIExplanationsORM | None:
        """Get RAG query explanation by sent_id."""
        stmt = select(AIExplanationsORM).where(AIExplanationsORM.sent_id == sent_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_fail_cache(self, cache_hash: str) -> AIFailCache | None:
        """Get cached AI failure analysis."""
        stmt = select(AIFailCache).where(AIFailCache.hash == cache_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm

    async def set_fail_cache(
        self, cache_hash: str, result_json: str, model_used: str, backend_used: str
    ) -> None:
        """Set cached AI failure analysis."""
        stmt = select(AIFailCache).where(AIFailCache.hash == cache_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.result_json = result_json
            orm.model_used = model_used
            orm.backend_used = backend_used
            orm.hit_count += 1
        else:
            orm = AIFailCache(
                hash=cache_hash,
                result_json=result_json,
                model_used=model_used,
                backend_used=backend_used,
                hit_count=1,
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
        self, file_id: str | None = None, check_type: str | None = None
    ) -> Sequence[AISentenceAnalysis]:
        """Get analyses that failed logic checks."""
        stmt = select(AISentenceAnalysis).where(
            AISentenceAnalysis.logic_result == "FAIL"
        )
        if file_id:
            stmt = stmt.where(AISentenceAnalysis.file_id == file_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

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
            if fail_analysis.file_id:
                panels.add(fail_analysis.file_id)
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
                affected_panels=fail_analysis.file_id,
                example_sent_id=fail_analysis.sent_id,
                example_sentence=fail_analysis.original_sentence,
                example_explanation=fail_analysis.fail_reason,
                recurrence_count=1,
                first_seen_at=func.now(),
                last_seen_at=func.now(),
            )
            self._session.add(new_pattern)

        await self._session.flush()
