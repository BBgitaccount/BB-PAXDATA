# src/bb_paxdata/interfaces/graphql/context.py
from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.session import get_db
from bb_paxdata.interfaces.api.dependencies import get_cache
from bb_paxdata.interfaces.graphql.loaders import SegmentLoader, SentenceLoader


async def get_graphql_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
) -> dict[str, Any]:
    """
    Her GraphQL request için temiz DataLoader instance'ları oluşturur.
    Loader'lar request-scoped'tır; request dışına sızmaz.
    """
    redis_client = await cache._get_client()
    return {
        "request": request,
        "db": db,
        "redis_pubsub": redis_client.pubsub(),
        "segment_loader": SegmentLoader(db),
        "sentence_loader": SentenceLoader(db),
    }
