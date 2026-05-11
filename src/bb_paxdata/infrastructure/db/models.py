"""SQLAlchemy 2.0 ORM models mirroring BB-PAXDATA legacy SQLite schemas."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import Enum as SQLEnum

from bb_paxdata.domain.enums.demand_category import DemandCategory
from bb_paxdata.domain.enums.relationship_type import RelationshipType
from bb_paxdata.domain.enums.risk_level import RiskLevel
from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    from bb_paxdata.domain.enums import (
        EvidenceType,
        LogLevel,
    )
    from bb_paxdata.domain.models.analysis import Analysis
    from bb_paxdata.domain.models.demand import Demand
    from bb_paxdata.domain.models.metadata import Metadata
    from bb_paxdata.domain.models.relationship import Relationship
    from bb_paxdata.domain.models.segment import Segment as SegmentDomain
    from bb_paxdata.domain.models.sentence import Sentence as SentenceDomain
    from bb_paxdata.domain.models.speaker import Speaker as SpeakerDomain
    from bb_paxdata.domain.models.topic import Topic
    from bb_paxdata.domain.models.transcript import Transcript
    from bb_paxdata.domain.models.validation_result import ValidationResult

E = TypeVar("E", bound=Enum)


def _parse_dt(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(value.replace("Z", ""), fmt)
            except ValueError:
                continue
    return None


def _try_enum(enum_cls: type[E], raw: str | None) -> E | None:
    if raw is None or raw == "":
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        key = raw.replace(" ", "_").upper()
        try:
            return enum_cls[key]
        except KeyError:
            return None


def _evidence_list(
    val: dict[str, Any] | list[Any] | str | None,
) -> list[Any] | None:
    if val is None:
        return None
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return list(val.values()) if val else []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return list(parsed.values())
        except json.JSONDecodeError:
            pass
    return None


class Panel(Base):
    __tablename__ = "panels"

    panel_id: Mapped[str] = mapped_column(String, primary_key=True)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    panel_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_str: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_format: Mapped[str] = mapped_column(Text, default="new")
    file_hash: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    n_segments: Mapped[int] = mapped_column(Integer, default=0)
    n_sentences: Mapped[int] = mapped_column(Integer, default=0)
    n_speakers: Mapped[int] = mapped_column(Integer, default=0)
    n_countries: Mapped[int] = mapped_column(Integer, default=0)
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    segments: Mapped[list[Segment]] = relationship(
        back_populates="panel", cascade="all, delete-orphan"
    )

    def to_domain(self) -> Transcript:
        from bb_paxdata.domain.models.transcript import Transcript

        return Transcript(
            id=self.panel_id,
            title=self.title or self.file_name,
            source_file=self.file_name,
            segments=[],
            speakers=[],
            start_time=None,
            end_time=None,
            total_duration=None,
            recording_date=None,
            total_sentences=None,
            total_words=None,
            total_speakers=None,
            backend_type=None,
            processing_version=None,
            overall_confidence=None,
            transcription_quality=None,
            language=None,
            domain=None,
            classification=None,
            metadata={
                "panel_number": self.panel_number,
                "inferred_theme": self.inferred_theme,
                "date_str": self.date_str,
                "file_format": self.file_format,
                "file_hash": self.file_hash,
                "n_segments": self.n_segments,
                "n_sentences": self.n_sentences,
                "n_speakers": self.n_speakers,
                "n_countries": self.n_countries,
                "total_words": self.total_words,
                "total_duration_sec": self.total_duration_sec,
                "imported_at": (
                    self.imported_at.isoformat() if self.imported_at else None
                ),
            },
            log_level=None,
        )

    @classmethod
    def from_domain(cls, model: Transcript) -> Panel:
        meta = model.metadata or {}
        return cls(
            panel_id=model.id,
            file_name=str(meta.get("source_file") or model.title or model.id),
            panel_number=meta.get("panel_number"),
            title=model.title,
            inferred_theme=meta.get("inferred_theme"),
            date_str=meta.get("date_str"),
            file_format=str(meta.get("file_format") or "new"),
            file_hash=meta.get("file_hash"),
            n_segments=int(meta.get("n_segments") or 0),
            n_sentences=int(meta.get("n_sentences") or 0),
            n_speakers=int(meta.get("n_speakers") or 0),
            n_countries=int(meta.get("n_countries") or 0),
            total_words=int(meta.get("total_words") or 0),
            total_duration_sec=int(meta.get("total_duration_sec") or 0),
        )


class Speaker(Base):
    __tablename__ = "speakers"

    speaker_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloc: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    influence_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_panel: Mapped[str | None] = mapped_column(Text, nullable=True)
    n_panels: Mapped[int] = mapped_column(Integer, default=0)
    n_segments: Mapped[int] = mapped_column(Integer, default=0)
    n_sentences: Mapped[int] = mapped_column(Integer, default=0)
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0)
    dominant_emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooperative_pct: Mapped[float] = mapped_column(Float, default=0)
    confrontational_pct: Mapped[float] = mapped_column(Float, default=0)
    risk_event_count: Mapped[int] = mapped_column(Integer, default=0)

    segments: Mapped[list[Segment]] = relationship(back_populates="speaker")
    profile: Mapped[SpeakerProfile | None] = relationship(
        back_populates="speaker", uselist=False
    )

    def to_domain(self) -> SpeakerDomain:
        from bb_paxdata.domain.enums import BlocType, InfluenceTier, SpeakerRole
        from bb_paxdata.domain.models.speaker import Speaker as SpeakerDomainModel

        desc_parts: list[str] = []
        if self.title:
            desc_parts.append(self.title)
        if self.country:
            desc_parts.append(f"country={self.country}")
        description = " · ".join(desc_parts) if desc_parts else None
        return SpeakerDomainModel(
            id=self.speaker_id,
            name=self.full_name,
            role=_try_enum(SpeakerRole, self.role) if self.role else None,
            influence_tier=(
                _try_enum(InfluenceTier, self.influence_tier)
                if self.influence_tier
                else None
            ),
            bloc_type=_try_enum(BlocType, self.bloc) if self.bloc else None,
            total_sentences=self.n_sentences,
            total_words=self.total_words,
            description=description,
            manipulation_tier=None,
            pressure_tier=None,
            audience_type=None,
            relationship_type=None,
            avg_sentence_length=None,
            speaking_percentage=None,
            first_speech_time=None,
            last_speech_time=None,
            total_speaking_time=None,
            confidence_score=None,
        )

    @classmethod
    def from_domain(cls, model: SpeakerDomain) -> Speaker:
        country: str | None = None
        title: str | None = None
        if model.description:
            if "country=" in model.description:
                base, _, rest = model.description.partition(" · country=")
                title = base or None
                country = rest or None
            else:
                title = model.description
        return cls(
            speaker_id=model.id,
            full_name=model.name,
            country=country,
            title=title,
            role=model.role.value if model.role else None,
            bloc=model.bloc_type.value if model.bloc_type else None,
            power_level=0,
            influence_tier=model.influence_tier.value if model.influence_tier else None,
            n_sentences=model.total_sentences or 0,
            total_words=model.total_words or 0,
        )


class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"

    speaker_id: Mapped[str] = mapped_column(
        ForeignKey("speakers.speaker_id"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloc: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    influence_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    n_panels: Mapped[int] = mapped_column(Integer, default=0)
    n_segments: Mapped[int] = mapped_column(Integer, default=0)
    n_sentences: Mapped[int] = mapped_column(Integer, default=0)
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0)
    dominant_emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooperative_pct: Mapped[float] = mapped_column(Float, default=0)
    constructive_pct: Mapped[float] = mapped_column(Float, default=0)
    neutral_pct: Mapped[float] = mapped_column(Float, default=0)
    concerned_pct: Mapped[float] = mapped_column(Float, default=0)
    confrontational_pct: Mapped[float] = mapped_column(Float, default=0)
    risk_event_count: Mapped[int] = mapped_column(Integer, default=0)
    top_countries_mentioned: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    top_topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    ally_countries: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    adversary_countries: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    avg_sentence_length: Mapped[float] = mapped_column(Float, default=0)
    lexical_diversity: Mapped[float] = mapped_column(Float, default=0)
    diplo_vocab_score: Mapped[float] = mapped_column(Float, default=0)
    demand_count: Mapped[int] = mapped_column(Integer, default=0)
    pattern_diversity: Mapped[float] = mapped_column(Float, default=0)
    avg_hedging_score: Mapped[float] = mapped_column(Float, default=0)
    avg_politeness_ratio: Mapped[float] = mapped_column(Float, default=0)
    avg_dki_score: Mapped[float] = mapped_column(Float, default=0)
    dominant_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_audience: Mapped[str | None] = mapped_column(Text, nullable=True)

    speaker: Mapped[Speaker] = relationship(back_populates="profile")

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"speaker_profile:{self.speaker_id}",
            entity_id=self.speaker_id,
            entity_type="speaker_profile",
            title=self.full_name,
            description=f"Speaker profile for {self.full_name}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "country": self.country,
                "top_countries_mentioned": self.top_countries_mentioned,
                "ally_countries": self.ally_countries,
                "adversary_countries": self.adversary_countries,
                "dominant_frame": self.dominant_frame,
                "dominant_audience": self.dominant_audience,
                "avg_dki_score": self.avg_dki_score,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> SpeakerProfile:
        cf = model.custom_fields or {}
        return cls(
            speaker_id=model.entity_id,
            full_name=model.title or model.entity_id,
            country=cf.get("country"),
            top_countries_mentioned=cf.get("top_countries_mentioned"),
            ally_countries=cf.get("ally_countries"),
            adversary_countries=cf.get("adversary_countries"),
            dominant_frame=cf.get("dominant_frame"),
            dominant_audience=cf.get("dominant_audience"),
            avg_dki_score=float(cf.get("avg_dki_score") or 0),
        )


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        Index("idx_seg_panel", "panel_id"),
        Index("idx_seg_country", "country"),
        Index("idx_seg_emotion", "emotion_category"),
        Index("idx_seg_topic", "dominant_topic"),
    )

    seg_id: Mapped[str] = mapped_column(String, primary_key=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("panels.panel_id"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(
        ForeignKey("speakers.speaker_id"), nullable=True
    )
    speaker_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloc: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    seq_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    global_sent_start: Mapped[int] = mapped_column(Integer, default=0)
    ts_start: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts_end: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts_start_sec: Mapped[int] = mapped_column(Integer, default=0)
    ts_end_sec: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    sentence_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_word_len: Mapped[float | None] = mapped_column(Float, nullable=True)
    vader_pos: Mapped[float | None] = mapped_column(Float, nullable=True)
    vader_neg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vader_neu: Mapped[float | None] = mapped_column(Float, nullable=True)
    vader_compound: Mapped[float | None] = mapped_column(Float, nullable=True)
    diplo_compound: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_phrases: Mapped[str | None] = mapped_column(Text, nullable=True)
    tfidf_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_scores: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_gpe: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    entities_org: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    entities_person: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    risk_signals: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    demand_count: Mapped[int] = mapped_column(Integer, default=0)
    rhetoric_patterns: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    risk_trend: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_trajectory: Mapped[str | None] = mapped_column(Text, nullable=True)
    intro_sentiment: Mapped[float] = mapped_column(Float, default=0)
    develop_sentiment: Mapped[float] = mapped_column(Float, default=0)
    concl_sentiment: Mapped[float] = mapped_column(Float, default=0)
    demand_concentration: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    sbi_score: Mapped[float] = mapped_column(Float, default=0)
    dki_score: Mapped[float] = mapped_column(Float, default=0)
    formula_manip_score: Mapped[float] = mapped_column(Float, default=0)
    inconsistency_score: Mapped[float] = mapped_column(Float, default=0)
    avg_hedging_score: Mapped[float] = mapped_column(Float, default=0)
    avg_politeness_ratio: Mapped[float] = mapped_column(Float, default=0)
    dominant_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    panel: Mapped[Panel] = relationship(back_populates="segments")
    speaker: Mapped[Speaker | None] = relationship(back_populates="segments")
    sentences: Mapped[list[Sentence]] = relationship(
        back_populates="segment", cascade="all, delete-orphan"
    )
    ai_insight: Mapped[AISegmentInsight | None] = relationship(
        back_populates="segment", uselist=False
    )

    @property
    def id(self) -> str:
        return self.seg_id

    def to_domain(self) -> SegmentDomain:
        from bb_paxdata.domain.enums import TopicCategory
        from bb_paxdata.domain.models.segment import Segment as SegmentDomainModel

        return SegmentDomainModel(
            id=self.seg_id,
            panel_id=self.panel_id,
            start_time=float(self.ts_start_sec) if self.ts_start_sec else None,
            end_time=float(self.ts_end_sec) if self.ts_end_sec else None,
            duration=float(self.duration_sec) if self.duration_sec else None,
            contextual_importance=None,
            temporal_pattern=None,
            dynamic_event=None,
            sentiment_arc=None,
            avg_sentiment_score=None,
            speaker_count=None,
            confidence_score=0.85,
            topic_category=(
                _try_enum(TopicCategory, self.dominant_topic)
                if self.dominant_topic
                else None
            ),
            primary_speaker_id=self.speaker_id,
            word_count=self.word_count,
            sentence_count=self.sentence_count,
            summary=self.text[:500] if self.text else None,
        )

    @classmethod
    def from_domain(
        cls, model: SegmentDomain, *, panel_id: str | None = None
    ) -> Segment:
        resolved_panel = panel_id or model.panel_id
        if not resolved_panel:
            raise ValueError("panel_id is required (argument or Segment.panel_id)")
        return cls(
            seg_id=model.id,
            panel_id=resolved_panel,
            speaker_id=model.primary_speaker_id,
            speaker_name="",
            ts_start_sec=int(model.start_time or 0),
            ts_end_sec=int(model.end_time or 0),
            duration_sec=int(model.duration or 0),
            text=model.summary or "",
            word_count=model.word_count or 0,
            sentence_count=model.sentence_count or 0,
            dominant_topic=model.topic_category.value if model.topic_category else None,
        )


class Sentence(Base):
    __tablename__ = "sentences"
    __table_args__ = (
        Index("idx_sent_seg", "seg_id"),
        Index("idx_sent_panel", "panel_id"),
        Index("idx_sent_country", "country"),
        Index("idx_sent_speaker", "speaker_id"),
        Index("idx_sent_emotion", "emotion_category"),
        Index("idx_sent_topic", "dominant_topic"),
        Index("idx_sent_demand", "demand_type"),
        Index("idx_sent_rhetoric", "rhetoric_type"),
        Index("idx_sent_frame", "dominant_frame"),
        Index("idx_sent_audience", "audience_type"),
    )

    sent_id: Mapped[str] = mapped_column(String, primary_key=True)
    seg_id: Mapped[str] = mapped_column(ForeignKey("segments.seg_id"), nullable=False)
    panel_id: Mapped[str] = mapped_column(ForeignKey("panels.panel_id"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloc: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    sent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    global_sent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Temporal fields for domain model compatibility
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    vader_compound: Mapped[float] = mapped_column(Float, default=0)
    diplo_compound: Mapped[float] = mapped_column(Float, default=0)
    emotion_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_scores: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    risk_signals: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    entities_gpe: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    entities_person: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    demand_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_weight: Mapped[float] = mapped_column(Float, default=0)
    demand_category: Mapped[DemandCategory | None] = mapped_column(
        SQLEnum(DemandCategory), default=None, nullable=True
    )
    rhetoric_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    influence_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    negation_aware_diplo: Mapped[float] = mapped_column(Float, default=0)
    topic_specificity: Mapped[float] = mapped_column(Float, default=0)
    hedging_score: Mapped[float] = mapped_column(Float, default=0)
    politeness_ratio: Mapped[float] = mapped_column(Float, default=0)
    face_threat_count: Mapped[int] = mapped_column(Integer, default=0)
    face_save_count: Mapped[int] = mapped_column(Integer, default=0)
    dominant_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_types: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    appraisal_attitude: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_analyzed: Mapped[int] = mapped_column(
        Integer, default=0
    )  # 0 = not analyzed, 1 = analyzed
    logic_result: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 'PASS' | 'FAIL' | None

    segment: Mapped[Segment] = relationship(back_populates="sentences")
    ai_demand_analyses: Mapped[list[AIDemandAnalysis]] = relationship(
        back_populates="sentence"
    )
    ai_analysis: Mapped[AISentenceAnalysis | None] = relationship(
        back_populates="sentence", uselist=False
    )

    @property
    def id(self) -> str:
        return self.sent_id

    @property
    def segment_id(self) -> str:
        return self.seg_id

    def to_domain(self) -> SentenceDomain:
        from bb_paxdata.domain.enums import (
            AppraisalAttitude,
            AudienceType,
            EvidenceType,
            FrameType,
            SentimentCategory,
            TopicCategory,
        )
        from bb_paxdata.domain.models.sentence import Sentence as SentenceDomainModel

        ev_raw = _evidence_list(self.evidence_types)
        evidence_enums: list[EvidenceType] | None = None
        if ev_raw:
            evidence_enums = []
            for x in ev_raw:
                e = _try_enum(EvidenceType, str(x))
                if e:
                    evidence_enums.append(e)

        ts_dict: dict[str, float] | None = None
        if isinstance(self.topic_scores, dict):
            ts_dict = {str(k): float(v) for k, v in self.topic_scores.items()}
        elif isinstance(self.topic_scores, str):
            try:
                loaded = json.loads(self.topic_scores)
                if isinstance(loaded, dict):
                    ts_dict = {str(k): float(v) for k, v in loaded.items()}
            except json.JSONDecodeError:
                ts_dict = None

        return SentenceDomainModel(
            id=self.sent_id,
            text=self.text,
            speaker_id=self.speaker_id,
            segment_id=self.seg_id,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=self.duration,
            sentiment=_try_enum(SentimentCategory, self.emotion_category),
            sentiment_score=self.vader_compound,
            negation_aware_diplo=self.negation_aware_diplo,
            tension_level=None,
            negation_type=None,
            hedging_type=None,
            hedging_score=self.hedging_score,
            politeness_act=None,
            politeness_ratio=self.politeness_ratio,
            diplomatic_tone=None,
            appraisal_attitude=_try_enum(AppraisalAttitude, self.appraisal_attitude),
            dominant_topic=(
                _try_enum(TopicCategory, self.dominant_topic)
                if self.dominant_topic
                else None
            ),
            topic_specificity=self.topic_specificity,
            topic_scores=ts_dict,
            dominant_frame=(
                _try_enum(FrameType, self.dominant_frame)
                if self.dominant_frame
                else None
            ),
            evidence_types=evidence_enums,
            audience_type=(
                _try_enum(AudienceType, self.audience_type)
                if self.audience_type
                else None
            ),
            word_count=self.word_count,
            face_threat_count=self.face_threat_count,
            face_save_count=self.face_save_count,
            confidence_score=None,
        )

    @classmethod
    def from_domain(
        cls, model: SentenceDomain, *, seg_id: str, panel_id: str
    ) -> Sentence:
        ev = None
        if model.evidence_types:
            ev = [et.value for et in model.evidence_types]
        return cls(
            sent_id=model.id,
            seg_id=seg_id,
            panel_id=panel_id,
            speaker_id=model.speaker_id,
            speaker_name="",
            text=model.text,
            # Temporal fields
            start_time=model.start_time,
            end_time=model.end_time,
            duration=model.duration,
            word_count=model.word_count or 0,
            vader_compound=model.sentiment_score or 0,
            negation_aware_diplo=model.negation_aware_diplo or 0,
            topic_specificity=model.topic_specificity or 0,
            hedging_score=model.hedging_score or 0,
            politeness_ratio=model.politeness_ratio or 0,
            face_threat_count=model.face_threat_count or 0,
            face_save_count=model.face_save_count or 0,
            dominant_topic=model.dominant_topic.value if model.dominant_topic else None,
            topic_scores=model.topic_scores,
            dominant_frame=model.dominant_frame.value if model.dominant_frame else None,
            evidence_types=ev,
            appraisal_attitude=(
                model.appraisal_attitude.value if model.appraisal_attitude else None
            ),
            audience_type=model.audience_type.value if model.audience_type else None,
        )


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (
        Index("idx_word_seg", "seg_id"),
        Index("idx_word_country", "country"),
        Index("idx_word_norm", "word_norm"),
        Index("idx_word_stopword", "is_stopword"),
    )

    word_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=False
    )
    seg_id: Mapped[str] = mapped_column(ForeignKey("segments.seg_id"), nullable=False)
    panel_id: Mapped[str] = mapped_column(ForeignKey("panels.panel_id"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloc: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    word_raw: Mapped[str] = mapped_column(Text, nullable=False)
    word_norm: Mapped[str] = mapped_column(Text, nullable=False)
    word_position: Mapped[int] = mapped_column(Integer, default=0)
    is_stopword: Mapped[bool] = mapped_column(Boolean, default=False)
    diplo_score: Mapped[float] = mapped_column(Float, default=0)
    is_named_entity: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"word:{self.word_id}",
            entity_id=str(self.word_id),
            entity_type="word",
            title=f"Word {self.word_id}",
            description=f"Word: {self.word_norm}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "sent_id": self.sent_id,
                "seg_id": self.seg_id,
                "panel_id": self.panel_id,
                "word_raw": self.word_raw,
                "word_norm": self.word_norm,
                "is_stopword": self.is_stopword,
                "diplo_score": self.diplo_score,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> Word:
        cf = model.custom_fields or {}
        return cls(
            sent_id=str(cf["sent_id"]),
            seg_id=str(cf["seg_id"]),
            panel_id=str(cf["panel_id"]),
            word_raw=str(cf.get("word_raw") or ""),
            word_norm=str(cf.get("word_norm") or ""),
            is_stopword=bool(cf.get("is_stopword")),
            diplo_score=float(cf.get("diplo_score") or 0),
            is_named_entity=bool(cf.get("is_named_entity") or False),
        )


class CountryReference(Base):
    __tablename__ = "country_references"
    __table_args__ = (
        Index("idx_coref_from", "from_country"),
        Index("idx_coref_to", "to_country"),
    )

    ref_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_id: Mapped[str | None] = mapped_column(
        ForeignKey("panels.panel_id"), nullable=True
    )
    seg_id: Mapped[str | None] = mapped_column(
        ForeignKey("segments.seg_id"), nullable=True
    )
    from_country: Mapped[str] = mapped_column(Text, nullable=False)
    to_country: Mapped[str] = mapped_column(Text, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    sentiment_context: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"country_ref:{self.ref_id}",
            entity_id=str(self.ref_id),
            entity_type="country_reference",
            title=f"Country Reference {self.ref_id}",
            description=f"{self.from_country} -> {self.to_country}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "panel_id": self.panel_id,
                "seg_id": self.seg_id,
                "from_country": self.from_country,
                "to_country": self.to_country,
                "mention_count": self.mention_count,
                "sentiment_context": self.sentiment_context,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> CountryReference:
        cf = model.custom_fields or {}
        return cls(
            panel_id=cf.get("panel_id"),
            seg_id=cf.get("seg_id"),
            from_country=str(cf.get("from_country") or ""),
            to_country=str(cf.get("to_country") or ""),
            mention_count=int(cf.get("mention_count") or 1),
            sentiment_context=cf.get("sentiment_context"),
        )


class CountryStat(Base):
    __tablename__ = "country_stats"

    country: Mapped[str] = mapped_column(Text, primary_key=True)
    panel_id: Mapped[str] = mapped_column(
        ForeignKey("panels.panel_id"), primary_key=True
    )
    n_segments: Mapped[int] = mapped_column(Integer, default=0)
    n_sentences: Mapped[int] = mapped_column(Integer, default=0)
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    words_per_minute: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    dominant_emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_scores: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"country_stat:{self.country}:{self.panel_id}",
            entity_id=self.panel_id,
            entity_type="country_stats",
            title=self.country,
            description=f"Statistics for {self.country}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "n_segments": self.n_segments,
                "topic_scores": self.topic_scores,
                "words_per_minute": self.words_per_minute,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> CountryStat:
        cf = model.custom_fields or {}
        return cls(
            country=model.title or str(cf.get("country") or ""),
            panel_id=model.entity_id,
            n_segments=int(cf.get("n_segments") or 0),
            topic_scores=cf.get("topic_scores"),
            words_per_minute=cf.get("words_per_minute"),
        )


class TopicMatrix(Base):
    __tablename__ = "topic_matrix"

    panel_id: Mapped[str] = mapped_column(
        ForeignKey("panels.panel_id"), primary_key=True
    )
    country: Mapped[str] = mapped_column(Text, primary_key=True)
    topic: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)

    def to_domain(self) -> Topic:
        from bb_paxdata.domain.enums import TopicCategory
        from bb_paxdata.domain.models.topic import Topic as TopicModel

        cat = _try_enum(TopicCategory, self.topic) or TopicCategory.NONE
        return TopicModel(
            id=f"{self.panel_id}:{self.country}:{self.topic}",
            topic_category=cat,
            topic_name=self.topic,
            topic_description=None,
            context=None,
            first_mention_time=None,
            last_mention_time=None,
            duration=None,
            controversy_score=None,
            complexity_score=None,
            sentiment_score=None,
            parent_topic_id=None,
            segment_id=None,
            speaker_id=None,
            subcategory=None,
            contextual_importance=None,
            key_terms=[],
            participating_speakers=[],
            speaker_engagement={},
            audience_reception=None,
            evolution_pattern=None,
            resolution_status=None,
            outcome=None,
            impact_score=None,
            action_items=[],
            is_active=True,
            is_resolved=False,
            is_contentious=False,
            analysis_notes=None,
            tags=[],
            confidence_score=0.85,
            evidence_types=[],
            related_topic_ids=[],
            conflicting_topic_ids=[],
            prominence_score=None,
        )

    @classmethod
    def from_domain(cls, model: Topic, *, panel_id: str, country: str) -> TopicMatrix:
        return cls(
            panel_id=panel_id,
            country=country,
            topic=model.topic_name,
            score=float(model.prominence_score or 0),
        )


class CountryPairSentiment(Base):
    __tablename__ = "country_pair_sentiment"
    __table_args__ = (Index("idx_pair_from", "from_country"),)

    from_country: Mapped[str] = mapped_column(Text, primary_key=True)
    to_country: Mapped[str] = mapped_column(Text, primary_key=True)
    total_mentions: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    relationship_type: Mapped[RelationshipType | None] = mapped_column(
        SQLEnum(RelationshipType), default=None, nullable=True
    )
    affinity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_weighted_score: Mapped[float] = mapped_column(Float, default=0)
    diplomatic_distance: Mapped[float] = mapped_column(Float, default=0)

    def to_domain(self) -> Relationship:
        from bb_paxdata.domain.enums import RelationshipType
        from bb_paxdata.domain.models.relationship import (
            Relationship as RelationshipModel,
        )

        rt = (
            _try_enum(RelationshipType, self.relationship_type)
            if self.relationship_type
            else RelationshipType.NEUTRAL
        )
        return RelationshipModel(
            id=f"{self.from_country}:{self.to_country}",
            speaker_a_id=self.from_country,
            speaker_b_id=self.to_country,
            relationship_type=rt or RelationshipType.NEUTRAL,
            relationship_status=None,
            relationship_nature=None,
            power_balance=None,
            influence_a_to_b=None,
            influence_b_to_a=None,
            pressure_a_on_b=None,
            pressure_b_on_a=None,
            interaction_frequency=None,
            communication_style=None,
            conflict_level=None,
            cooperation_level=None,
            relationship_start=None,
            relationship_duration=None,
            last_interaction=None,
            emotional_tone=None,
            trust_level=None,
            respect_level=None,
            relationship_context=None,
            relationship_evolution=None,
            trajectory=None,
            impact_on_conversation=None,
            analysis_notes=None,
            confidence_score=0.85,
            evidence_types=[],
            related_relationship_ids=[],
            group_affiliations=[],
            is_active=True,
            is_formal=False,
            is_hierarchical=False,
            change_indicators=[],
            consequences=[],
            tags=[],
        )

    @classmethod
    def from_domain(
        cls, model: Relationship, *, from_country: str, to_country: str
    ) -> CountryPairSentiment:
        return cls(
            from_country=from_country,
            to_country=to_country,
            relationship_type=model.relationship_type.value,
            affinity_score=model.confidence_score,
        )


class DemandRecord(Base):
    __tablename__ = "demand_records"
    __table_args__ = (
        Index("idx_demand_country", "country"),
        Index("idx_demand_type", "demand_type"),
    )

    demand_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    sent_id: Mapped[str | None] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=True
    )
    seg_id: Mapped[str | None] = mapped_column(
        ForeignKey("segments.seg_id"), nullable=True
    )
    panel_id: Mapped[str | None] = mapped_column(
        ForeignKey("panels.panel_id"), nullable=True
    )
    speaker_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    demand_verb: Mapped[str] = mapped_column(Text, nullable=False)
    demand_type: Mapped[str] = mapped_column(Text, nullable=False)
    demand_weight: Mapped[float] = mapped_column(Float, default=0)
    demand_category: Mapped[DemandCategory | None] = mapped_column(
        SQLEnum(DemandCategory), default=None, nullable=True
    )
    target_entity: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    diplo_compound: Mapped[float] = mapped_column(Float, default=0)

    def to_domain(self) -> Demand:
        from bb_paxdata.domain.enums import DemandCategory, DemandType
        from bb_paxdata.domain.models.demand import Demand as DemandModel

        dt = _try_enum(DemandType, self.demand_type) or DemandType.INTENTION
        dc = (
            _try_enum(DemandCategory, self.demand_category)
            if self.demand_category
            else DemandCategory.DIPLOMATIC_ENGAGEMENT
        )
        return DemandModel(
            id=str(self.demand_id),
            segment_id=self.seg_id,
            sentence_id=self.sent_id,
            speaker_id=self.speaker_name,
            target_speaker_id=None,
            demand_type=dt,
            demand_category=dc or DemandCategory.DIPLOMATIC_ENGAGEMENT,
            pressure_level=None,
            demand_text=self.full_sentence,
            paraphrased_demand=None,
            context=None,
            timestamp=None,
            urgency=None,
            deadline=None,
            compliance_likelihood=None,
            assertiveness_score=None,
            politeness_score=None,
            evidence_types=[],
            confidence_score=min(1.0, max(0.0, self.demand_weight or 0.5)),
            response_text=None,
            response_timestamp=None,
            compliance_status=None,
            impact_score=None,
            risk_implication=None,
            fulfillment_timestamp=None,
            notes=None,
        )

    @classmethod
    def from_domain(cls, model: Demand, *, panel_id: str | None = None) -> DemandRecord:
        return cls(
            sent_id=model.sentence_id,
            seg_id=model.segment_id,
            panel_id=panel_id,
            speaker_name=model.speaker_id,
            country="",
            demand_verb="",
            demand_type=model.demand_type.value,
            demand_weight=model.confidence_score,
            demand_category=model.demand_category.value,
            full_sentence=model.demand_text,
        )


class PatternRecord(Base):
    __tablename__ = "pattern_records"
    __table_args__ = (
        Index("idx_pattern_type", "pattern_type"),
        Index("idx_pattern_country", "country"),
    )

    pattern_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    sent_id: Mapped[str | None] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=True
    )
    seg_id: Mapped[str | None] = mapped_column(
        ForeignKey("segments.seg_id"), nullable=True
    )
    panel_id: Mapped[str | None] = mapped_column(
        ForeignKey("panels.panel_id"), nullable=True
    )
    speaker_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    pattern_type: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    diplo_compound: Mapped[float] = mapped_column(Float, default=0)

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"pattern:{self.pattern_id}",
            entity_id=str(self.pattern_id),
            entity_type="pattern_record",
            title=f"Pattern {self.pattern_id}",
            description=f"Pattern: {self.pattern_type}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "pattern_type": self.pattern_type,
                "full_sentence": self.full_sentence,
                "diplo_compound": self.diplo_compound,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> PatternRecord:
        cf = model.custom_fields or {}
        return cls(
            speaker_name="",
            country="",
            pattern_type=str(cf.get("pattern_type") or ""),
            full_sentence=str(cf.get("full_sentence") or ""),
            diplo_compound=float(cf.get("diplo_compound") or 0),
        )


class PanelDynamics(Base):
    __tablename__ = "panel_dynamics"
    __table_args__ = (
        Index("idx_dyn_panel", "panel_id"),
        Index("idx_dyn_sent", "sent_id", unique=True),
    )

    dyn_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_id: Mapped[str | None] = mapped_column(
        ForeignKey("panels.panel_id"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    kgi_score: Mapped[float] = mapped_column(Float, default=0)
    risk_delta: Mapped[float] = mapped_column(Float, default=0)
    emotion_shift: Mapped[float] = mapped_column(Float, default=0)
    topic_shift: Mapped[int] = mapped_column(Integer, default=0)
    inconsistency_score: Mapped[float] = mapped_column(Float, default=0)
    sent_id: Mapped[str] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=False
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"panel_dyn:{self.dyn_id}",
            entity_id=str(self.dyn_id),
            entity_type="panel_dynamics",
            title=f"Panel Dynamics {self.dyn_id}",
            description="Panel dynamics analysis",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "panel_id": self.panel_id,
                "kgi_score": self.kgi_score,
                "risk_delta": self.risk_delta,
                "sent_id": self.sent_id,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> PanelDynamics:
        cf = model.custom_fields or {}
        return cls(
            panel_id=cf.get("panel_id"),
            position=int(cf.get("position") or 0),
            kgi_score=float(cf.get("kgi_score") or 0),
            risk_delta=float(cf.get("risk_delta") or 0),
            emotion_shift=float(cf.get("emotion_shift") or 0),
            topic_shift=int(cf.get("topic_shift") or 0),
            inconsistency_score=float(cf.get("inconsistency_score") or 0),
            sent_id=str(cf["sent_id"]),
        )


class DiscourseNetworkEdge(Base):
    __tablename__ = "discourse_network_edges"
    __table_args__ = (Index("idx_net_from", "from_country"),)

    edge_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_id: Mapped[str | None] = mapped_column(
        ForeignKey("panels.panel_id"), nullable=True
    )
    from_country: Mapped[str] = mapped_column(Text, nullable=False)
    to_country: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0)
    edge_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_source: Mapped[int] = mapped_column(Integer, default=0)

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"discourse_edge:{self.edge_id}",
            entity_id=str(self.edge_id),
            entity_type="discourse_network_edge",
            title=f"Discourse Edge {self.edge_id}",
            description=f"{self.from_country} -> {self.to_country}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "from_country": self.from_country,
                "to_country": self.to_country,
                "weight": self.weight,
                "edge_type": self.edge_type,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> DiscourseNetworkEdge:
        cf = model.custom_fields or {}
        return cls(
            from_country=str(cf["from_country"]),
            to_country=str(cf["to_country"]),
            weight=float(cf.get("weight") or 1),
            edge_type=cf.get("edge_type"),
        )


class AISentenceAnalysis(Base):
    __tablename__ = "ai_sentence_analysis"
    __table_args__ = (
        Index("idx_ai_sent_id", "sent_id"),
        Index("idx_ai_panel", "panel_id"),
        Index("idx_ai_country", "country"),
        Index("idx_ai_logic", "overall_logic_check"),
        Index("idx_ai_risk", "risk_level"),
        Index("idx_ai_tone", "diplomatic_tone"),
    )

    ai_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Part of composite PK
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    global_sent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prev_sent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_sent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    triplet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        SQLEnum(RiskLevel), default=None, nullable=True
    )
    risk_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_demand: Mapped[bool] = mapped_column(Boolean, default=False)
    demand_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    secondary_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    diplomatic_tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    manipulation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_inconsistency: Mapped[bool] = mapped_column(Boolean, default=False)
    contextual_importance: Mapped[str | None] = mapped_column(Text, nullable=True)
    rhetorical_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtext: Mapped[str | None] = mapped_column(Text, nullable=True)
    commentary: Mapped[str | None] = mapped_column(Text, nullable=True)
    hedging_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    politeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    framing: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    appraisal_attitude: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_demand: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_hedging: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_appraisal: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_manipulation: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_check_politeness: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_logic_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_fail_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_pass_count: Mapped[int] = mapped_column(Integer, default=0)
    logic_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    backend: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # "local" | "api" | "gemini" | "groq"
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_demand_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_hedging_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_frame_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_manipulation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_politeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_evidence_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_result: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 'PASS' | 'FAIL' | None
    validation_flags: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_types: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    anomaly_severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    # Legacy fields for backward compatibility
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    sentence: Mapped[Sentence | None] = relationship(back_populates="ai_analysis")

    def to_domain(self) -> Analysis:
        from bb_paxdata.domain.enums import RiskLevel
        from bb_paxdata.domain.models.analysis import Analysis as AnalysisModel

        rl = (
            _try_enum(RiskLevel, self.risk_level)
            if self.risk_level
            else RiskLevel.MEDIUM
        )
        return AnalysisModel(
            id=str(self.ai_id),
            sentence_id=self.sent_id,
            segment_id=self.seg_id,
            speaker_id=None,
            risk_level=rl or RiskLevel.MEDIUM,
            risk_trajectory=None,
            future_risk_tier=None,
            emotional_intensity=None,
            stress_level=None,
            anomaly_confidence=None,
            sentiment_score=float(self.sentiment_score or 0),
            confidence_score=0.85,
            validation_score=None,
            fail_category=None,
            evidence_types=[],
            evidence_strength=None,
            complexity_score=None,
            coherence_score=None,
            manipulation_score=self.manipulation_score,
            analysis_version="1.0",
            analysis_timestamp=datetime.utcnow(),
            analyzer_id=None,
            sumcomplexity_score=None,
            detailed_findings=None,
            recommendations=[],
        )

    @classmethod
    def from_domain(cls, model: Analysis, *, sent_id: str) -> AISentenceAnalysis:
        return cls(
            sent_id=sent_id,
            prompt_version="v1",
            seg_id=model.segment_id,
            risk_level=model.risk_level.value,
            sentiment_score=model.sentiment_score,
            manipulation_score=model.manipulation_score,
        )


class AIValidationLog(Base):
    __tablename__ = "ai_validation_log"
    __table_args__ = (
        Index("idx_val_sent", "sent_id"),
        Index("idx_val_result", "result"),
        Index("idx_val_type", "check_type"),
    )

    val_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    formula_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    discrepancy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    def to_domain(self) -> ValidationResult:
        from bb_paxdata.domain.models.validation_result import (
            ValidationResult as VR,
        )

        passed = self.result.upper() == "PASS"
        return VR(
            id=str(self.val_id),
            entity_id=self.sent_id,
            entity_type="sentence",
            overall_status="passed" if passed else "failed",
            total_checks=1,
            passed_checks=1 if passed else 0,
            failed_checks=0 if passed else 1,
            overall_score=None,
            confidence_score=None,
            severity_score=None,
            evidence_types=[],
            evidence_summary=None,
            validation_duration=None,
            validation_version=None,
            validator_id=None,
            log_level=LogLevel.INFO,
            resolution_method=None,
            resolution_timestamp=None,
            previous_validation_id=None,
            summary=None,
            detailed_report=None,
        )

    @classmethod
    def from_domain(cls, model: ValidationResult, *, sent_id: str) -> AIValidationLog:
        return cls(
            sent_id=sent_id,
            check_type="aggregate",
            result="PASS" if model.failed_checks == 0 else "FAIL",
        )


class AISegmentInsight(Base):
    __tablename__ = "ai_segment_insights"
    __table_args__ = (Index("idx_seg_insight", "seg_id"),)

    insight_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    seg_id: Mapped[str] = mapped_column(
        ForeignKey("segments.seg_id"), unique=True, nullable=False
    )
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    segment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    hidden_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_dynamics: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhetoric_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    diplomatic_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sbi_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    dki_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_inconsistency_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    overall_logic_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    logic_health_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_insight: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Main insight content
    ai_insight_version: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Version of insight generation
    insight_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    segment: Mapped[Segment] = relationship(back_populates="ai_insight")

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_seg_insight:{self.insight_id}",
            entity_id=self.seg_id,
            entity_type="ai_segment_insight",
            title=f"AI Segment Insight {self.insight_id}",
            description="AI analysis of segment",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"segment_summary": self.segment_summary},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AISegmentInsight:
        cf = model.custom_fields or {}
        return cls(
            seg_id=model.entity_id,
            segment_summary=cf.get("segment_summary"),
        )


class AICache(Base):
    __tablename__ = "ai_cache"
    __table_args__ = (Index("idx_cache_hash", "hash"),)

    hash: Mapped[str] = mapped_column(String, primary_key=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_cache:{self.hash}",
            entity_id=self.hash,
            entity_type="ai_cache",
            title=f"AI Cache {self.hash}",
            description="Cached AI response",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"hit_count": self.hit_count},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AICache:
        cf = model.custom_fields or {}
        return cls(
            hash=model.entity_id,
            result_json=str(cf.get("result_json") or ""),
            hit_count=int(cf.get("hit_count") or 0),
        )


class AIContextualFlag(Base):
    __tablename__ = "ai_contextual_flags"
    __table_args__ = (
        Index("idx_flags_sent", "sent_id"),
        Index("idx_flags_sev", "severity"),
        Index("idx_flags_type", "anomaly_type"),
        Index("idx_flags_country", "country"),
        Index("idx_flags_cat", "flag_category"),
    )

    flag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    flag_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_flag:{self.flag_id}",
            entity_id=self.sent_id,
            entity_type="ai_contextual_flag",
            title=f"AI Flag {self.flag_id}",
            description=f"AI contextual flag: {self.anomaly_type}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "anomaly_type": self.anomaly_type,
                "severity": self.severity,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIContextualFlag:
        cf = model.custom_fields or {}
        return cls(
            sent_id=model.entity_id,
            anomaly_type=str(cf.get("anomaly_type") or ""),
            severity=str(cf.get("severity") or ""),
        )


class AIDemandAnalysis(Base):
    __tablename__ = "ai_demand_analysis"
    __table_args__ = (
        Index("idx_ai_demand_demand", "demand_id"),
        Index("idx_ai_demand_sent", "sent_id"),
        Index("idx_ai_demand_country", "country"),
    )

    ai_demand_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    demand_id: Mapped[int | None] = mapped_column(
        ForeignKey("demand_records.demand_id"), nullable=True
    )
    sent_id: Mapped[str | None] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=True
    )
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    demand_verb: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_category: Mapped[DemandCategory | None] = mapped_column(
        SQLEnum(DemandCategory), default=None, nullable=True
    )
    future_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    demand_subtext: Mapped[str | None] = mapped_column(Text, nullable=True)
    hidden_agenda: Mapped[str | None] = mapped_column(Text, nullable=True)
    potential_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    diplomatic_leverage: Mapped[str | None] = mapped_column(Text, nullable=True)
    future_demands: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategic_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    sentence: Mapped[Sentence | None] = relationship(
        back_populates="ai_demand_analyses"
    )
    demand_record: Mapped[DemandRecord | None] = relationship()

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_demand:{self.ai_demand_id}",
            entity_id=str(self.ai_demand_id),
            entity_type="ai_demand_analysis",
            title=f"AI Demand Analysis {self.ai_demand_id}",
            description="AI analysis of demand",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"strategic_value": self.strategic_value},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIDemandAnalysis:
        cf = model.custom_fields or {}
        return cls(strategic_value=cf.get("strategic_value"))


class AIPanelSynthesis(Base):
    __tablename__ = "ai_panel_synthesis"

    synthesis_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    panel_id: Mapped[str] = mapped_column(
        ForeignKey("panels.panel_id"), unique=True, nullable=False
    )
    panel_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_balance: Mapped[str | None] = mapped_column(Text, nullable=True)
    critical_moments: Mapped[str | None] = mapped_column(Text, nullable=True)
    outlook: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_map: Mapped[str | None] = mapped_column(Text, nullable=True)
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_panel_synth:{self.synthesis_id}",
            entity_id=self.panel_id,
            entity_type="ai_panel_synthesis",
            title=f"AI Panel Synthesis {self.synthesis_id}",
            description="AI synthesis of panel",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={
                "panel_summary": self.panel_summary,
                "power_balance": self.power_balance,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIPanelSynthesis:
        cf = model.custom_fields or {}
        return cls(
            panel_id=model.entity_id,
            panel_summary=cf.get("panel_summary"),
            power_balance=cf.get("power_balance"),
        )


class AIFailAnalysis(Base):
    __tablename__ = "ai_fail_analysis"
    __table_args__ = (
        Index("idx_fail_sent", "sent_id"),
        Index("idx_fail_check", "check_type"),
        Index("idx_fail_kategori", "fail_category"),
        Index("idx_fail_country", "country"),
        Index("idx_fail_panel", "panel_id"),
    )

    fail_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    global_sent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    formula_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    discrepancy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    triplet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_sent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_sent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    kgi_score: Mapped[float] = mapped_column(Float, default=0)
    risk_delta: Mapped[float] = mapped_column(Float, default=0)
    emotion_shift: Mapped[float] = mapped_column(Float, default=0)
    topic_shift: Mapped[float] = mapped_column(Float, default=0)
    formula_inconsistency_score: Mapped[float] = mapped_column(Float, default=0)
    ai_manipulation_score: Mapped[float] = mapped_column(Float, default=0)
    ai_hedging_score: Mapped[float] = mapped_column(Float, default=0)
    ai_risk_score: Mapped[float] = mapped_column(Float, default=0)
    ai_sentiment_score: Mapped[float] = mapped_column(Float, default=0)
    ai_tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    negation_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    negation_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    contextual_factor: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporal_factor: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_gap: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_misperception: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    comparative_correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    linguistic_marker: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    anomaly_cross_rows: Mapped[list[AIFailAnomalyCross]] = relationship(
        back_populates="fail_analysis"
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_fail:{self.fail_id}",
            entity_id=self.sent_id,
            entity_type="ai_fail_analysis",
            title=f"AI Fail Analysis {self.fail_id}",
            description=f"AI failure analysis: {self.check_type}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"check_type": self.check_type},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIFailAnalysis:
        cf = model.custom_fields or {}
        return cls(
            sent_id=model.entity_id,
            check_type=str(cf.get("check_type") or ""),
        )


class AIFailPattern(Base):
    __tablename__ = "ai_fail_patterns"
    __table_args__ = (
        Index("idx_fail_pattern_kat", "fail_category"),
        Index("idx_fail_pattern_chk", "check_type"),
    )

    pattern_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fail_category: Mapped[str] = mapped_column(Text, nullable=False)
    negation_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level_avg: Mapped[float] = mapped_column(Float, default=0)
    avg_discrepancy: Mapped[float] = mapped_column(Float, default=0)
    avg_ai_confidence: Mapped[float] = mapped_column(Float, default=0)
    dominant_negation_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_panels: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_sent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_fail_pattern:{self.pattern_id}",
            entity_id=str(self.pattern_id),
            entity_type="ai_fail_pattern",
            title=f"AI Fail Pattern {self.pattern_id}",
            description=f"AI failure pattern: {self.fail_category}",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"fail_category": self.fail_category},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIFailPattern:
        cf = model.custom_fields or {}
        return cls(
            fail_category=str(cf.get("fail_category") or ""),
        )


class AIFailAnomalyCross(Base):
    __tablename__ = "ai_fail_anomaly_cross"
    __table_args__ = (
        Index("idx_fac_sent", "sent_id"),
        Index("idx_fac_fail", "fail_id"),
    )

    cross_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    fail_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_fail_analysis.fail_id"), nullable=True
    )
    anomaly_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    fail_analysis: Mapped[AIFailAnalysis | None] = relationship(
        back_populates="anomaly_cross_rows"
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_fail_cross:{self.cross_id}",
            entity_id=self.sent_id,
            entity_type="ai_fail_anomaly_cross",
            title=f"AI Fail Cross {self.cross_id}",
            description="AI failure anomaly cross-reference",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"fail_id": self.fail_id},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIFailAnomalyCross:
        cf = model.custom_fields or {}
        return cls(
            sent_id=model.entity_id,
            fail_id=cf.get("fail_id"),
            anomaly_type=str(cf.get("anomaly_type") or ""),
            severity=str(cf.get("severity") or ""),
        )


class AIFailCache(Base):
    __tablename__ = "ai_fail_cache"
    __table_args__ = (Index("idx_fcache_hash", "hash"),)

    hash: Mapped[str] = mapped_column(String, primary_key=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    def to_domain(self) -> Metadata:
        from bb_paxdata.domain.models.metadata import Metadata

        return Metadata(
            id=f"ai_fail_cache:{self.hash}",
            entity_id=self.hash,
            entity_type="ai_fail_cache",
            title=f"AI Fail Cache {self.hash}",
            description="Cached AI failure analysis",
            category=None,
            subcategory=None,
            source=None,
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=None,
            processing_version=None,
            access_level=None,
            expires_at=None,
            custom_fields={"hit_count": self.hit_count},
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> AIFailCache:
        cf = model.custom_fields or {}
        return cls(
            hash=model.entity_id,
            result_json=str(cf.get("result_json") or ""),
            hit_count=int(cf.get("hit_count") or 0),
        )
