# src/bb_paxdata/interfaces/graphql/types.py
from __future__ import annotations

import base64
from datetime import datetime

import strawberry


def encode_cursor(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def decode_cursor(cursor: str) -> str:
    return base64.b64decode(cursor.encode()).decode()


@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None
    end_cursor: str | None


@strawberry.type
class SentenceType:
    id: strawberry.ID
    sentence_index: int
    text: str
    risk_score: float
    sentiment_score: float
    power_level: float
    uncertainty_score: float


@strawberry.type
class SegmentType:
    id: strawberry.ID
    segment_index: int
    summary: str
    risk_level: str

    @strawberry.field
    async def sentences(self, info: strawberry.types.Info) -> list[SentenceType]:
        loader = info.context["sentence_loader"]
        return await loader.load(str(self.id))


@strawberry.type
class AnalysisType:
    id: strawberry.ID
    title: str
    created_at: datetime
    status: str
    source_language: str

    @strawberry.field
    async def segments(self, info: strawberry.types.Info) -> list[SegmentType]:
        loader = info.context["segment_loader"]
        return await loader.load(str(self.id))


@strawberry.type
class AnalysisEdge:
    node: AnalysisType
    cursor: str


@strawberry.type
class AnalysisConnection:
    edges: list[AnalysisEdge]
    page_info: PageInfo
    total_count: int


@strawberry.input
class CreateAnalysisInput:
    title: str
    source_text: str
    source_language: str = "tr"
    pipeline_config_id: str | None = None
