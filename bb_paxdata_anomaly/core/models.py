from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class AnomalySeverity(Enum):
    """Anomali şiddet seviyeleri."""

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass(frozen=True)
class SegmentRef:
    """Anomaliden etkilenen bir segment referansı."""

    segment_id: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class Sentence:
    """Tek bir cümle ve duygu skoru."""

    text: str
    sentiment_score: float
    start_time: float
    end_time: float
    speaker_id: str | None = None


@dataclass(frozen=True)
class Segment:
    """Cümleler topluluğu ve konuşmacı bilgisi."""

    segment_id: str
    sentences: tuple[Sentence, ...]
    start_time: float
    end_time: float
    speaker_id: str | None = None


@dataclass(frozen=True)
class Transcript:
    """Tam transcript yapısı."""

    segments: tuple[Segment, ...]
    total_duration: float
    silence_gaps: list[tuple[float, float]]


@dataclass(frozen=True)
class Analysis:
    """Analiz nesnesi - Immutable."""

    analysis_id: str
    transcript: Transcript
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnomalyResult:
    """Anomali tespit sonucu."""

    rule_id: str
    rule_name: str
    severity: AnomalySeverity
    confidence_score: float
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)
    affected_segments: list[SegmentRef] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"Confidence score must be in [0, 1], got {self.confidence_score}"
            )
