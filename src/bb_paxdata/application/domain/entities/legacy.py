from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class LegacyTranscript:
    """
    Eski sistemdeki transkript satırının domain temsili.
    Frozen dataclass: immutable, hashable, test edilebilir.
    """

    id: int
    speaker_name: str
    country_code: str | None
    raw_text: str
    timestamp: datetime | None
    vader_compound: float | None
    power_level: int | None
    tfidf_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegacyAnalyticIndex:
    """Eski sistemdeki analitik indeksler — readonly domain temsili."""

    transcript_id: int
    sbi_score: float | None  # Speaker-Based Index
    dki_score: float | None  # Discourse-Kinetic Index
    hedging_markers: list[str] = field(default_factory=list)
    framing_labels: dict[str, str] = field(default_factory=dict)
    raw_ai_output: str | None = None  # Ham LLM çıktısı (recovery için)
