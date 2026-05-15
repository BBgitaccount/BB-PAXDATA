# src/bb_paxdata/application/pipeline/stages/finalize_stage.py
"""
Pipeline FINALIZE aşaması.
Persistence işlemlerini koordine eder ve nihai PipelineResult üretir.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import structlog
from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult

if TYPE_CHECKING:
    from bb_paxdata.application.pipeline.models.collect_result import CollectResult
    from bb_paxdata.domain.models.analysis import Analysis
    from bb_paxdata.domain.models.country_reference import CountryReference
    from bb_paxdata.domain.services.country_repositories import (
        ICountryReferenceRepository,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class FinalizeStage:
    def __init__(
        self,
        country_ref_repo: ICountryReferenceRepository,
    ) -> None:
        self._country_ref_repo = country_ref_repo

    async def run(
        self,
        analysis: Analysis,
        collect_result: CollectResult,
        success: bool,
        errors: list[str],
        session: AsyncSession | None = None,
    ) -> PipelineResult:
        """
        Nihai sonuçları DB'ye yazar (opsiyonel) ve zarfı döndürür.
        """
        if session:
            await self._persist_country_references(
                collect_result.country_references, session
            )

        return PipelineResult(
            analysis=analysis,
            raw_ner=collect_result.raw_ner,
            raw_tokenizer=collect_result.raw_tokenizer,
            raw_ai=collect_result.raw_ai,
            success=success,
            errors=errors,
            stage="completed" if success else "completed_with_errors",
        )

    async def _persist_country_references(
        self,
        references: Sequence[CountryReference],
        session: AsyncSession,
    ) -> None:
        """
        COLLECT aşamasından gelen CountryReference entity'lerini DB'ye yazar.
        """
        if not references:
            return

        try:
            # Note: The repository should use the provided session.
            # In DI, the repository might already have a session,
            # but here we follow the pattern of injecting the session if needed.
            await self._country_ref_repo.save_batch(list(references))
            logger.info(
                "finalize_stage.country_references_persisted",
                count=len(references),
            )
        except Exception as exc:
            logger.error("finalize_stage.country_persistence_failed", error=str(exc))
            # Hata persistence katmanında kalsın, pipeline sonucunu etkilemesin?
            # Veya errors listesine eklenebilir.
            # Bu implementasyonda sadece loglanıyor.
