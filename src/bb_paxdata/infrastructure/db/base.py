"""SQLAlchemy declarative base for BB-PAXDATA."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):  # type: ignore[misc]
    """Application-wide ORM base."""
