from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from sqlalchemy import select

from bb_paxdata.infrastructure.db.models import File
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class FileRepository(BaseRepository[File]):
    """Async repository for File ORM model with Meilisearch support."""

    model_class = File

    async def get(self, file_id: str) -> File | None:
        """Get a file by ID."""
        return await self.get_by_id(file_id)

    async def add(self, entity: Any) -> File:
        """Add a file (supports domain model or ORM model)."""
        from bb_paxdata.application.domain.models.transcript import Transcript

        if isinstance(entity, Transcript):
            orm = File.from_domain(entity)
        else:
            orm = entity
        return await super().add(orm)

    async def search_meilisearch(
        self,
        query: str,
        panel_number: int | None = None,
        inferred_theme: str | None = None,
        limit: int = 20,
    ) -> list[File]:
        """Full-text search over files using Meilisearch."""
        try:
            from bb_paxdata.infrastructure.search.meilisearch_client import (
                search_files,
            )

            filters = []
            if panel_number:
                filters.append(f"panel_number = {panel_number}")
            if inferred_theme:
                filters.append(f"inferred_theme = '{inferred_theme}'")

            filter_str = " AND ".join(filters) if filters else None

            result = await search_files(
                query=query,
                filters=filter_str,
                limit=limit,
            )

            hits = result.get("hits", [])
            file_ids = [hit["file_id"] for hit in hits]

            # Fetch full File objects from database
            stmt = select(File).where(File.file_id.in_(file_ids))
            db_result = await self._session.execute(stmt)
            files = db_result.scalars().all()

            # Return in the same order as Meilisearch results
            file_dict = {f.file_id: f for f in files}
            return [file_dict[fid] for fid in file_ids if fid in file_dict]

        except Exception as e:
            logger.warning(
                "meilisearch_search_failed",
                query=query[:100],
                error=str(e),
            )
            # Fallback to SQL LIKE search
            stmt = select(File).where(
                File.file_name.ilike(f"%{query}%") | File.title.ilike(f"%{query}%")
            )
            if panel_number:
                stmt = stmt.where(File.panel_number == panel_number)
            if inferred_theme:
                stmt = stmt.where(File.inferred_theme == inferred_theme)
            stmt = stmt.limit(limit)

            result = await self._session.execute(stmt)
            return result.scalars().all()  # type: ignore[no-any-return]

    async def index_to_meilisearch(self, files: list[File]) -> None:
        """Index files to Meilisearch for full-text search."""
        try:
            from bb_paxdata.infrastructure.search.meilisearch_client import (
                index_files,
            )

            documents = []
            for file in files:
                documents.append(
                    {
                        "file_id": file.file_id,
                        "file_name": file.file_name,
                        "title": file.title,
                        "inferred_theme": file.inferred_theme,
                        "panel_number": file.panel_number,
                        "date_str": file.date_str,
                        "n_segments": file.n_segments,
                        "n_sentences": file.n_sentences,
                        "total_words": file.total_words,
                    }
                )

            await index_files(documents)
            logger.info(
                "files_indexed_to_meilisearch",
                count=len(files),
            )
        except Exception as e:
            logger.warning(
                "files_indexed_to_meilisearch_failed",
                error=str(e),
            )

    async def get_by_panel_number(self, panel_number: int) -> File | None:
        """Get a file by panel number."""
        stmt = select(File).where(File.panel_number == panel_number)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_theme(self, inferred_theme: str) -> Sequence[File]:
        """Get files by inferred theme."""
        stmt = select(File).where(File.inferred_theme == inferred_theme)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_recent(self, limit: int = 20) -> Sequence[File]:
        """Get most recently processed files."""
        stmt = (
            select(File)
            .order_by(File.last_processed_at.desc().nullsfirst())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]
