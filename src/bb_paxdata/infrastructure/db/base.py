"""SQLAlchemy declarative base for BB-PAXDATA."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Application-wide ORM base."""
