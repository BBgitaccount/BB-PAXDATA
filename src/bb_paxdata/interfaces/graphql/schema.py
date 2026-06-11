# src/bb_paxdata/interfaces/graphql/schema.py
from __future__ import annotations

from collections.abc import AsyncGenerator

import strawberry
from bb_paxdata.interfaces.graphql.resolvers import (
    resolve_analyses_connection,
    resolve_analysis,
    resolve_create_analysis,
    resolve_submit_verdict,
)
from bb_paxdata.interfaces.graphql.types import (
    AnalysisConnection,
    AnalysisType,
    CreateAnalysisInput,
    SentenceType,
)
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter


@strawberry.type
class Query:
    @strawberry.field
    async def analysis(
        self, info: strawberry.types.Info, id: strawberry.ID
    ) -> AnalysisType | None:
        return await resolve_analysis(info, id)

    @strawberry.field
    async def analyses(
        self,
        info: strawberry.types.Info,
        first: int = 20,
        after: str | None = None,
        status_filter: str | None = None,
    ) -> AnalysisConnection:
        """Relay-style cursor pagination ile analiz listesi döner."""
        return await resolve_analyses_connection(info, first, after, status_filter)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_analysis(
        self,
        info: strawberry.types.Info,
        input: CreateAnalysisInput,
    ) -> AnalysisType:
        return await resolve_create_analysis(info, input)

    @strawberry.mutation
    async def submit_verdict(
        self,
        info: strawberry.types.Info,
        sentence_id: strawberry.ID,
        verdict: str,
        notes: str | None = None,
    ) -> SentenceType:
        """HITL karar giriş endpoint'i."""
        return await resolve_submit_verdict(info, sentence_id, verdict, notes)


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def analysis_status_changed(
        self,
        info: strawberry.types.Info,
        analysis_id: strawberry.ID,
    ) -> AsyncGenerator[AnalysisType, None]:
        """Belirtilen analiz tamamlanana veya hata durumuna girene dek status yayınlar."""
        pubsub = info.context["redis_pubsub"]
        channel = f"analysis:{analysis_id}:status"
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    res = await resolve_analysis(info, analysis_id)
                    if res is not None:
                        yield res
        finally:
            await pubsub.unsubscribe(channel)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        # Kötü niyetli nested query saldırısını engeller
        lambda: QueryDepthLimiter(max_depth=10),
        # Karmaşık sorguların kaynak tüketimini sınırlar
        lambda: MaxAliasesLimiter(max_alias_count=15),
    ],
)
