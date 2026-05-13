from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from bb_paxdata.config.settings import Settings
from bb_paxdata.domain.entities.legacy import LegacyAnalyticIndex, LegacyTranscript

logger = structlog.get_logger()


class LegacyReader(Protocol):
    """Legacy DB reading interface. Infrastructure independent."""

    async def fetch_transcripts(
        self, batch_size: int, offset: int
    ) -> list[LegacyTranscript]: ...
    async def fetch_analytics(
        self, transcript_ids: list[int]
    ) -> list[LegacyAnalyticIndex]: ...
    async def count_transcripts(self) -> int: ...
    async def close(self) -> None: ...


class ModernWriter(Protocol):
    """Modern DB writing interface. Infrastructure independent."""

    async def upsert_transcripts(
        self, session: Any, items: list[LegacyTranscript]
    ) -> int: ...
    async def upsert_analytics(
        self, session: Any, items: list[LegacyAnalyticIndex]
    ) -> int: ...


@dataclass(frozen=True)
class MigrationResult:
    total_source_rows: int
    migrated_rows: int
    failed_rows: int
    retried_rows: int
    duration_sec: float
    errors: list[str] = field(default_factory=list)
    status: str = "completed"

    @property
    def success_rate(self) -> float:
        if self.total_source_rows == 0:
            return 100.0
        return round((self.migrated_rows / self.total_source_rows) * 100, 2)


class MigrationUseCase:
    """
    Legacy -> Modern DB migration orchestrator.

    Flow:
    1. Get source row count
    2. Read in batches
    3. Bulk fetch analytics for each batch (prevent N+1)
    4. Write to new DB within transaction
    5. Failure -> individual retry
    6. Return MigrationResult
    """

    def __init__(
        self,
        settings: Settings,
        legacy_reader: LegacyReader,
        modern_writer: ModernWriter,
        session_factory: Any,
    ) -> None:
        self._settings = settings
        self._reader = legacy_reader
        self._writer = modern_writer
        self._session_factory = session_factory
        self._log = logger.bind(use_case="migration", version=settings.version)

    async def execute(self, dry_run: bool = False) -> MigrationResult:
        start = time.monotonic()
        errors: list[str] = []
        migrated = 0
        failed = 0
        retried = 0

        total = await self._reader.count_transcripts()
        self._log.info(
            "migration_started",
            total=total,
            batch_size=self._settings.batch_size,
            dry_run=dry_run,
        )

        if total == 0:
            return MigrationResult(
                0, 0, 0, 0, time.monotonic() - start, ["Source DB empty"], "completed"
            )

        for offset in range(0, total, self._settings.batch_size):
            batch: list[LegacyTranscript] = []
            try:
                batch = await self._reader.fetch_transcripts(
                    batch_size=self._settings.batch_size,
                    offset=offset,
                )
                if not batch:
                    break

                # Prevent N+1 by fetching analytics in a single query
                t_ids = [t.id for t in batch]
                analytics = await self._reader.fetch_analytics(t_ids)
                analytics_map = {a.transcript_id: a for a in analytics}

                if not dry_run:
                    async with self._session_factory() as session:
                        async with session.begin():
                            written = await self._writer.upsert_transcripts(
                                session, batch
                            )
                            await self._writer.upsert_analytics(
                                session,
                                list(analytics_map.values()),
                            )
                            migrated += written
                else:
                    # Dry-run: count only
                    migrated += len(batch)

                self._log.info(
                    "batch_ok",
                    offset=offset,
                    count=len(batch),
                    progress=f"{min(offset + len(batch), total)}/{total}",
                )

            except Exception as exc:
                err_msg = f"offset={offset} | {type(exc).__name__}: {exc}"
                errors.append(err_msg)
                self._log.warning("batch_failed", offset=offset, error=str(exc))

                # Individual retry: try each row in the batch separately
                retry_result = await self._retry_singles(batch, dry_run)
                migrated += retry_result["ok"]
                failed += retry_result["fail"]
                retried += retry_result["ok"] + retry_result["fail"]
                errors.extend(retry_result["errors"])

        return MigrationResult(
            total_source_rows=total,
            migrated_rows=migrated,
            failed_rows=failed,
            retried_rows=retried,
            duration_sec=round(time.monotonic() - start, 3),
            errors=errors,
            status="partial" if failed > 0 else "completed",
        )

    async def _retry_singles(
        self,
        batch: list[LegacyTranscript],
        dry_run: bool,
    ) -> dict[str, Any]:
        ok = 0
        fail = 0
        errors: list[str] = []

        for tx in batch:
            try:
                if not dry_run:
                    # Minimal analytics for each row (if exists)
                    analytics = await self._reader.fetch_analytics([tx.id])
                    async with self._session_factory() as session:
                        async with session.begin():
                            await self._writer.upsert_transcripts(session, [tx])
                            if analytics:
                                await self._writer.upsert_analytics(session, analytics)
                ok += 1
                self._log.debug("single_retry_ok", transcript_id=tx.id)
            except Exception as exc:
                fail += 1
                errors.append(f"single_retry_fail id={tx.id}: {exc}")
                self._log.error(
                    "single_retry_fail", transcript_id=tx.id, error=str(exc)
                )

        return {"ok": ok, "fail": fail, "errors": errors}
