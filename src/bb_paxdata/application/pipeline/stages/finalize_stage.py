# src/bb_paxdata/application/pipeline/stages/finalize_stage.py
"""
Pipeline FINALIZE aşaması.
Persistence işlemlerini koordine eder ve nihai PipelineResult üretir.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC
from typing import TYPE_CHECKING, Any

import structlog

from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult
from bb_paxdata.application.pipeline.stages.base import BaseFinalizeStage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from bb_paxdata.application.domain.models.analysis import Analysis
    from bb_paxdata.application.domain.models.country_reference import CountryReference
    from bb_paxdata.application.pipeline.models.collect_result import CollectResult
    from bb_paxdata.infrastructure.db.repositories.unit_of_work import (
        AbstractUnitOfWork,
    )

logger = structlog.get_logger(__name__)


class FinalizeStage(BaseFinalizeStage):
    def __init__(
        self,
        unit_of_work: AbstractUnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work

    async def process(self, session: Any, analysis: Analysis) -> Analysis:
        """
        BaseFinalizeStage abstract method implementation.
        Not used by this concrete finalize stage.
        """
        raise NotImplementedError("This stage uses run() instead of process()")

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
            await self._persist_country_references(collect_result.country_references)
            if collect_result.speaker_id:
                if "seen_speakers" not in session.info:
                    session.info["seen_speakers"] = set()
                if collect_result.speaker_id not in session.info["seen_speakers"]:
                    session.info["seen_speakers"].add(collect_result.speaker_id)
                    from datetime import datetime

                    from bb_paxdata.infrastructure.db.repositories.speaker_repository import (
                        SpeakerRepository,
                    )
                    from bb_paxdata.infrastructure.db.repositories.unit_of_work import (
                        SqlAlchemyUnitOfWork,
                    )

                    uow = SqlAlchemyUnitOfWork(lambda: session)
                    uow._session = session
                    uow.speakers = SpeakerRepository(session)
                    try:
                        speaker = await uow.speakers.get_by_id(
                            collect_result.speaker_id
                        )
                        if speaker:
                            speaker.last_seen_at = datetime.now(UTC).replace(
                                tzinfo=None
                            )
                            speaker.appearance_count += 1
                            await session.flush()
                    except Exception as exc:
                        logger.error(
                            "finalize_stage.speaker_stats_update_failed", error=str(exc)
                        )

        return PipelineResult(
            analysis=analysis,
            raw_ner=collect_result.raw_ner,
            raw_tokenizer=collect_result.raw_tokenizer,
            raw_ai=collect_result.raw_ai,
            success=success,
            errors=errors,
            stage="completed" if success else "completed_with_errors",
            extra_data=(
                {"appraisal_vector": collect_result.appraisal_vector}
                if hasattr(collect_result, "appraisal_vector")
                else {}
            ),
        )

    async def _persist_country_references(
        self,
        references: Sequence[CountryReference],
    ) -> None:
        """
        COLLECT aşamasından gelen CountryReference entity'lerini DB'ye yazar.
        """
        if not references:
            return

        try:
            async with self._unit_of_work:
                await self._unit_of_work.country_references.save_batch(list(references))
                await self._unit_of_work.commit()
                logger.info(
                    "finalize_stage.country_references_persisted",
                    count=len(references),
                )
        except Exception as exc:
            logger.error("finalize_stage.country_persistence_failed", error=str(exc))
            # Hata persistence katmanında kalsın, pipeline sonucunu etkilemesin?
            # Veya errors listesine eklenebilir.
            # Bu implementasyonda sadece loglanıyor.
