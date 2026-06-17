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

    def validate(self):
        if not self.title or len(self.title.strip()) < 1 or len(self.title) > 200:
            raise ValueError("title must be between 1 and 200 characters")
        if (
            not self.source_text
            or len(self.source_text.strip()) < 10
            or len(self.source_text) > 100000
        ):
            raise ValueError("source_text must be between 10 and 100,000 characters")
        import re

        if not re.match(r"^[a-z]{2}(-[A-Z]{2})?$", self.source_language):
            raise ValueError(
                "source_language must be ISO 639-1 language code (e.g. 'en', 'tr')"
            )
