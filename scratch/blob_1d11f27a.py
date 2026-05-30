import asyncio
import inspect
from datetime import datetime, timezone
from typing import Callable

from ...domain.models.tui import (
    BuildCancelledEvent,
    BuildEvent,
    BuildSnapshot,
    FileMetrics,
    FileProcessedEvent,
    SessionId,
    StageCompletedEvent,
    StageStartedEvent,
    StageStatus,
)
from ...domain.ports.state_store import StateStorePort


class MemoryStateStore(StateStorePort):
    """In-memory concrete implementation of StateStorePort."""

    def __init__(self, session_id: str, total_files: int) -> None:
        self._session_id = session_id
        self._started_at = datetime.now(timezone.utc)
        self._subscribers = []
        self._lock = asyncio.Lock()

        # Initial state setup
        initial_stages = {
            "Transcript Ingestion": StageStatus.PENDING,
            "Speaker Profiles": StageStatus.PENDING,
            "Country Statistics": StageStatus.PENDING,
            "Discourse Network": StageStatus.PENDING,
            "Bilateral Sentiments": StageStatus.PENDING,
        }

        self._snapshot = BuildSnapshot(
            session_id=SessionId(session_id),
            started_at=self._started_at,
            current_stage="Transcript Ingestion",
            stages=initial_stages,
            files=(),
            total_files=total_files,
            processed_files=0,
            skipped_files=0,
            error_files=0,
            total_words=0,
            total_sentences=0,
            throughput_wps=0.0,
            is_cancelled=False,
        )

    async def get_snapshot(self) -> BuildSnapshot:
        async with self._lock:
            return self._snapshot

    async def apply_event(self, event: BuildEvent) -> None:
        async with self._lock:
            snap = self._snapshot
            new_stages = dict(snap.stages)
            new_files = list(snap.files)
            current_stage = snap.current_stage
            processed_files = snap.processed_files
            skipped_files = snap.skipped_files
            error_files = snap.error_files
            total_words = snap.total_words
            total_sentences = snap.total_sentences
            is_cancelled = snap.is_cancelled

            if isinstance(event, FileProcessedEvent):
                new_files.append(
                    FileMetrics(
                        path=event.path,
                        words=event.words,
                        sentences=event.sentences,
                        processing_time_ms=event.processing_time_ms,
                        status=event.status,
                    )
                )
                if event.status == StageStatus.COMPLETED:
                    processed_files += 1
                elif event.status == StageStatus.CANCELLED:
                    skipped_files += 1  # count skips
                elif event.status == StageStatus.FAILED:
                    error_files += 1

                total_words += event.words
                total_sentences += event.sentences

            elif isinstance(event, StageStartedEvent):
                current_stage = event.stage_name
                new_stages[event.stage_name] = StageStatus.ACTIVE

            elif isinstance(event, StageCompletedEvent):
                new_stages[event.stage_name] = event.status

            elif isinstance(event, BuildCancelledEvent):
                is_cancelled = True
                for stage in new_stages:
                    if new_stages[stage] in (StageStatus.PENDING, StageStatus.ACTIVE):
                        new_stages[stage] = StageStatus.CANCELLED

            # Calculate throughput
            elapsed = (datetime.now(timezone.utc) - self._started_at).total_seconds()
            throughput = total_words / elapsed if elapsed > 0.5 else 0.0

            # Reconstruct immutable snapshot
            self._snapshot = BuildSnapshot(
                session_id=snap.session_id,
                started_at=snap.started_at,
                current_stage=current_stage,
                stages=new_stages,
                files=tuple(new_files),
                total_files=snap.total_files,
                processed_files=processed_files,
                skipped_files=skipped_files,
                error_files=error_files,
                total_words=total_words,
                total_sentences=total_sentences,
                throughput_wps=throughput,
                is_cancelled=is_cancelled,
            )

            # Notify subscribers
            await self._notify_subscribers()

    async def subscribe(self, callback: Callable[[BuildSnapshot], None]) -> None:
        async with self._lock:
            # We store the reference. If callback is a bound method, we can store it.
            self._subscribers.append(callback)
            # Instantly push current state to the subscriber
            snapshot = self._snapshot

        try:
            if inspect.iscoroutinefunction(callback):
                await callback(snapshot)
            else:
                callback(snapshot)
        except Exception:
            pass

    async def _notify_subscribers(self) -> None:
        snapshot = self._snapshot
        for sub in list(self._subscribers):
            try:
                if inspect.iscoroutinefunction(sub):
                    await sub(snapshot)
                else:
                    sub(snapshot)
            except Exception:
                # Remove stale subscribers if they raise errors (e.g. closed widgets)
                self._subscribers.remove(sub)
