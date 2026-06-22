from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.analysis import Analysis
    from bb_paxdata.application.domain.models.discourse_flow import DiscourseFlow
    from bb_paxdata.application.domain.models.dki import DKIResult
    from bb_paxdata.application.domain.models.sbi_models import SpeakerPosition


class ISBIRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[SpeakerPosition]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[SpeakerPosition]: ...
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> SpeakerPosition | None: ...


class IDKIRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[DKIResult]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[DKIResult]: ...
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> DKIResult | None: ...


class IAnalysisRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[Analysis]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[Analysis]: ...


class IDiscourseFlowRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[DiscourseFlow]: ...
