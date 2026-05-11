"""Unit of Work: one session, coordinated repositories, explicit transaction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository
from bb_paxdata.infrastructure.db.repositories.segment import SegmentRepository
from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository


class AbstractUnitOfWork(ABC):
    """Application transaction boundary."""

    sentences: SentenceRepository
    segments: SegmentRepository
    analysis: AnalysisRepository

    async def __aenter__(self) -> AbstractUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None:
        """Persist pending changes."""

    @abstractmethod
    async def rollback(self) -> None:
        """Discard pending changes."""


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """Coordinates repositories over a single SQLAlchemy ``AsyncSession``."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            msg = (
                "UnitOfWork session is not active; "
                "use 'async with SqlAlchemyUnitOfWork(...)'"
            )
            raise RuntimeError(msg)
        return self._session

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self.sentences = SentenceRepository(self.session)
        self.segments = SegmentRepository(self.session)
        self.analysis = AnalysisRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        try:
            if self._session is not None:
                if exc_type is not None:
                    await self._session.rollback()
                else:
                    await self._session.commit()
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        if self._session is not None:
            await self.session.rollback()
