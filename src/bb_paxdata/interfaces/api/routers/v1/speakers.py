from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.use_cases.speaker_registry_use_case import (
    SpeakerRegistryUseCase,
)
from bb_paxdata.infrastructure.db.models import File, Sentence, Speaker, SpeakerProfile
from bb_paxdata.infrastructure.db.repositories.speaker_repository import (
    SpeakerRepository,
)
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(prefix="/speakers", tags=["Speakers"])

# --- Pydantic Schemas ---


class SpeakerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    canonical_name: str
    display_name: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    bloc: str | None = None
    power_level: float | None = None
    role: str | None = None
    title: str | None = None
    organization: str | None = None
    is_active: bool = True
    aliases: list[str] = Field(default_factory=list)
    additional_metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata")


class SpeakerCreate(SpeakerBase):
    pass


class SpeakerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    display_name: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    bloc: str | None = None
    power_level: float | None = None
    role: str | None = None
    title: str | None = None
    organization: str | None = None
    is_active: bool | None = None
    aliases: list[str] | None = None
    additional_metadata: dict[str, Any] | None = Field(default=None, alias="metadata")


class SpeakerResponse(SpeakerBase):
    speaker_id: str
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    appearance_count: int
    data_source: str
    created_at: datetime
    updated_at: datetime


class SpeakerStatsResponse(SpeakerResponse):
    n_panels: int = 0
    n_segments: int = 0
    n_sentences: int = 0
    total_words: int = 0
    total_duration_sec: int = 0
    avg_sentiment: float = 0.0
    dominant_emotion: str | None = None
    dominant_topic: str | None = None
    cooperative_pct: float = 0.0
    constructive_pct: float = 0.0
    neutral_pct: float = 0.0
    concerned_pct: float = 0.0
    confrontational_pct: float = 0.0
    risk_event_count: int = 0
    top_topics: str | None = None
    avg_sentence_length: float = 0.0
    lexical_diversity: float = 0.0
    diplo_vocab_score: float = 0.0
    demand_count: int = 0
    pattern_diversity: float = 0.0
    avg_hedging_score: float = 0.0
    avg_politeness_ratio: float = 0.0
    avg_dki_score: float = 0.0
    dominant_frame: str | None = None
    dominant_audience: str | None = None


class PaginatedSpeakersResponse(BaseModel):
    items: list[SpeakerStatsResponse]
    total: int
    page: int
    limit: int
    pages: int


class KPIStatsSummary(BaseModel):
    total_speakers: int
    active_speakers: int
    represented_countries: int
    average_power_level: float


class CountryDistribution(BaseModel):
    country_code: str | None = None
    country_name: str | None = None
    count: int


class BlocDistribution(BaseModel):
    bloc: str | None = None
    count: int


class AppearanceItem(BaseModel):
    file_id: str
    title: str
    date_str: str | None = None
    sentence_count: int


class SentimentHistoryItem(BaseModel):
    file_id: str
    file_title: str
    date_str: str | None = None
    avg_sentiment: float
    sentence_count: int


# --- API Endpoints ---


@router.get("/stats/summary", response_model=KPIStatsSummary)
async def get_stats_summary(db: AsyncSession = Depends(get_db)):
    """Retrieve summary KPIs cards statistics."""
    repo = SpeakerRepository(db)
    stats = await repo.get_stats_summary()
    return stats


@router.get("/stats/by-country", response_model=list[CountryDistribution])
async def get_stats_by_country(db: AsyncSession = Depends(get_db)):
    """Retrieve speaker distribution by country."""
    stmt = (
        select(
            Speaker.country_code,
            Speaker.country_name,
            func.count(Speaker.speaker_id).label("count"),
        )
        .where(Speaker.country_code.isnot(None))
        .group_by(Speaker.country_code, Speaker.country_name)
    )

    res = await db.execute(stmt)
    return [
        {"country_code": row[0], "country_name": row[1], "count": row[2]}
        for row in res.all()
    ]


@router.get("/stats/by-bloc", response_model=list[BlocDistribution])
async def get_stats_by_bloc(db: AsyncSession = Depends(get_db)):
    """Retrieve speaker distribution by diplomatic bloc."""
    stmt = (
        select(Speaker.bloc, func.count(Speaker.speaker_id).label("count"))
        .where(Speaker.bloc.isnot(None))
        .group_by(Speaker.bloc)
    )

    res = await db.execute(stmt)
    return [{"bloc": row[0], "count": row[1]} for row in res.all()]


@router.get("", response_model=PaginatedSpeakersResponse)
async def list_speakers(
    db: AsyncSession = Depends(get_db),
    query: str | None = Query(None),
    country: str | None = Query(None),
    bloc: str | None = Query(None),
    sort_by: str = Query("canonical_name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Retrieve speakers with sorting, filtering and TanStack Table server-side pagination."""
    # Build core query joining Speaker with SpeakerProfile
    stmt = select(Speaker, SpeakerProfile).outerjoin(
        SpeakerProfile, Speaker.speaker_id == SpeakerProfile.speaker_id
    )

    # Filtering
    if query:
        like_query = f"%{query}%"
        stmt = stmt.where(
            or_(
                Speaker.canonical_name.ilike(like_query),
                Speaker.display_name.ilike(like_query),
                cast(Speaker.aliases, String).ilike(like_query),
            )
        )
    if country:
        stmt = stmt.where(Speaker.country_code == country)
    if bloc:
        stmt = stmt.where(Speaker.bloc == bloc)

    # Get total count before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_res = await db.execute(count_stmt)
    total_count = count_res.scalar() or 0

    # Sorting
    # Determine the column to sort on (support sorting on both Speaker and SpeakerProfile fields)
    sort_column = None
    if hasattr(Speaker, sort_by):
        sort_column = getattr(Speaker, sort_by)
    elif hasattr(SpeakerProfile, sort_by):
        sort_column = getattr(SpeakerProfile, sort_by)
    else:
        sort_column = Speaker.canonical_name

    if sort_order == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())

    # Pagination
    stmt = stmt.offset((page - 1) * limit).limit(limit)

    result = await db.execute(stmt)
    items = []
    for speaker, profile in result.all():
        # Merge speaker and profile fields
        item = {
            "speaker_id": speaker.speaker_id,
            "canonical_name": speaker.canonical_name,
            "display_name": speaker.display_name,
            "country_code": speaker.country_code,
            "country_name": speaker.country_name,
            "bloc": speaker.bloc,
            "power_level": speaker.power_level,
            "role": speaker.role,
            "title": speaker.title,
            "organization": speaker.organization,
            "is_active": speaker.is_active,
            "first_seen_at": speaker.first_seen_at,
            "last_seen_at": speaker.last_seen_at,
            "appearance_count": speaker.appearance_count,
            "data_source": speaker.data_source,
            "aliases": speaker.aliases or [],
            "metadata": speaker.additional_metadata or {},
            "created_at": speaker.created_at,
            "updated_at": speaker.updated_at,
            # Stats from SpeakerProfile
            "n_panels": profile.n_panels if profile else 0,
            "n_segments": profile.n_segments if profile else 0,
            "n_sentences": profile.n_sentences if profile else 0,
            "total_words": profile.total_words if profile else 0,
            "total_duration_sec": profile.total_duration_sec if profile else 0,
            "avg_sentiment": profile.avg_sentiment if profile else 0.0,
            "dominant_emotion": profile.dominant_emotion if profile else None,
            "dominant_topic": profile.dominant_topic if profile else None,
            "cooperative_pct": profile.cooperative_pct if profile else 0.0,
            "constructive_pct": profile.constructive_pct if profile else 0.0,
            "neutral_pct": profile.neutral_pct if profile else 0.0,
            "concerned_pct": profile.concerned_pct if profile else 0.0,
            "confrontational_pct": profile.confrontational_pct if profile else 0.0,
            "risk_event_count": profile.risk_event_count if profile else 0,
            "top_topics": profile.top_topics if profile else None,
            "avg_sentence_length": profile.avg_sentence_length if profile else 0.0,
            "lexical_diversity": profile.lexical_diversity if profile else 0.0,
            "diplo_vocab_score": profile.diplo_vocab_score if profile else 0.0,
            "demand_count": profile.demand_count if profile else 0,
            "pattern_diversity": profile.pattern_diversity if profile else 0.0,
            "avg_hedging_score": profile.avg_hedging_score if profile else 0.0,
            "avg_politeness_ratio": profile.avg_politeness_ratio if profile else 0.0,
            "avg_dki_score": profile.avg_dki_score if profile else 0.0,
            "dominant_frame": profile.dominant_frame if profile else None,
            "dominant_audience": profile.dominant_audience if profile else None,
        }
        items.append(item)

    pages = (total_count + limit - 1) // limit

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "pages": max(1, pages),
    }


@router.get("/{speaker_id}", response_model=SpeakerStatsResponse)
async def get_speaker(speaker_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve detailed info and stats profile for a single speaker."""
    stmt = (
        select(Speaker, SpeakerProfile)
        .outerjoin(SpeakerProfile, Speaker.speaker_id == SpeakerProfile.speaker_id)
        .where(Speaker.speaker_id == speaker_id)
    )

    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Speaker with ID {speaker_id} not found.",
        )

    speaker, profile = row
    item = {
        "speaker_id": speaker.speaker_id,
        "canonical_name": speaker.canonical_name,
        "display_name": speaker.display_name,
        "country_code": speaker.country_code,
        "country_name": speaker.country_name,
        "bloc": speaker.bloc,
        "power_level": speaker.power_level,
        "role": speaker.role,
        "title": speaker.title,
        "organization": speaker.organization,
        "is_active": speaker.is_active,
        "first_seen_at": speaker.first_seen_at,
        "last_seen_at": speaker.last_seen_at,
        "appearance_count": speaker.appearance_count,
        "data_source": speaker.data_source,
        "aliases": speaker.aliases or [],
        "metadata": speaker.additional_metadata or {},
        "created_at": speaker.created_at,
        "updated_at": speaker.updated_at,
        # Stats from SpeakerProfile
        "n_panels": profile.n_panels if profile else 0,
        "n_segments": profile.n_segments if profile else 0,
        "n_sentences": profile.n_sentences if profile else 0,
        "total_words": profile.total_words if profile else 0,
        "total_duration_sec": profile.total_duration_sec if profile else 0,
        "avg_sentiment": profile.avg_sentiment if profile else 0.0,
        "dominant_emotion": profile.dominant_emotion if profile else None,
        "dominant_topic": profile.dominant_topic if profile else None,
        "cooperative_pct": profile.cooperative_pct if profile else 0.0,
        "constructive_pct": profile.constructive_pct if profile else 0.0,
        "neutral_pct": profile.neutral_pct if profile else 0.0,
        "concerned_pct": profile.concerned_pct if profile else 0.0,
        "confrontational_pct": profile.confrontational_pct if profile else 0.0,
        "risk_event_count": profile.risk_event_count if profile else 0,
        "top_topics": profile.top_topics if profile else None,
        "avg_sentence_length": profile.avg_sentence_length if profile else 0.0,
        "lexical_diversity": profile.lexical_diversity if profile else 0.0,
        "diplo_vocab_score": profile.diplo_vocab_score if profile else 0.0,
        "demand_count": profile.demand_count if profile else 0,
        "pattern_diversity": profile.pattern_diversity if profile else 0.0,
        "avg_hedging_score": profile.avg_hedging_score if profile else 0.0,
        "avg_politeness_ratio": profile.avg_politeness_ratio if profile else 0.0,
        "avg_dki_score": profile.avg_dki_score if profile else 0.0,
        "dominant_frame": profile.dominant_frame if profile else None,
        "dominant_audience": profile.dominant_audience if profile else None,
    }
    return item


@router.post("", response_model=SpeakerResponse, status_code=status.HTTP_201_CREATED)
async def create_speaker(payload: SpeakerCreate, db: AsyncSession = Depends(get_db)):
    """Create a speaker manually."""
    uow = SqlAlchemyUnitOfWork(lambda: db)
    uow._session = db
    uow.speakers = SpeakerRepository(db)

    use_case = SpeakerRegistryUseCase(uow)
    context = {
        "country_code": payload.country_code,
        "country_name": payload.country_name,
        "bloc": payload.bloc,
        "power_level": payload.power_level,
        "role": payload.role,
        "title": payload.title,
        "organization": payload.organization,
        "is_active": payload.is_active,
        "aliases": payload.aliases,
        "metadata": payload.additional_metadata,
        "data_source": "manual",
    }

    try:
        speaker = await use_case.detect_or_create_speaker(
            payload.canonical_name, context
        )
        # Flush was done by use case, commit here
        await db.commit()
        await db.refresh(speaker)
        return speaker
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create speaker: {e!s}",
        )


@router.put("/{speaker_id}", response_model=SpeakerResponse)
async def update_speaker(
    speaker_id: str, payload: SpeakerUpdate, db: AsyncSession = Depends(get_db)
):
    """Update speaker details."""
    stmt = select(Speaker).where(Speaker.speaker_id == speaker_id)
    res = await db.execute(stmt)
    speaker = res.scalar_one_or_none()
    if not speaker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Speaker with ID {speaker_id} not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    if "metadata" in data and data["metadata"] is not None:
        speaker.additional_metadata = data.pop("metadata")

    for k, v in data.items():
        setattr(speaker, k, v)

    await db.commit()
    await db.refresh(speaker)
    return speaker


@router.get("/{speaker_id}/appearances", response_model=list[AppearanceItem])
async def get_speaker_appearances(speaker_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve list of files/panels the speaker appeared in."""
    stmt = (
        select(
            File.file_id,
            File.title,
            File.date_str,
            func.count(Sentence.sent_id).label("sentence_count"),
        )
        .join(Sentence, Sentence.file_id == File.file_id)
        .where(Sentence.speaker_id == speaker_id)
        .group_by(File.file_id, File.title, File.date_str)
        .order_by(File.date_str.desc())
    )

    res = await db.execute(stmt)
    return [
        {
            "file_id": row[0],
            "title": row[1],
            "date_str": row[2],
            "sentence_count": row[3],
        }
        for row in res.all()
    ]


@router.get(
    "/{speaker_id}/sentiment-history", response_model=list[SentimentHistoryItem]
)
async def get_speaker_sentiment_history(
    speaker_id: str, db: AsyncSession = Depends(get_db)
):
    """Retrieve speaker sentiment history time series data."""
    stmt = (
        select(
            File.file_id,
            File.title.label("file_title"),
            File.date_str.label("date_str"),
            func.avg(Sentence.vader_compound).label("avg_sentiment"),
            func.count(Sentence.sent_id).label("sentence_count"),
        )
        .join(Sentence, Sentence.file_id == File.file_id)
        .where(Sentence.speaker_id == speaker_id)
        .group_by(File.file_id, File.title, File.date_str)
        .order_by(File.date_str.asc())
    )

    res = await db.execute(stmt)
    return [
        {
            "file_id": row[0],
            "file_title": row[1],
            "date_str": row[2],
            "avg_sentiment": float(row[3] or 0.0),
            "sentence_count": row[4],
        }
        for row in res.all()
    ]
