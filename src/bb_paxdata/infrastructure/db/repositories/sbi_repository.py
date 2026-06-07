from typing import TYPE_CHECKING

from sqlalchemy import select

from bb_paxdata.application.domain.models.sbi_models import SpeakerPosition
from bb_paxdata.application.domain.services.compare_sessions_protocols import (
    ISBIRepository,
)
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository
from bb_paxdata.infrastructure.db.sbi_table import SpeakerPositionTable

if TYPE_CHECKING:
    pass


class SBIRepository(BaseRepository[SpeakerPositionTable], ISBIRepository):
    """Repository for SBI data access."""

    model_class = SpeakerPositionTable

    async def get_by_session(self, session_id: str) -> list[SpeakerPosition]:
        """Get all speaker positions for a session."""
        stmt = select(self.model_class).where(self.model_class.session_id == session_id)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [row.to_domain() for row in rows]

    async def get_by_speaker(self, speaker_id: str) -> list[SpeakerPosition]:
        """Get all speaker positions for a speaker across sessions."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.speaker_id == speaker_id)
            .order_by(self.model_class.computed_at.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [row.to_domain() for row in rows]

    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> SpeakerPosition | None:
        """Get speaker position for a specific session and speaker."""
        stmt = select(self.model_class).where(
            self.model_class.session_id == session_id,
            self.model_class.speaker_id == speaker_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.to_domain() if row else None
