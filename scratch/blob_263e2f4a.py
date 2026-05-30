import asyncio
import inspect
from typing import Any, Callable, Type, TypeVar

from ...domain.models.tui import BuildEvent
from ...domain.ports.event_bus import EventBusPort

E = TypeVar("E", bound=BuildEvent)


class AsyncEventBus(EventBusPort):
    """In-memory concrete implementation of EventBusPort using async callbacks."""

    def __init__(self) -> None:
        self._handlers: dict[Type[BuildEvent], list[Callable]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: BuildEvent) -> None:
        async with self._lock:
            # Match direct handlers and base-class handlers if registered
            handlers_to_run = []
            for event_cls, callbacks in self._handlers.items():
                if isinstance(event, event_cls):
                    handlers_to_run.extend(callbacks)

        if not handlers_to_run:
            return

        # Execute handlers concurrently
        tasks = []
        for handler in handlers_to_run:
            try:
                if inspect.iscoroutinefunction(handler):
                    tasks.append(asyncio.create_task(handler(event)))
                else:
                    handler(event)
            except Exception:
                pass

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def subscribe(
        self, event_type: Type[E], callback: Callable[[E], Any]
    ) -> None:
        async with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(callback)
