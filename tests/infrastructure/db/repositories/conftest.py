"""In-memory SQLite engine shared across repository tests."""

from collections.abc import Callable, Generator

import pytest
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session_factory() -> Generator[Callable[[], Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionTesting = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionTesting()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def seed_panel_speaker_segment(session: Session) -> None:
    session.add(
        m.Panel(
            panel_id="p1",
            file_name="t.txt",
            file_format="txt",
        )
    )
    session.add(
        m.Speaker(
            speaker_id="sp1",
            full_name="Speaker One",
        )
    )
    session.flush()
    from bb_paxdata.domain.models.segment import Segment as SegmentDomain

    seg = SegmentDomain(
        id="seg1",
        panel_id="p1",
        primary_speaker_id="sp1",
        word_count=1,
        sentence_count=1,
    )
    session.add(m.Segment.from_domain(seg))
    session.commit()
