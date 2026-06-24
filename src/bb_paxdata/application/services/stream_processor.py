"""StreamProcessor service for managing priority-based result streaming with backpressure control."""

import asyncio
import heapq
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Priority(IntEnum):
    """Priority levels for streaming results."""

    RISK = 1  # Highest priority - risk-related results
    SENTIMENT = 2  # Medium priority - sentiment analysis
    TOPIC = 3  # Lower priority - topic modeling
    GENERAL = 4  # Lowest priority - general results


@dataclass(order=True)
class StreamItem:
    """Priority queue item for streaming results."""

    priority: int
    timestamp: float = field(compare=False)
    session_id: str = field(compare=False)
    data: dict[str, Any] = field(compare=False)
    item_id: str = field(compare=False)

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


class StreamProcessor:
    """Manages priority-based streaming with backpressure and partial aggregation."""

    def __init__(
        self,
        max_queue_size: int = 1000,
        backpressure_threshold: float = 0.8,
        aggregation_window: int = 10,
    ):
        self.max_queue_size = max_queue_size
        self.backpressure_threshold = backpressure_threshold
        self.aggregation_window = aggregation_window

        # Priority queue for ordered processing
        self._queue: list[StreamItem] = []
        self._queue_lock = asyncio.Lock()

        # Session-specific partial aggregation buffers
        self._aggregation_buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._aggregation_lock = asyncio.Lock()

        # Metrics
        self._total_processed = 0
        self._total_dropped = 0
        self._queue_size_history: list[tuple[float, int]] = []
        self._session_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "items_processed": 0,
                "items_dropped": 0,
                "start_time": time.time(),
            }
        )

    async def enqueue(
        self,
        session_id: str,
        data: dict[str, Any],
        priority: Priority = Priority.GENERAL,
        item_id: str | None = None,
    ) -> bool:
        """Enqueue an item for streaming with priority.

        Returns True if enqueued successfully, False if dropped due to backpressure.
        """
        async with self._queue_lock:
            current_size = len(self._queue)

            # Check backpressure
            if current_size >= self.max_queue_size:
                self._total_dropped += 1
                self._session_metrics[session_id]["items_dropped"] += 1
                logger.warning(
                    "stream_processor_backpressure_drop",
                    session_id=session_id,
                    queue_size=current_size,
                    max_size=self.max_queue_size,
                )
                return False

            # Apply backpressure threshold
            if current_size / self.max_queue_size >= self.backpressure_threshold:
                # Only accept high-priority items when under backpressure
                if priority > Priority.RISK:
                    self._total_dropped += 1
                    self._session_metrics[session_id]["items_dropped"] += 1
                    logger.warning(
                        "stream_processor_backpressure_priority_drop",
                        session_id=session_id,
                        priority=priority.name,
                        queue_size=current_size,
                    )
                    return False

            # Enqueue item
            item = StreamItem(
                priority=priority.value,
                session_id=session_id,
                data=data,
                item_id=item_id or f"{session_id}-{time.time()}",
            )
            heapq.heappush(self._queue, item)

            # Record queue size history
            self._queue_size_history.append((time.time(), len(self._queue)))
            if len(self._queue_size_history) > 1000:
                self._queue_size_history.pop(0)

            logger.debug(
                "stream_processor_enqueue",
                session_id=session_id,
                priority=priority.name,
                queue_size=len(self._queue),
            )
            return True

    async def dequeue(self) -> StreamItem | None:
        """Dequeue the highest-priority item."""
        async with self._queue_lock:
            if not self._queue:
                return None

            item = heapq.heappop(self._queue)
            self._total_processed += 1
            self._session_metrics[item.session_id]["items_processed"] += 1

            logger.debug(
                "stream_processor_dequeue",
                session_id=item.session_id,
                priority=item.priority,
                queue_size=len(self._queue),
            )
            return item

    async def get_queue_size(self) -> int:
        """Get current queue size."""
        async with self._queue_lock:
            return len(self._queue)

    async def get_backpressure_status(self) -> dict[str, Any]:
        """Get backpressure status and metrics."""
        async with self._queue_lock:
            current_size = len(self._queue)
            utilization = (
                current_size / self.max_queue_size if self.max_queue_size > 0 else 0
            )

            return {
                "queue_size": current_size,
                "max_queue_size": self.max_queue_size,
                "utilization": utilization,
                "backpressure_active": utilization >= self.backpressure_threshold,
                "total_processed": self._total_processed,
                "total_dropped": self._total_dropped,
                "active_sessions": len(self._session_metrics),
            }

    async def add_to_aggregation_buffer(
        self, session_id: str, data: dict[str, Any]
    ) -> None:
        """Add data to session's partial aggregation buffer."""
        async with self._aggregation_lock:
            self._aggregation_buffers[session_id].append(data)

            # Trim buffer if too large
            if len(self._aggregation_buffers[session_id]) > self.aggregation_window * 2:
                self._aggregation_buffers[session_id] = self._aggregation_buffers[
                    session_id
                ][-self.aggregation_window :]

    async def get_aggregated_results(
        self, session_id: str, flush: bool = False
    ) -> list[dict[str, Any]]:
        """Get aggregated partial results for a session."""
        async with self._aggregation_lock:
            buffer = self._aggregation_buffers.get(session_id, [])

            if flush:
                self._aggregation_buffers[session_id] = []
                return buffer

            # Return last N items for partial aggregation
            return buffer[-self.aggregation_window :] if buffer else []

    async def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Get metrics for a specific session."""
        return dict(self._session_metrics.get(session_id, {}))

    async def get_all_session_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all active sessions."""
        return {k: dict(v) for k, v in self._session_metrics.items()}

    async def clear_session(self, session_id: str) -> None:
        """Clear data for a specific session."""
        async with self._aggregation_lock:
            if session_id in self._aggregation_buffers:
                del self._aggregation_buffers[session_id]

        if session_id in self._session_metrics:
            del self._session_metrics[session_id]

    async def get_queue_size_history(self) -> list[tuple[float, int]]:
        """Get historical queue size data for monitoring."""
        async with self._queue_lock:
            return list(self._queue_size_history)


# Global stream processor instance
_stream_processor: StreamProcessor | None = None


def get_stream_processor() -> StreamProcessor:
    """Get or create the global StreamProcessor instance."""
    global _stream_processor
    if _stream_processor is None:
        _stream_processor = StreamProcessor()
    return _stream_processor
