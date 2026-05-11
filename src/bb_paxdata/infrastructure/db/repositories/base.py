from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async base repository for ORM models."""

    model_class: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, record_id: Any) -> ModelT | None:
        """Get a single record by primary key."""
        from sqlalchemy import inspect

        pk_column = inspect(self.model_class).primary_key[0]
        stmt = select(self.model_class).where(pk_column == record_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int | None = None) -> Sequence[ModelT]:
        """Get all records, optionally limited."""
        stmt = select(self.model_class)
        if limit:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, entity: ModelT) -> ModelT:
        """Add a new entity and return it."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def add_many(self, entities: list[Any]) -> None:
        """Add multiple entities in bulk."""
        for entity in entities:
            await self.add(entity)
        await self._session.flush()

    async def delete_by_id(self, record_id: Any) -> None:
        """Delete a record by primary key."""
        entity = await self.get_by_id(record_id)
        if entity:
            await self._session.delete(entity)
            await self._session.flush()

    async def exists(self, record_id: Any) -> bool:
        """Check if a record exists by primary key."""
        from sqlalchemy import inspect

        pk_column = inspect(self.model_class).primary_key[0]
        stmt = select(self.model_class).where(pk_column == record_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
