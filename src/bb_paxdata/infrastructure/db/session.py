"""Database engine, session factory, and lifecycle helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bb_paxdata.infrastructure.db.base import Base

DATABASE_URL = "sqlite:///bb-paxdata.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from bb_paxdata.infrastructure.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
