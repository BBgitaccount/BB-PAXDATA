from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from bb_paxdata.application.domain.models.dki import DKIResult
from bb_paxdata.application.domain.services.compare_sessions_protocols import (
    IDKIRepository,
)
from bb_paxdata.infrastructure.db.dki_table import DKIResultModel
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository


class DKIRepository(BaseRepository[DKIResultModel], IDKIRepository):
    """Repository for DKI result persistence."""

    model_class = DKIResultModel

    async def get_by_session(self, session_id: str) -> list[DKIResult]:
        """Get all DKI results for a session."""
        stmt = select(self.model_class).where(self.model_class.session_id == session_id)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._row_to_domain(row) for row in rows]

    async def get_by_speaker(self, speaker_id: str) -> list[DKIResult]:
        """Get all DKI results for a speaker across sessions."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.speaker_id == speaker_id)
            .order_by(self.model_class.created_at.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._row_to_domain(row) for row in rows]

    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> DKIResult | None:
        """Get DKI result for a specific session and speaker."""
        stmt = select(self.model_class).where(
            self.model_class.session_id == session_id,
            self.model_class.speaker_id == speaker_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._row_to_domain(row) if row else None

    def _row_to_domain(self, row: DKIResultModel) -> DKIResult:
        """Convert ORM row to domain model."""
        from bb_paxdata.application.domain.models.dki import DKIComponents

        components = DKIComponents(
            velocity=row.velocity,
            semantic_shift=row.semantic_shift,
            debate_loading=row.debate_loading,
            raw_product=row.velocity * row.semantic_shift * row.debate_loading,
        )
        return DKIResult(
            speaker_id=row.speaker_id,
            session_id=row.session_id,
            dki_score=row.dki_score,
            components=components,
            anomaly_flag=row.anomaly_flag,
            calculation_timestamp=row.created_at,
        )

    async def save_dki(self, result: DKIResult, analysis_id: str) -> None:
        """Persist a DKI result to the database."""
        model = DKIResultModel(
            analysis_id=analysis_id,
            speaker_id=result.speaker_id,
            session_id=result.session_id,
            dki_score=result.dki_score,
            velocity=result.components.velocity,
            semantic_shift=result.components.semantic_shift,
            debate_loading=result.components.debate_loading,
            anomaly_flag=result.anomaly_flag,
            calculation_method="azarbonyad_poole_rosenthal_2026",
        )
        await self.add(model)

    async def get_history(
        self, speaker_id: str, before: datetime | None = None
    ) -> list[DKIResultModel]:
        """Retrieve DKI history for a speaker, ordered chronologically."""
        stmt = select(DKIResultModel).where(DKIResultModel.speaker_id == speaker_id)

        if before:
            stmt = stmt.where(DKIResultModel.created_at < before)

        stmt = stmt.order_by(DKIResultModel.created_at.asc())

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
