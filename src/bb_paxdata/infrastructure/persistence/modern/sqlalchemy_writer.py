from __future__ import annotations

from bb_paxdata.domain.entities.legacy import LegacyAnalyticIndex, LegacyTranscript
from bb_paxdata.infrastructure.persistence.models import AnalyticModel, TranscriptModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ModernSQLAlchemyWriter:
    """Yeni DB'ye veri yazar (Upsert destekli)."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    async def upsert_transcripts(
        self, session: AsyncSession, items: list[LegacyTranscript]
    ) -> int:
        if self.dry_run or not items:
            return len(items)

        count = 0
        for item in items:
            # Simple upsert logic
            stmt = select(TranscriptModel).where(TranscriptModel.id == item.id)

            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()

            if obj:
                obj.speaker_name = item.speaker_name
                obj.country_code = item.country_code
                obj.raw_text = item.raw_text
                obj.timestamp = item.timestamp
                obj.vader_compound = item.vader_compound
                obj.power_level = item.power_level
                obj.metadata_json = item.metadata
            else:
                session.add(
                    TranscriptModel(
                        id=item.id,
                        speaker_name=item.speaker_name,
                        country_code=item.country_code,
                        raw_text=item.raw_text,
                        timestamp=item.timestamp,
                        vader_compound=item.vader_compound,
                        power_level=item.power_level,
                        metadata_json=item.metadata,
                    )
                )
            count += 1
        return count

    async def upsert_analytics(
        self, session: AsyncSession, items: list[LegacyAnalyticIndex]
    ) -> int:
        if self.dry_run or not items:
            return len(items)

        count = 0
        for item in items:
            stmt = select(AnalyticModel).where(
                AnalyticModel.transcript_id == item.transcript_id
            )
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()

            if obj:
                obj.sbi_score = item.sbi_score
                obj.dki_score = item.dki_score
                obj.hedging_markers = item.hedging_markers
                obj.framing_labels = item.framing_labels
                obj.raw_ai_output = item.raw_ai_output
            else:
                session.add(
                    AnalyticModel(
                        transcript_id=item.transcript_id,
                        sbi_score=item.sbi_score,
                        dki_score=item.dki_score,
                        hedging_markers=item.hedging_markers,
                        framing_labels=item.framing_labels,
                        raw_ai_output=item.raw_ai_output,
                    )
                )
            count += 1
        return count
