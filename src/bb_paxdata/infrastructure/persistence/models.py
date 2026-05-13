from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TranscriptModel(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    speaker_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(10))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    vader_compound: Mapped[float | None] = mapped_column(Float)
    power_level: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    analytics: Mapped[list[AnalyticModel]] = relationship(back_populates="transcript")


class AnalyticModel(Base):
    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("transcripts.id"), nullable=False
    )
    sbi_score: Mapped[float | None] = mapped_column(Float)
    dki_score: Mapped[float | None] = mapped_column(Float)
    hedging_markers: Mapped[list[str]] = mapped_column(JSON, default=list)
    framing_labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    raw_ai_output: Mapped[str | None] = mapped_column(Text)

    transcript: Mapped[TranscriptModel] = relationship(back_populates="analytics")
