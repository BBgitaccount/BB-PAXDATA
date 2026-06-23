"""
Few-Shot Pool Manager Service.

Manages pools of high-quality correction examples for prompt engineering.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.correction_event import CorrectionEvent
from bb_paxdata.application.domain.models.prompt_version import (
    ExampleQuality,
    FewShotExample,
    FewShotPool,
)

logger = structlog.get_logger(__name__)


class FewShotPoolManager:
    """
    Manages few-shot example pools for prompt engineering.

    Features:
    - Field-specific pools (sentiment, frame, discourse_act)
    - Automatic addition of reliable corrections
    - Pool size limits with automatic cleanup
    - Quality-based filtering
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        # In-memory pools (in production, these would be persisted)
        self._pools: dict[str, FewShotPool] = {}

    def get_or_create_pool(self, field: str, max_size: int = 100) -> FewShotPool:
        """Get or create a pool for a specific field."""
        if field not in self._pools:
            self._pools[field] = FewShotPool(
                id=str(uuid.uuid4()),
                field=field,
                max_size=max_size,
            )
        return self._pools[field]

    async def add_correction_to_pool(
        self,
        correction: CorrectionEvent,
        correction_rate: float = 0.0,
    ) -> FewShotExample | None:
        """
        Add a correction to the appropriate pool if it meets quality criteria.

        Criteria for reliable corrections:
        - AI confidence < 0.5 (AI was uncertain)
        - Correction rate > threshold (systematic error)

        Args:
            correction: The correction event
            correction_rate: Historical correction rate for this field

        Returns:
            Created FewShotExample, or None if criteria not met
        """
        # Check if correction is reliable
        if correction.ai_confidence >= 0.5:
            logger.debug(
                "correction_not_reliable_high_confidence",
                confidence=correction.ai_confidence,
            )
            return None

        if correction_rate < 0.3:
            logger.debug(
                "correction_not_reliable_low_rate",
                correction_rate=correction_rate,
            )
            return None

        # Determine quality
        quality = self._assess_quality(correction, correction_rate)

        # Create example
        example = FewShotExample(
            id=str(uuid.uuid4()),
            field=correction.field_corrected,
            original_text="",  # Would be populated from sentence context
            corrected_value=correction.corrected_value,
            original_ai_value=correction.original_value,
            confidence=correction.ai_confidence,
            correction_rate=correction_rate,
            quality=quality,
            source_correction_id=correction.id,
        )

        # Add to pool
        pool = self.get_or_create_pool(correction.field_corrected)
        pool.add_example(example)

        logger.info(
            "example_added_to_pool",
            field=correction.field_corrected,
            example_id=example.id,
            quality=quality,
            pool_size=len(pool.examples),
        )

        return example

    def _assess_quality(
        self, correction: CorrectionEvent, correction_rate: float
    ) -> ExampleQuality:
        """
        Assess the quality of a correction for few-shot learning.

        High quality: Low confidence, high correction rate
        Medium quality: Moderate confidence or correction rate
        Low quality: High confidence or low correction rate
        """
        if correction.ai_confidence < 0.3 and correction_rate > 0.5:
            return ExampleQuality.HIGH
        elif correction.ai_confidence < 0.5 and correction_rate > 0.3:
            return ExampleQuality.MEDIUM
        else:
            return ExampleQuality.LOW

    def get_examples_for_field(
        self, field: str, limit: int = 10
    ) -> Sequence[FewShotExample]:
        """Get reliable examples for a specific field."""
        pool = self._pools.get(field)
        if not pool:
            return []
        return pool.get_examples(limit=limit)

    def cleanup_pools(self, max_age_days: int = 30) -> dict[str, int]:
        """
        Clean up old examples from all pools.

        Returns dict of field -> number of examples removed.
        """
        results = {}
        for field, pool in self._pools.items():
            removed = pool.cleanup_old_examples(max_age_days)
            if removed > 0:
                results[field] = removed
                logger.info(
                    "pool_cleanup_completed",
                    field=field,
                    removed=removed,
                    remaining=len(pool.examples),
                )
        return results

    def get_pool_stats(self) -> dict[str, Any]:
        """Get statistics for all pools."""
        stats = {}
        for field, pool in self._pools.items():
            reliable_count = sum(1 for e in pool.examples if e.is_reliable())
            stats[field] = {
                "total_examples": len(pool.examples),
                "reliable_examples": reliable_count,
                "max_size": pool.max_size,
                "last_updated": pool.updated_at.isoformat(),
            }
        return stats

    async def batch_add_corrections(
        self,
        corrections: Sequence[CorrectionEvent],
        field_correction_rates: dict[str, float],
    ) -> dict[str, int]:
        """
        Batch add multiple corrections to pools.

        Args:
            corrections: List of correction events
            field_correction_rates: Mapping of field -> correction rate

        Returns:
            Dict of field -> number of examples added
        """
        results = {}
        for correction in corrections:
            rate = field_correction_rates.get(correction.field_corrected, 0.0)
            example = await self.add_correction_to_pool(correction, rate)
            if example:
                results[correction.field_corrected] = (
                    results.get(correction.field_corrected, 0) + 1
                )

        logger.info(
            "batch_add_completed",
            total_corrections=len(corrections),
            examples_added=sum(results.values()),
            by_field=results,
        )

        return results
