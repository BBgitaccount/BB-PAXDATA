"""Unit of Work: one session, coordinated repositories, explicit transaction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from sqlalchemy.orm import Session

from bb_paxdata.infrastructure.db.repositories.analysis_repo import AnalysisRepository
from bb_paxdata.infrastructure.db.repositories.segment_repo import SegmentRepository
from bb_paxdata.infrastructure.db.repositories.sentence_repo import SentenceRepository


class AbstractUnitOfWork(ABC):
    """Application transaction boundary."""

    sentences: SentenceRepository
    segments: SegmentRepository
    analysis: AnalysisRepository

    @abstractmethod
    def __enter__(self) -> AbstractUnitOfWork:
        """Open a unit of work and bind repositories."""

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Commit on success, rollback on failure, always release the session."""

    @abstractmethod
    def commit(self) -> None:
        """Persist pending changes."""

    @abstractmethod
    def rollback(self) -> None:
        """Discard pending changes."""


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """Coordinates repositories over a single SQLAlchemy ``Session``."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            msg = (
                "UnitOfWork session is not active; "
                "use 'with SqlAlchemyUnitOfWork(...)'"
            )
            raise RuntimeError(msg)
        return self._session

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self.sentences = SentenceRepository(self._session)
        self.segments = SegmentRepository(self._session)
        self.analysis = AnalysisRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        try:
            if self._session is not None:
                if exc_type is not None:
                    self._session.rollback()
                else:
                    self._session.commit()
        finally:
            if self._session is not None:
                self._session.close()
                self._session = None

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
