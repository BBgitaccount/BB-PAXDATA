from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback for SQLite mode
    Vector = None

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    inspect,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from sqlalchemy.sql import delete
from sqlalchemy.sql.sqltypes import Enum as SQLEnum

from bb_paxdata.application.domain.enums.country_enums import RelationshipType
from bb_paxdata.application.domain.enums.demand_category import DemandCategory
from bb_paxdata.application.domain.enums.risk_level import RiskLevel
from bb_paxdata.application.domain.models.metadata import Metadata
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.discourse_network_table import (
    DiscourseNetworkEdgeTable,
)

if TYPE_CHECKING:
    from bb_paxdata.application.domain.enums import (
        EvidenceType,
        LogLevel,
    )
    from bb_paxdata.application.domain.models.analysis import Analysis
    from bb_paxdata.application.domain.models.argument import ArgumentGraph
    from bb_paxdata.application.domain.models.demand import Demand
    from bb_paxdata.application.domain.models.relationship import Relationship
    from bb_paxdata.application.domain.models.segment import Segment as SegmentDomain
    from bb_paxdata.application.domain.models.sentence import Sentence as SentenceDomain
    from bb_paxdata.application.domain.models.speaker import Speaker as SpeakerDomain
    from bb_paxdata.application.domain.models.topic import Topic
    from bb_paxdata.application.domain.models.transcript import Transcript
    from bb_paxdata.application.domain.models.validation_result import ValidationResult
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
                return datetime.strptime(value.replace("Z", ""), fmt).replace(
                    tzinfo=UTC
                )
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


def generate_speaker_id() -> str:
    return f"spk_{uuid.uuid4()}"


class Speaker(Base):
    __tablename__ = "speakers"

    speaker_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=generate_speaker_id
    )
    canonical_name: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String, nullable=True)
    bloc: Mapped[str | None] = mapped_column(String, nullable=True)
    power_level: Mapped[float | None] = mapped_column(
        Float,
        CheckConstraint("power_level >= 0.0 AND power_level <= 1.0"),
        nullable=True,
    )
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    organization: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    appearance_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    data_source: Mapped[str] = mapped_column(
        String, default="pipeline_auto", server_default="pipeline_auto"
    )
    aliases: Mapped[list[str] | None] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    additional_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    profile: Mapped[SpeakerProfile | None] = relationship(
        back_populates="master", uselist=False, cascade="all, delete-orphan"
    )


class File(Base):
    __tablename__ = "files"
    file_id: Mapped[str] = mapped_column(String, primary_key=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_map_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reprocess_count: Mapped[int] = mapped_column(Integer, default=0)
    force_rebuild: Mapped[int] = mapped_column(Integer, default=0)
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
        back_populates="file", cascade="all, delete-orphan", lazy="selectin"
    )
    network_edges: Mapped[list[DiscourseNetworkEdgeTable]] = relationship(
        back_populates="file", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_domain(self) -> Transcript:
        from bb_paxdata.application.domain.models.transcript import Transcript

        return Transcript(
            id=self.file_id,
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
                "idempotency_key": self.idempotency_key,
                "reprocess_count": self.reprocess_count,
                "force_rebuild": self.force_rebuild,
                "last_processed_at": (
                    self.last_processed_at.isoformat()
                    if self.last_processed_at
                    else None
                ),
                "file_name": self.file_name,
                "imported_at": (
                    self.imported_at.isoformat() if self.imported_at else None
                ),
            },
            log_level=None,
        )

    @classmethod
    def from_domain(cls, model: Transcript) -> File:
        meta = model.metadata or {}
        return cls(
            file_id=model.id,
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


class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"
    speaker_id: Mapped[str] = mapped_column(
        String, ForeignKey("speakers.speaker_id"), primary_key=True
    )
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

    segments: Mapped[list[Segment]] = relationship(
        primaryjoin="SpeakerProfile.speaker_id == foreign(Segment.speaker_id)",
        foreign_keys="[Segment.speaker_id]",
        back_populates="speaker",
        lazy="noload",
    )

    master: Mapped[Speaker] = relationship(back_populates="profile", lazy="joined")

    def to_domain(self) -> SpeakerDomain:
        from bb_paxdata.application.domain.enums import (
            BlocType,
            InfluenceTier,
            SpeakerRole,
        )
        from bb_paxdata.application.domain.models.speaker import (
            Speaker as SpeakerDomainModel,
        )

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
            avg_sentence_length=self.avg_sentence_length or None,
            speaking_percentage=None,
            first_speech_time=None,
            last_speech_time=None,
            total_speaking_time=(
                float(self.total_duration_sec) if self.total_duration_sec else None
            ),
            confidence_score=None,
        )

    @classmethod
    def from_domain(cls, model: Any) -> SpeakerProfile:
        if isinstance(model, Metadata):
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


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        Index("idx_seg_file", "file_id"),
        Index("idx_seg_country", "country"),
        Index("idx_seg_emotion", "emotion_category"),
        Index("idx_seg_topic", "dominant_topic"),
    )
    seg_id: Mapped[str] = mapped_column(String, primary_key=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.file_id"), nullable=False)
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
    file: Mapped[File] = relationship(back_populates="segments", lazy="joined")
    speaker: Mapped[SpeakerProfile | None] = relationship(
        primaryjoin="Segment.speaker_id == SpeakerProfile.speaker_id",
        foreign_keys=[speaker_id],
        back_populates="segments",
        lazy="joined",
    )
    master_speaker: Mapped[Speaker | None] = relationship(lazy="joined")

    sentences: Mapped[list[Sentence]] = relationship(
        back_populates="segment", cascade="all, delete-orphan", lazy="selectin"
    )
    ai_insight: Mapped[AISegmentInsight | None] = relationship(
        back_populates="segment", uselist=False, lazy="joined"
    )

    @property
    def id(self) -> str:
        return self.seg_id

    def to_domain(self) -> SegmentDomain:
        from bb_paxdata.application.domain.enums import (
            AudienceType,
            EvidenceType,
            FrameType,
            TopicCategory,
        )
        from bb_paxdata.application.domain.enums.signal_type import SignalType
        from bb_paxdata.application.domain.models.segment import (
            Segment as SegmentDomainModel,
        )

        risk_signals_parsed: list[Any] = []
        raw_list = []
        if isinstance(self.risk_signals, list):
            raw_list = self.risk_signals
        elif isinstance(self.risk_signals, str):
            try:
                loaded = json.loads(self.risk_signals)
                if isinstance(loaded, list):
                    raw_list = loaded
            except json.JSONDecodeError:
                pass

        for x in raw_list:
            if isinstance(x, str):
                try:
                    loaded_x = json.loads(x)
                    if isinstance(loaded_x, dict):
                        dict_x = dict(loaded_x)
                        if "signal_start" not in dict_x:
                            dict_x["signal_start"] = 0
                        if "signal_end" not in dict_x:
                            dict_x["signal_end"] = len(dict_x.get("signal_text", ""))
                        if "sentence_id" not in dict_x:
                            dict_x["sentence_id"] = "unknown"
                        raw_sig_type = dict_x.get("signal_type")
                        dict_x["signal_type"] = (
                            _try_enum(SignalType, raw_sig_type) or SignalType.CHEAP_TALK
                        )
                        risk_signals_parsed.append(dict_x)
                    else:
                        risk_signals_parsed.append(
                            {
                                "signal_text": x,
                                "signal_start": 0,
                                "signal_end": len(x),
                                "signal_type": SignalType.CHEAP_TALK,
                                "escalation_multiplier": 1.0,
                                "credibility_score": 0.5,
                                "sentence_id": "unknown",
                            }
                        )
                except json.JSONDecodeError:
                    risk_signals_parsed.append(
                        {
                            "signal_text": x,
                            "signal_start": 0,
                            "signal_end": len(x),
                            "signal_type": SignalType.CHEAP_TALK,
                            "escalation_multiplier": 1.0,
                            "credibility_score": 0.5,
                            "sentence_id": "unknown",
                        }
                    )
            elif isinstance(x, dict):
                dict_x = dict(x)
                if "signal_start" not in dict_x:
                    dict_x["signal_start"] = 0
                if "signal_end" not in dict_x:
                    dict_x["signal_end"] = len(dict_x.get("signal_text", ""))
                if "sentence_id" not in dict_x:
                    dict_x["sentence_id"] = "unknown"
                raw_sig_type = dict_x.get("signal_type")
                dict_x["signal_type"] = (
                    _try_enum(SignalType, raw_sig_type) or SignalType.CHEAP_TALK
                )
                risk_signals_parsed.append(dict_x)

        demand_concentration_parsed: dict[str, int] | None = None
        if isinstance(self.demand_concentration, dict):
            demand_concentration_parsed = {
                k: int(v) for k, v in self.demand_concentration.items()
            }
        elif isinstance(self.demand_concentration, str):
            try:
                loaded = json.loads(self.demand_concentration)
                if isinstance(loaded, dict):
                    demand_concentration_parsed = {k: int(v) for k, v in loaded.items()}
            except json.JSONDecodeError:
                demand_concentration_parsed = None

        return SegmentDomainModel(
            id=self.seg_id,
            panel_id=self.file_id,
            start_time=float(self.ts_start_sec) if self.ts_start_sec else None,
            end_time=float(self.ts_end_sec) if self.ts_end_sec else None,
            duration=float(self.duration_sec) if self.duration_sec else None,
            contextual_importance=None,
            temporal_pattern=None,
            dynamic_event=None,
            sentiment_arc=None,
            avg_sentiment_score=None,
            speaker=self.speaker.to_domain() if self.speaker else None,
            speaker_name=self.speaker_name,
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
            sbi_score=self.sbi_score,
            dki_score=self.dki_score,
            risk_score=self.risk_score,
            risk_signals=risk_signals_parsed if risk_signals_parsed else [],
            risk_trajectory=self.risk_trajectory,
            demand_concentration=demand_concentration_parsed,
            demand_count=self.demand_count,
            dominant_frame=_try_enum(FrameType, self.dominant_frame),
            dominant_audience=_try_enum(AudienceType, self.dominant_audience),
            dominant_evidence=_try_enum(EvidenceType, self.dominant_evidence),
            dominant_topic=(
                _try_enum(TopicCategory, self.dominant_topic)
                if self.dominant_topic
                else None
            ),
            emotion_category=self.emotion_category,
            vader_compound=self.vader_compound,
            avg_hedging_score=self.avg_hedging_score,
            formula_manip_score=self.formula_manip_score,
        )

    @classmethod
    def from_domain(
        cls, model: SegmentDomain, *, panel_id: str | None = None
    ) -> Segment:
        resolved_panel = panel_id or model.panel_id
        if not resolved_panel:
            raise ValueError("panel_id is required (argument or Segment.panel_id)")

        sp_name = model.speaker_name
        if not sp_name and model.speaker:
            if hasattr(model.speaker, "name"):
                sp_name = model.speaker.name
            elif isinstance(model.speaker, dict):
                sp_name = model.speaker.get("name")
        if not sp_name:
            sp_name = ""

        return cls(
            seg_id=model.id,
            file_id=resolved_panel,
            speaker_id=model.primary_speaker_id,
            speaker_name=sp_name,
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
        Index("idx_sent_file", "file_id"),
        Index("idx_sent_country", "country"),
        Index("idx_sent_speaker", "speaker_id"),
        Index("idx_sent_emotion", "emotion_category"),
        Index("idx_sent_topic", "dominant_topic"),
        Index("idx_sent_demand", "demand_type"),
        Index("idx_sent_rhetoric", "rhetoric_type"),
        Index("idx_sent_frame", "dominant_frame"),
        Index("idx_sent_audience", "audience_type"),
        Index("idx_sent_code", "sentence_code", unique=True),
    )
    sent_id: Mapped[str] = mapped_column(String, primary_key=True)
    sentence_code: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True
    )
    seg_id: Mapped[str] = mapped_column(ForeignKey("segments.seg_id"), nullable=False)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.file_id"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("speakers.speaker_id"), nullable=True
    )
    speaker_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloc: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    sent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    global_sent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    entities_org: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
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
    ai_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    logic_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_inconsistency_score: Mapped[float] = mapped_column(Float, default=0.0)
    discrepancy_score: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[list[float] | None] = (
        mapped_column(Vector(384), nullable=True)
        if Vector
        else mapped_column(JSON, nullable=True)
    )
    segment: Mapped[Segment] = relationship(back_populates="sentences", lazy="joined")
    ai_demand_analyses: Mapped[list[AIDemandAnalysis]] = relationship(
        back_populates="sentence", lazy="selectin"
    )
    ai_analysis: Mapped[AISentenceAnalysis | None] = relationship(
        back_populates="sentence", uselist=False, lazy="joined"
    )

    @property
    def id(self) -> str:
        return self.sent_id

    @property
    def segment_id(self) -> str:
        return self.seg_id

    def to_domain(self) -> SentenceDomain:
        from bb_paxdata.application.domain.enums import (
            AppraisalAttitude,
            AudienceType,
            EvidenceType,
            FrameType,
            SentimentCategory,
            TopicCategory,
        )
        from bb_paxdata.application.domain.models.sentence import (
            Sentence as SentenceDomainModel,
        )

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
            ts_dict = {k: float(v) for k, v in self.topic_scores.items()}
        elif isinstance(self.topic_scores, str):
            try:
                loaded = json.loads(self.topic_scores)
                if isinstance(loaded, dict):
                    ts_dict = {k: float(v) for k, v in loaded.items()}
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
            risk_score=self.risk_score,
            manipulation_score=self.negation_aware_diplo,
            is_demand=self.demand_type is not None,
            ai_analyzed=self.ai_analyzed,
            logic_result=self.logic_result,
            formula_inconsistency_score=self.formula_inconsistency_score,
            discrepancy_score=self.discrepancy_score,
            entities_gpe=(
                self.entities_gpe if isinstance(self.entities_gpe, list) else None
            ),
            global_sent_order=self.global_sent_order,
            speaker_name=self.speaker_name,
            country=self.country,
            role=self.role,
            bloc=self.bloc,
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
            file_id=panel_id,
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
            ai_analyzed=model.ai_analyzed,
            logic_result=model.logic_result,
            formula_inconsistency_score=model.formula_inconsistency_score,
            discrepancy_score=model.discrepancy_score,
        )


class Word(Base):
    """
    Kelime (Token) düzeyinde metin analizi sonuçlarını saklayan ORM tablosu.

    Semantik Kurallar:
    - sent_id: Kelimenin ait olduğu tekil cümlenin ID'si (sentences.sent_id FK).
    - seg_id: Kelimenin ait olduğu daha büyük konuşma bloğunun ID'si (segments.seg_id FK).
    - İkisi birden tutulur çünkü kelime düzeyinde hem cümle hem segment bazlı sorgular gerekir.
      Segmentler birden fazla cümle içerdiğinden ilişki 1-to-many'dir. Ancak her kelime bir cümleye
      bağlı olduğundan dolaylı olarak türetilebilir.
    """

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
    file_id: Mapped[str] = mapped_column(ForeignKey("files.file_id"), nullable=False)
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

    # Yeni NLP Öznitelikleri (Sorun #4)
    lemma: Mapped[str | None] = mapped_column(Text, nullable=True)
    pos_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    dep_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_negated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hedge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_diplomatic_term: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    char_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_domain(self) -> Metadata:
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
                "panel_id": self.file_id,
                "word_raw": self.word_raw,
                "word_norm": self.word_norm,
                "is_stopword": self.is_stopword,
                "diplo_score": self.diplo_score,
                "lemma": self.lemma,
                "pos_tag": self.pos_tag,
                "dep_label": self.dep_label,
                "entity_type": self.entity_type,
                "is_negated": self.is_negated,
                "is_hedge": self.is_hedge,
                "is_diplomatic_term": self.is_diplomatic_term,
                "char_offset_start": self.char_offset_start,
                "char_offset_end": self.char_offset_end,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> Word:
        cf = model.custom_fields or {}
        return cls(
            sent_id=str(cf["sent_id"]),
            seg_id=str(cf["seg_id"]),
            file_id=str(cf["panel_id"]),
            word_raw=str(cf.get("word_raw") or ""),
            word_norm=str(cf.get("word_norm") or ""),
            is_stopword=bool(cf.get("is_stopword")),
            diplo_score=float(cf.get("diplo_score") or 0),
            is_named_entity=bool(cf.get("is_named_entity") or False),
            lemma=cf.get("lemma"),
            pos_tag=cf.get("pos_tag"),
            dep_label=cf.get("dep_label"),
            entity_type=cf.get("entity_type"),
            is_negated=bool(cf.get("is_negated") or False),
            is_hedge=bool(cf.get("is_hedge") or False),
            is_diplomatic_term=bool(cf.get("is_diplomatic_term") or False),
            char_offset_start=cf.get("char_offset_start"),
            char_offset_end=cf.get("char_offset_end"),
        )


class CountryStat(Base):
    __tablename__ = "country_stats"
    country: Mapped[str] = mapped_column(Text, primary_key=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.file_id"), primary_key=True)
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
        topic_scores_parsed: dict[str, Any] | None = None
        if isinstance(self.topic_scores, dict):
            topic_scores_parsed = self.topic_scores
        elif isinstance(self.topic_scores, str):
            try:
                loaded = json.loads(self.topic_scores)
                if isinstance(loaded, dict):
                    topic_scores_parsed = loaded
            except json.JSONDecodeError:
                topic_scores_parsed = None

        return Metadata(
            id=f"country_stat:{self.country}:{self.file_id}",
            entity_id=self.file_id,
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
                "topic_scores": topic_scores_parsed,
                "words_per_minute": self.words_per_minute,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> CountryStat:
        cf = model.custom_fields or {}
        return cls(
            country=model.title or str(cf.get("country") or ""),
            file_id=model.entity_id,
            n_segments=int(cf.get("n_segments") or 0),
            topic_scores=cf.get("topic_scores"),
            words_per_minute=cf.get("words_per_minute"),
        )


class TopicMatrix(Base):
    __tablename__ = "topic_matrix"
    file_id: Mapped[str] = mapped_column(ForeignKey("files.file_id"), primary_key=True)
    country: Mapped[str] = mapped_column(Text, primary_key=True)
    topic: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    mention_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    demand_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dominant_emotion: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_frame: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_domain(self) -> Topic:
        from bb_paxdata.application.domain.enums import TopicCategory
        from bb_paxdata.application.domain.models.topic import Topic as TopicModel

        cat = _try_enum(TopicCategory, self.topic) or TopicCategory.NONE
        return TopicModel(
            id=f"{self.file_id}:{self.country}:{self.topic}",
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
            file_id=panel_id,
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
        from bb_paxdata.application.domain.enums import RelationshipType
        from bb_paxdata.application.domain.models.relationship import (
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
    file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files.file_id"), nullable=True
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

    # New fields for demand analysis (BLOAT-5)
    timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[float | None] = mapped_column(Float, nullable=True)
    compliance_likelihood: Mapped[float | None] = mapped_column(Float, nullable=True)
    assertiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    politeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    compliance_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_demand_ids: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    is_conditional: Mapped[bool] = mapped_column(Boolean, default=False)
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_implication: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_fulfilled: Mapped[bool] = mapped_column(Boolean, default=False)
    fulfillment_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def to_domain(self) -> Demand:
        from bb_paxdata.application.domain.enums import DemandCategory, DemandType
        from bb_paxdata.application.domain.models.demand import Demand as DemandModel

        dt = _try_enum(DemandType, self.demand_type) or DemandType.INTENTION
        dc = (
            _try_enum(DemandCategory, self.demand_category)
            if self.demand_category
            else DemandCategory.DIPLOMATIC_ENGAGEMENT
        )

        related_demand_ids_parsed: list[Any] | None = None
        if isinstance(self.related_demand_ids, list):
            related_demand_ids_parsed = self.related_demand_ids
        elif isinstance(self.related_demand_ids, str):
            try:
                loaded = json.loads(self.related_demand_ids)
                if isinstance(loaded, list):
                    related_demand_ids_parsed = loaded
            except json.JSONDecodeError:
                related_demand_ids_parsed = None

        conditions_parsed: list[Any] | None = None
        if isinstance(self.conditions, list):
            conditions_parsed = self.conditions
        elif isinstance(self.conditions, str):
            try:
                loaded = json.loads(self.conditions)
                if isinstance(loaded, list):
                    conditions_parsed = loaded
            except json.JSONDecodeError:
                conditions_parsed = None

        tags_parsed: list[Any] | None = None
        if isinstance(self.tags, list):
            tags_parsed = self.tags
        elif isinstance(self.tags, str):
            try:
                loaded = json.loads(self.tags)
                if isinstance(loaded, list):
                    tags_parsed = loaded
            except json.JSONDecodeError:
                tags_parsed = None

        extra_metadata_parsed: dict[str, Any] | None = None
        if isinstance(self.extra_metadata, dict):
            extra_metadata_parsed = self.extra_metadata
        elif isinstance(self.extra_metadata, str):
            try:
                loaded = json.loads(self.extra_metadata)
                if isinstance(loaded, dict):
                    extra_metadata_parsed = loaded
            except json.JSONDecodeError:
                extra_metadata_parsed = None

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
            timestamp=self.timestamp,
            deadline=self.deadline,
            compliance_likelihood=self.compliance_likelihood,
            assertiveness_score=self.assertiveness_score,
            politeness_score=self.politeness_score,
            evidence_types=[],
            confidence_score=min(1.0, max(0.0, self.demand_weight or 0.5)),
            response_text=self.response_text,
            response_timestamp=self.response_timestamp,
            compliance_status=self.compliance_status,
            related_demand_ids=related_demand_ids_parsed or [],
            is_conditional=self.is_conditional or False,
            conditions=conditions_parsed or [],
            impact_score=self.impact_score,
            risk_implication=self.risk_implication,
            is_active=self.is_active or True,
            is_fulfilled=self.is_fulfilled or False,
            fulfillment_timestamp=self.fulfillment_timestamp,
            notes=self.notes,
            tags=tags_parsed or [],
            metadata=extra_metadata_parsed or {},
        )

    @classmethod
    def from_domain(cls, model: Demand, *, panel_id: str | None = None) -> DemandRecord:
        return cls(
            sent_id=model.sentence_id,
            seg_id=model.segment_id,
            file_id=panel_id,
            speaker_name=model.speaker_id,
            country="",
            demand_verb="",
            demand_type=model.demand_type.value,
            demand_weight=model.confidence_score,
            demand_category=model.demand_category.value,
            full_sentence=model.demand_text,
            timestamp=model.timestamp,
            deadline=model.deadline,
            compliance_likelihood=model.compliance_likelihood,
            assertiveness_score=model.assertiveness_score,
            politeness_score=model.politeness_score,
            response_text=model.response_text,
            response_timestamp=model.response_timestamp,
            compliance_status=model.compliance_status,
            related_demand_ids=model.related_demand_ids,
            is_conditional=model.is_conditional,
            conditions=model.conditions,
            impact_score=model.impact_score,
            risk_implication=model.risk_implication,
            is_active=model.is_active,
            is_fulfilled=model.is_fulfilled,
            fulfillment_timestamp=model.fulfillment_timestamp,
            notes=model.notes,
            tags=model.tags,
            extra_metadata=model.metadata,
        )


class PatternRecord(Base):
    __tablename__ = "pattern_records"
    __table_args__ = (
        Index("idx_pattern_type", "pattern_type"),
        Index("idx_pattern_country", "country"),
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 10", name="check_risk_score_range"
        ),
        CheckConstraint(
            "sentiment_category IN ('cooperative', 'confrontational', 'concerned', 'neutral_cautious', 'constructive', 'neutral', 'unknown')",
            name="check_sentiment_category",
        ),
        UniqueConstraint(
            "sent_id", "pattern_type", "matched_keyword", name="uq_pattern_per_sentence"
        ),
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
    file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files.file_id"), nullable=True
    )
    speaker_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    power_level: Mapped[int] = mapped_column(Integer, default=0)
    pattern_type: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_subtype: Mapped[str | None] = mapped_column(Text, nullable=True)
    pattern_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_keyword: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    prev_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    diplo_compound: Mapped[float] = mapped_column(Float, default=0)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sentiment_category: Mapped[str | None] = mapped_column(
        Text, default="unknown", nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def to_domain(self) -> Metadata:
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


class FileDynamics(Base):
    __tablename__ = "panel_dynamics"
    __table_args__ = (
        Index("idx_dyn_panel", "file_id"),
        Index("idx_dyn_sent", "sent_id", unique=True),
    )
    dyn_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files.file_id"), nullable=True
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
                "panel_id": self.file_id,
                "position": self.position,
                "kgi_score": self.kgi_score,
                "risk_delta": self.risk_delta,
                "emotion_shift": self.emotion_shift,
                "topic_shift": self.topic_shift,
                "inconsistency_score": self.inconsistency_score,
                "sent_id": self.sent_id,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> FileDynamics:
        cf = model.custom_fields or {}
        return cls(
            file_id=cf.get("panel_id"),
            position=int(cf.get("position") or 0),
            kgi_score=float(cf.get("kgi_score") or 0),
            risk_delta=float(cf.get("risk_delta") or 0),
            emotion_shift=float(cf.get("emotion_shift") or 0),
            topic_shift=int(cf.get("topic_shift") or 0),
            inconsistency_score=float(cf.get("inconsistency_score") or 0),
            sent_id=str(cf["sent_id"]),
        )


class AISentenceAnalysis(Base):
    __tablename__ = "ai_sentence_analysis"
    __table_args__ = (
        Index("idx_ai_sent_id", "sent_id"),
        Index("idx_ai_panel", "file_id"),
        Index("idx_ai_country", "country"),
        Index("idx_ai_logic", "overall_logic_check"),
        Index("idx_ai_risk", "risk_level"),
        Index("idx_ai_tone", "diplomatic_tone"),
        Index("idx_ai_prompt_processed", "prompt_version", "processed_at"),
        Index("idx_ai_processed_at", "processed_at"),
        Index("idx_ai_sentence_code", "sentence_code"),
    )
    ai_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(
        ForeignKey("sentences.sent_id"), nullable=False
    )
    sentence_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        comment="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    topic_diversity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Shannon entropy of BERTopic P(topic|doc) distribution (Faz 5). "
        "0.0 = fully focused, higher = dispersed topic signal.",
    )
    diplomatic_tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    manipulation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_inconsistency: Mapped[bool] = mapped_column(Boolean, default=False)
    coherence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="DualGate consensus coherence score (0.0-1.0)"
    )
    anomaly_consensus_level: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="CLEAN|SOFT_ANOMALY|HARD_ANOMALY|CRITICAL_ANOMALY",
    )
    anomaly_ai_decision: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="CONFIRMED|DISMISSED|ESCALATED|AI_ONLY|INCONCLUSIVE",
    )
    anomaly_ai_reasoning: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="AI Anomaly Controller reasoning"
    )
    anomaly_detected_subtype: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="irony|rhetorical_strategy|coercive_signal|tone_drift",
    )
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
    backend: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    logic_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_flags: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_types: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    anomaly_severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    backend_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    speech_act_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    @property
    def speech_act_domain(self):
        if self.speech_act_json is None:
            return None
        from bb_paxdata.application.domain.models.speech_act import (
            SpeechActClassification,
        )

        return SpeechActClassification.model_validate(self.speech_act_json)

    sentence: Mapped[Sentence | None] = relationship(
        back_populates="ai_analysis", lazy="joined"
    )

    def to_domain(self) -> Analysis:
        from bb_paxdata.application.domain.enums import RiskLevel
        from bb_paxdata.application.domain.models.analysis import (
            Analysis as AnalysisModel,
        )

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
            analysis_timestamp=datetime.now(UTC),
            analyzer_id=None,
            sumcomplexity_score=None,
            detailed_findings=None,
            recommendations=[],
            framing=self.framing or self.ai_frame_type,
            speech_act=self.speech_act_domain,
        )

    @classmethod
    def from_domain(
        cls,
        model: Analysis,
        *,
        sent_id: str,
        file_id: str | None = None,
        sentence_code: str | None = None,
        speaker_name: str | None = None,
        country: str | None = None,
        power_level: int = 0,
        global_sent_order: int | None = None,
        sentiment_score: float | None = None,
        sentiment_category: str | None = None,
        risk_score: int | None = None,
        ai_sentiment: str | None = None,
        ai_risk_score: float | None = None,
        ai_frame_type: str | None = None,
        hedging_score: float | None = None,
        politeness_score: float | None = None,
        logic_result: str | None = None,
    ) -> AISentenceAnalysis:
        consensus = getattr(model, "consensus_result", None)

        def _get_val(obj, key, default=None):
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        coherence_val = _get_val(consensus, "coherence_score")
        if coherence_val is None:
            coherence_val = getattr(model, "coherence_score", None)

        level = _get_val(consensus, "level")
        level_val = getattr(level, "value", level) if level is not None else None

        ai_result = _get_val(consensus, "ai_result")
        decision = _get_val(ai_result, "decision")
        decision_val = (
            getattr(decision, "value", decision) if decision is not None else None
        )

        reasoning = _get_val(ai_result, "reasoning")
        detected_subtype = _get_val(ai_result, "detected_subtype")

        obj = cls(
            sent_id=sent_id,
            prompt_version="v1",
            seg_id=model.segment_id,
            risk_level=model.risk_level.value,
            sentiment_score=(
                model.sentiment_score if sentiment_score is None else sentiment_score
            ),
            manipulation_score=model.manipulation_score,
            framing=model.framing,
            coherence_score=coherence_val,
            anomaly_consensus_level=level_val,
            anomaly_ai_decision=decision_val,
            anomaly_ai_reasoning=reasoning,
            anomaly_detected_subtype=detected_subtype,
            speech_act_json=model.speech_act.model_dump() if model.speech_act else None,
            topic_diversity=model.topic_diversity_score,
        )
        if file_id is not None:
            obj.file_id = file_id
        if sentence_code is not None:
            obj.sentence_code = sentence_code
        if speaker_name is not None:
            obj.speaker_name = speaker_name
        if country is not None:
            obj.country = country
        obj.power_level = power_level
        if global_sent_order is not None:
            obj.global_sent_order = global_sent_order
        if sentiment_category is not None:
            obj.sentiment_category = sentiment_category
        if risk_score is not None:
            obj.risk_score = risk_score
        if ai_sentiment is not None:
            obj.ai_sentiment = ai_sentiment
        if ai_risk_score is not None:
            obj.ai_risk_score = round(ai_risk_score)
        if ai_frame_type is not None:
            obj.ai_frame_type = ai_frame_type
        if hedging_score is not None:
            obj.hedging_score = hedging_score
        if politeness_score is not None:
            obj.politeness_score = politeness_score
        if logic_result is not None:
            obj.logic_result = logic_result
        return obj


class AIValidationLog(Base):
    __tablename__ = "ai_validation_log"
    __table_args__ = (
        Index("idx_val_sent", "sent_id"),
        Index("idx_val_result", "result"),
        Index("idx_val_type", "check_type"),
        Index("idx_val_sentence_code", "sentence_code"),
    )
    val_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    sentence_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        from bb_paxdata.application.domain.models.validation_result import (
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
    prompt_version: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        comment="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
    file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    ai_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_insight_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    insight_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    segment: Mapped[Segment] = relationship(back_populates="ai_insight", lazy="joined")

    def to_domain(self) -> Metadata:
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
        Index("idx_flags_sentence_code", "sentence_code"),
    )
    flag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    sentence_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    prompt_version: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        comment="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        back_populates="ai_demand_analyses", lazy="joined"
    )
    demand_record: Mapped[DemandRecord | None] = relationship(lazy="joined")

    def to_domain(self) -> Metadata:
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
    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.file_id"), unique=True, nullable=False
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        comment="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
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
        return Metadata(
            id=f"ai_panel_synth:{self.synthesis_id}",
            entity_id=self.file_id,
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
            file_id=model.entity_id,
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
        Index("idx_fail_panel", "file_id"),
        Index("idx_fail_sentence_code", "sentence_code"),
    )
    fail_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_id: Mapped[str] = mapped_column(Text, nullable=False)
    sentence_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        comment="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        back_populates="fail_analysis", lazy="selectin"
    )

    def to_domain(self) -> Metadata:
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
        back_populates="anomaly_cross_rows", lazy="joined"
    )

    def to_domain(self) -> Metadata:
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


class DependencyTripleORM(Base):
    __tablename__ = "dependency_triples"
    __table_args__ = (
        Index("idx_dep_sent", "sent_id"),
        Index("idx_dep_panel", "file_id"),
        Index("idx_dep_from", "subject_resolved"),
        Index("idx_dep_to", "object_resolved"),
        Index("idx_dep_verb", "verb_lemma"),
    )
    triple_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    sent_id: Mapped[str] = mapped_column(String, nullable=False)
    seg_id: Mapped[str | None] = mapped_column(String, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_resolved: Mapped[str | None] = mapped_column(Text, nullable=True)
    verb_lemma: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_resolved: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_passive: Mapped[int] = mapped_column(Integer, default=0)
    is_negative: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_context: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    human_verified: Mapped[int] = mapped_column(Integer, default=0)
    verification_status: Mapped[str] = mapped_column(Text, default="AUTO")
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )


class ActorActionMatrixORM(Base):
    __tablename__ = "actor_action_matrix"
    __table_args__ = (
        Index("idx_matrix_panel", "file_id"),
        Index("idx_matrix_actor", "actor_id"),
        Index("idx_matrix_action", "action_type"),
    )
    matrix_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )


class AIExplanationsORM(Base):
    __tablename__ = "ai_explanations"
    __table_args__ = (Index("idx_exp_sent", "sent_id"),)
    explanation_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    sent_id: Mapped[str] = mapped_column(String, nullable=False)
    risk_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    grammatical_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    discrepancy_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    token_attributions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )


class FormulaValidationLog(Base):
    __tablename__ = "formula_validation_logs"
    __table_args__ = (
        Index("idx_fval_run", "run_id"),
        Index("idx_fval_entity", "entity_type", "entity_id"),
        Index("idx_fval_formula", "formula_name"),
        Index("idx_fval_status", "status"),
        Index("idx_fval_sentence_code", "sentence_code"),
        Index("idx_fval_is_current", "is_current"),
        Index("idx_fval_reviewer", "reviewer_id"),
        Index("idx_fval_human_verdict", "human_verdict"),
    )
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    sentence_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    formula_name: Mapped[str] = mapped_column(String, nullable=False)
    expected_constraint: Mapped[str] = mapped_column(Text, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    human_review_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    human_verdict: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    human_corrected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    human_reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_reviewer_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    log_version: Mapped[int] = mapped_column(Integer, default=1)
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_triage_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_at_review: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    audit_entries: Mapped[list[FormulaValidationAudit]] = relationship(
        "FormulaValidationAudit", back_populates="log", lazy="selectin"
    )

    def to_domain(self) -> Metadata:
        return Metadata(
            id=f"formula_val:{self.log_id}",
            entity_id=self.entity_id,
            entity_type="formula_validation_log",
            title=f"Formula {self.formula_name} validation",
            description=f"Formula Validation {self.status} for {self.entity_type} {self.entity_id}",
            category=self.formula_name,
            subcategory=self.status,
            source="FormulaAuditor",
            source_url=None,
            source_date=None,
            quality_score=None,
            validation_status=self.status,
            last_validated=self.created_at,
            processed_by="FormulaAuditor",
            processing_version="2.0",
            access_level=None,
            expires_at=None,
            custom_fields={
                "run_id": self.run_id,
                "entity_type": self.entity_type,
                "expected_constraint": self.expected_constraint,
                "actual_value": self.actual_value,
                "details": self.details,
                "human_verdict": self.human_verdict,
                "human_corrected_value": self.human_corrected_value,
                "log_version": self.log_version,
                "is_current": self.is_current,
            },
        )

    @classmethod
    def from_domain(cls, model: Metadata) -> FormulaValidationLog:
        cf = model.custom_fields or {}
        return cls(
            run_id=cf.get("run_id", ""),
            entity_type=cf.get("entity_type", ""),
            entity_id=model.entity_id,
            formula_name=model.category or "",
            expected_constraint=cf.get("expected_constraint", ""),
            actual_value=float(cf.get("actual_value", 0.0)),
            status=model.validation_status or "FAIL",
            details=cf.get("details"),
        )


class FormulaValidationAudit(Base):
    __tablename__ = "formula_validation_audit"
    __table_args__ = (
        Index("idx_faudit_log", "log_id"),
        Index("idx_faudit_action", "action_type"),
        Index("idx_faudit_performer", "performed_by"),
        Index("idx_faudit_at", "performed_at"),
    )
    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("formula_validation_logs.log_id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    log: Mapped[FormulaValidationLog] = relationship(
        "FormulaValidationLog", back_populates="audit_entries", lazy="joined"
    )

    def to_domain(self) -> Metadata:
        return Metadata(
            id=f"formula_audit:{self.audit_id}",
            entity_id=str(self.log_id),
            entity_type="formula_validation_audit",
            title=f"Audit {self.action_type} on log {self.log_id}",
            description=f"{self.performed_by} → {self.action_type}: {self.previous_verdict} → {self.new_verdict}",
            category=self.action_type,
            subcategory=self.review_status,
            source="HITL",
            source_url=None,
            source_date=self.performed_at,
            quality_score=None,
            validation_status=None,
            last_validated=None,
            processed_by=self.performed_by,
            processing_version="2.0",
            access_level=None,
            expires_at=None,
            custom_fields={
                "previous_verdict": self.previous_verdict,
                "new_verdict": self.new_verdict,
                "previous_value": self.previous_value,
                "new_value": self.new_value,
                "justification": self.justification,
                "ip_address": self.ip_address,
            },
        )


class ReviewerAssignment(Base):
    __tablename__ = "reviewer_assignments"
    __table_args__ = (
        Index("idx_rassign_reviewer", "reviewer_id"),
        Index("idx_rassign_scope", "scope_type", "scope_value"),
        UniqueConstraint(
            "reviewer_id", "scope_type", "scope_value", name="uq_reviewer_scope"
        ),
    )
    assignment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_value: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(20), nullable=False)
    max_daily_reviews: Mapped[int] = mapped_column(Integer, default=50)
    current_daily_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


class SegmentAnalyzedEvent(Base):
    __tablename__ = "segment_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    text_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    vader_compound: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    diplo_compound: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vad_vector: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    emotion_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    demand_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    speech_act: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hedging_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    politeness_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    topic_scores: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    topic_model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    frame_distribution: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    pipeline_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    power_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ActorTopicProjection(Base):
    __tablename__ = "actor_topic_projection"
    file_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    country: Mapped[str] = mapped_column(String(100), primary_key=True)
    topic: Mapped[str] = mapped_column(String(200), primary_key=True)
    topic_model_version: Mapped[str] = mapped_column(String(50), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fuzzy_mention_mass: Mapped[float] = mapped_column(Float, nullable=False)
    avg_sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment_ci_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_ci_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score_raw: Mapped[float | None] = mapped_column(
        Float, default=0.0, nullable=True
    )
    risk_score_weighted: Mapped[float | None] = mapped_column(
        Float, default=0.0, nullable=True
    )
    risk_score_normalized: Mapped[float | None] = mapped_column(
        Float, default=0.0, nullable=True
    )
    risk_ci_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_ci_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_risk_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    demand_count: Mapped[float] = mapped_column(Float, nullable=False)
    demand_density_per_1k: Mapped[float | None] = mapped_column(Float, nullable=True)
    speech_act_distribution: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    avg_vad: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dominant_emotion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frame_distribution: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    dominant_frame: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frame_competition_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hedging: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_politeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    diplomatic_signal_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_entropy: Mapped[float | None] = mapped_column(Float, nullable=True)
    js_divergence: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_coalition_actors: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    last_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ActorTopicDocument(Base):
    __tablename__ = "actor_topic_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    topic_model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    topic_details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    network_edges: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    diplomatic_tension_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    agenda_diversity_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AggregationLineage(Base):
    __tablename__ = "aggregation_lineage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    projection_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    weight_contribution: Mapped[float] = mapped_column(Float, nullable=False)
    contribution_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TopicModelVersion(Base):
    __tablename__ = "topic_model_versions"
    version_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    corpus_checksum: Mapped[str] = mapped_column(String(64), nullable=False)


class TopicMapping(Base):
    __tablename__ = "topic_mappings"
    version_from: Mapped[str] = mapped_column(String(50), primary_key=True)
    topic_from: Mapped[str] = mapped_column(String(200), primary_key=True)
    version_to: Mapped[str] = mapped_column(String(50), primary_key=True)
    topic_to: Mapped[str] = mapped_column(String(200), primary_key=True)
    wasserstein_distance: Mapped[float] = mapped_column(Float, nullable=False)
    mapping_confidence: Mapped[float] = mapped_column(Float, nullable=False)


class DomainEvent(Base):
    __tablename__ = "domain_events"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    __table_args__ = (
        Index("ix_domain_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_domain_events_type_time", "event_type", "occurred_at"),
    )


class OutboxEventORM(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    endpoint_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class DeadLetterEventORM(Base):
    __tablename__ = "dead_letter_events"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    original_event_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    moved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class WebhookSubscriptionORM(Base):
    __tablename__ = "webhook_subscriptions"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    endpoint_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    event_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


@event.listens_for(Session, "before_flush")
def delete_outbox_event_on_resolved_dead_letter(session, flush_context, instances):
    event_ids_to_delete = set()

    for obj in session.new:
        if isinstance(obj, DeadLetterEventORM) and obj.resolved:
            event_ids_to_delete.add(obj.original_event_id)

    for obj in session.dirty:
        if isinstance(obj, DeadLetterEventORM):
            from sqlalchemy.orm import PassiveFlag

            state = inspect(obj)
            history = state.get_history("resolved", PassiveFlag.PASSIVE_NO_FETCH)
            if history.has_changes() and obj.resolved:
                event_ids_to_delete.add(obj.original_event_id)

    if event_ids_to_delete:
        session.execute(
            delete(OutboxEventORM).where(OutboxEventORM.id.in_(event_ids_to_delete))
        )
        for value in list(session.identity_map.values()):
            if isinstance(value, OutboxEventORM):
                state = inspect(value)
                obj_id = state.identity[0] if state.identity else state.dict.get("id")
                if obj_id in event_ids_to_delete:
                    session.expunge(value)


@event.listens_for(Session, "before_flush")
def extract_and_persist_domain_events(session, flush_context, instances):
    # Collect all domain events from session.new, session.dirty, and loaded instances
    events_to_emit = []

    all_instances = (
        set(session.new) | set(session.dirty) | set(session.identity_map.values())
    )
    for obj in all_instances:
        if hasattr(obj, "_domain_events") and obj._domain_events:
            events_to_emit.extend(obj._domain_events)
            obj._domain_events.clear()

    if not events_to_emit:
        return

    # Import ORM models locally to avoid circular imports
    from sqlalchemy import select

    from bb_paxdata.infrastructure.db.models import (
        DomainEvent,
        OutboxEventORM,
        WebhookSubscriptionORM,
    )

    # Fetch active webhook subscriptions to produce OutboxEventORM rows
    stmt = select(WebhookSubscriptionORM).where(
        WebhookSubscriptionORM.is_active.is_(True)
    )
    subscriptions = session.execute(stmt).scalars().all()

    for e in events_to_emit:
        evt_version = e.get("event_version", 1)
        # 1. Persist the DomainEvent in database
        event_orm = DomainEvent(
            aggregate_type=e["aggregate_type"],
            aggregate_id=e["aggregate_id"],
            event_type=e["event_type"],
            event_version=evt_version,
            payload=e["payload"],
            actor_id=e.get("actor_id"),
            correlation_id=e.get("correlation_id"),
            occurred_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(event_orm)

        # 2. Add OutboxEventORM for active subscriptions
        evt_type = e["event_type"]
        agg_id = e["aggregate_id"]
        payl = e["payload"]

        for sub in subscriptions:
            if "*" in sub.event_types or evt_type in sub.event_types:
                outbox_event = OutboxEventORM(
                    event_type=evt_type,
                    event_version=evt_version,
                    aggregate_id=agg_id,
                    payload=payl,
                    endpoint_url=sub.endpoint_url,
                    secret=sub.secret,
                    endpoint_id=sub.id,
                )
                session.add(outbox_event)


@event.listens_for(Session, "before_flush")
def detect_outbox_events(session, flush_context, instances):
    for obj in session.new:
        if isinstance(obj, OutboxEventORM):
            session.info["has_outbox_events"] = True
            break


@event.listens_for(Session, "after_commit")
def trigger_outbox_processing_after_commit(session):
    if session.info.get("has_outbox_events", False):
        session.info["has_outbox_events"] = False
        try:
            from bb_paxdata.infrastructure.webhooks.tasks import process_outbox_queue

            process_outbox_queue.delay()
        except Exception:
            # Prevent breaking application flow if Celery/Redis is not running or misconfigured
            pass


@event.listens_for(Session, "after_rollback")
def clear_outbox_events_on_rollback(session):
    session.info["has_outbox_events"] = False


class ArgumentGraphNode(Base):
    __tablename__ = "argument_graph_nodes"
    __table_args__ = (
        Index("idx_arg_node_graph", "graph_id"),
        Index("idx_arg_node_speaker", "speaker"),
        Index("idx_arg_node_type", "node_type"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    stance: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    predicate: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_negated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


class ArgumentGraphEdge(Base):
    __tablename__ = "argument_graph_edges"
    __table_args__ = (
        Index("idx_edge_graph", "graph_id"),
        Index("idx_edge_source_target", "source_id", "target_id"),
        Index("idx_edge_type", "relation_type"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    edge_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_cross_speaker: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


class ArgumentGraphMetadata(Base):
    __tablename__ = "argument_graphs_metadata"
    __table_args__ = (Index("idx_arg_meta_doc", "document_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graph_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    document_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_claim_ids: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    total_edges: Mapped[int] = mapped_column(Integer, default=0)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)
    graph_density: Mapped[float] = mapped_column(Float, default=0.0)
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    attack_count: Mapped[int] = mapped_column(Integer, default=0)
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    graph_snapshot_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    def to_domain(self) -> ArgumentGraph:
        from bb_paxdata.application.domain.models.argument import ArgumentGraph

        graph_data: dict[str, Any] | None = None
        if isinstance(self.graph_snapshot_json, dict):
            graph_data = self.graph_snapshot_json
        elif isinstance(self.graph_snapshot_json, str):
            try:
                loaded = json.loads(self.graph_snapshot_json)
                if isinstance(loaded, dict):
                    graph_data = loaded
            except json.JSONDecodeError:
                graph_data = None

        if graph_data:
            try:
                return ArgumentGraph(**graph_data, skip_validation=True)
            except Exception as e:
                import structlog

                logger = structlog.get_logger(__name__)
                logger.error(f"Failed to deserialize graph snapshot: {e}")
        return ArgumentGraph(
            graph_id=self.graph_id,
            document_id=self.document_id,
            root_claim_ids=self.root_claim_ids or [],
            total_nodes=self.total_nodes,
            total_edges=self.total_edges,
            skip_validation=True,
        )

    @classmethod
    def from_domain(cls, graph: ArgumentGraph) -> ArgumentGraphMetadata:
        return cls(
            graph_id=graph.graph_id,
            document_id=graph.document_id,
            root_claim_ids=graph.root_claim_ids,
            total_nodes=graph.total_nodes,
            total_edges=graph.total_edges,
            max_depth=graph.max_depth,
            graph_density=graph.graph_density,
            claim_count=graph.claim_count,
            attack_count=graph.attack_count,
            support_count=graph.support_count,
            model_version=graph.model_version,
            processing_time_ms=graph.processing_time_ms,
            graph_snapshot_json=graph.model_dump(),
        )


class PromptVersion(Base):
    """Database-backed prompt version storage for migration support."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_id_version"),
        Index("idx_prompt_id_active", "prompt_id", "is_active"),
        Index("idx_prompt_id_language", "prompt_id", "language"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    model_name: Mapped[str] = mapped_column(
        String(100), default="gpt-4o", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="any", nullable=False)
    academic_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class Entry(Base):
    """Physical entries table to support verification and backfill verification requirements."""

    __tablename__ = "entries"
    person: Mapped[str] = mapped_column(String(255), primary_key=True)
