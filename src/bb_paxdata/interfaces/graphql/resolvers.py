# src/bb_paxdata/interfaces/graphql/resolvers.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import strawberry
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import File, Segment, Sentence
from bb_paxdata.interfaces.graphql.types import (
    AnalysisConnection,
    AnalysisEdge,
    AnalysisType,
    CreateAnalysisInput,
    PageInfo,
    SentenceType,
    decode_cursor,
    encode_cursor,
)


async def resolve_analysis(
    info: strawberry.types.Info, id: strawberry.ID
) -> AnalysisType | None:
    session: AsyncSession = info.context["db"]
    stmt = select(File).where(File.file_id == str(id))
    result = await session.execute(stmt)
    file = result.scalar_one_or_none()
    if not file:
        return None
    return AnalysisType(
        id=strawberry.ID(file.file_id),
        title=file.title or file.file_name,
        created_at=file.first_processed_at or datetime.now(timezone.utc),
        status="COMPLETE",
        source_language=file.file_format or "tr",
    )


async def resolve_analyses_connection(
    info: strawberry.types.Info,
    first: int = 20,
    after: str | None = None,
    status_filter: str | None = None,
) -> AnalysisConnection:
    if first < 1 or first > 100:
        raise ValueError("first parameter must be between 1 and 100")
    session: AsyncSession = info.context["db"]
    stmt = select(File)

    if after:
        try:
            decoded_id = decode_cursor(after)
            stmt = stmt.where(File.file_id > decoded_id)
        except Exception:
            pass

    stmt = stmt.order_by(File.file_id).limit(first + 1)
    result = await session.execute(stmt)
    files = list(result.scalars().all())

    has_next_page = len(files) > first
    if has_next_page:
        files = files[:first]

    edges = []
    for f in files:
        cursor = encode_cursor(f.file_id)
        edges.append(
            AnalysisEdge(
                node=AnalysisType(
                    id=strawberry.ID(f.file_id),
                    title=f.title or f.file_name,
                    created_at=f.first_processed_at or datetime.now(timezone.utc),
                    status="COMPLETE",
                    source_language=f.file_format or "tr",
                ),
                cursor=cursor,
            )
        )

    start_cursor = edges[0].cursor if edges else None
    end_cursor = edges[-1].cursor if edges else None

    # Count query
    count_stmt = select(func.count(File.file_id))
    count_result = await session.execute(count_stmt)
    total_count = count_result.scalar() or 0

    return AnalysisConnection(
        edges=edges,
        page_info=PageInfo(
            has_next_page=has_next_page,
            has_previous_page=bool(after),
            start_cursor=start_cursor,
            end_cursor=end_cursor,
        ),
        total_count=total_count,
    )


async def resolve_create_analysis(
    info: strawberry.types.Info, input: CreateAnalysisInput
) -> AnalysisType:
    input.validate()
    session: AsyncSession = info.context["db"]
    file_id = f"file-{uuid4().hex[:8]}"
    created_time = datetime.now(timezone.utc)

    db_file = File(
        file_id=file_id,
        file_name=input.title,
        title=input.title,
        idempotency_key=f"graphql-{file_id}",
        file_format=input.source_language,
        first_processed_at=created_time,
    )
    session.add(db_file)

    # Split text into sentences and create mock segments and sentences
    raw_sentences = [s.strip() for s in input.source_text.split(".") if s.strip()]
    if raw_sentences:
        seg_id = f"seg-{uuid4().hex[:8]}"
        db_segment = Segment(
            seg_id=seg_id,
            file_id=file_id,
            speaker_name="System",
            text=input.source_text,
            word_count=len(input.source_text.split()),
            sentence_count=len(raw_sentences),
            risk_score=0,
        )
        session.add(db_segment)

        for idx, text in enumerate(raw_sentences, start=1):
            sent_id = f"sent-{uuid4().hex[:8]}"
            db_sentence = Sentence(
                sent_id=sent_id,
                seg_id=seg_id,
                file_id=file_id,
                speaker_name="System",
                text=text,
                word_count=len(text.split()),
                sent_order=idx,
                vader_compound=0.0,
                power_level=0,
            )
            session.add(db_sentence)

    await session.commit()

    return AnalysisType(
        id=strawberry.ID(file_id),
        title=input.title,
        created_at=created_time,
        status="COMPLETE",
        source_language=input.source_language,
    )


async def resolve_submit_verdict(
    info: strawberry.types.Info,
    sentence_id: strawberry.ID,
    verdict: str,
    notes: str | None = None,
) -> SentenceType:
    if verdict not in {"CONFIRMED_PASS", "CONFIRMED_FAIL", "CORRECTED"}:
        raise ValueError(
            "verdict must be one of: CONFIRMED_PASS, CONFIRMED_FAIL, CORRECTED"
        )
    session: AsyncSession = info.context["db"]
    stmt = select(Sentence).where(Sentence.sent_id == str(sentence_id))
    result = await session.execute(stmt)
    s = result.scalar_one_or_none()
    if not s:
        raise ValueError(f"Sentence not found: {sentence_id}")

    s.logic_result = verdict

    queue_stmt = select(HumanReviewQueue).where(
        HumanReviewQueue.sent_id == str(sentence_id)
    )
    queue_result = await session.execute(queue_stmt)
    entry = queue_result.scalar_one_or_none()
    if entry:
        entry.status = verdict
        entry.reviewer_notes = notes

    await session.commit()

    return SentenceType(
        id=strawberry.ID(s.sent_id),
        sentence_index=s.sent_order or 0,
        text=s.text or "",
        risk_score=float(s.risk_score or 0.0),
        sentiment_score=s.vader_compound or 0.0,
        power_level=float(s.power_level or 0.0),
        uncertainty_score=getattr(s, "uncertainty_score", 0.0),
    )
