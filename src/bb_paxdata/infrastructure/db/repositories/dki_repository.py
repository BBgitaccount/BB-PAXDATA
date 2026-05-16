from datetime import datetime

from sqlalchemy import select

from bb_paxdata.domain.models.dki import DKIResult
from bb_paxdata.infrastructure.db.dki_table import DKIResultModel
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository


class DKIRepository(BaseRepository[DKIResultModel]):
    """Repository for DKI result persistence."""

    model_class = DKIResultModel

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
