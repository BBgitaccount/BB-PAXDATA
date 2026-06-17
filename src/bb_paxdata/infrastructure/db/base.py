from typing import Any

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Application-wide ORM base."""

    # Transient list to store domain events associated with this ORM instance.
    _domain_events: list[dict[str, Any]]

    def record_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        correlation_id: str | None = None,
        aggregate_id: str | None = None,
        event_version: int | None = None,
    ) -> None:
        """Record an event on this ORM instance."""
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []

        pk_val = aggregate_id
        if pk_val is None:
            from sqlalchemy import inspect

            mapper = inspect(self.__class__)
            pk_val = "unknown"
            if mapper.primary_key:
                pk_attr = mapper.primary_key[0].name
                pk_val = str(getattr(self, pk_attr, "unknown"))

        corr_id = correlation_id
        if corr_id is None:
            from bb_paxdata.application.domain.utils.context import get_correlation_id

            corr_id = get_correlation_id()

        from bb_paxdata.infrastructure.events.upcaster import global_upcaster_registry

        evt_version = event_version or global_upcaster_registry.get_latest_version(
            event_type
        )

        self._domain_events.append(
            {
                "aggregate_type": self.__class__.__name__,
                "aggregate_id": pk_val,
                "event_type": event_type,
                "event_version": evt_version,
                "payload": payload,
                "actor_id": actor_id,
                "correlation_id": corr_id,
            }
        )

    def clear_events(self) -> None:
        """Clear all events registered on this instance."""
        if hasattr(self, "_domain_events") and self._domain_events:
            self._domain_events.clear()

    def get_events(self) -> list[dict[str, Any]]:
        """Get all events registered on this instance."""
        return getattr(self, "_domain_events", None) or []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # If the subclass has defined a from_domain method, wrap it to transfer events
        if "from_domain" in cls.__dict__:
            original_from_domain = cls.from_domain

            def wrapped_from_domain(cls_, model, *args, **kwargs_):
                orm_instance = original_from_domain(model, *args, **kwargs_)
                # Transfer events from domain model to ORM model
                if hasattr(model, "get_events"):
                    events = model.get_events()
                    if events:
                        if not hasattr(orm_instance, "_domain_events"):
                            orm_instance._domain_events = []
                        orm_instance._domain_events.extend(events)
                        model.clear_events()
                return orm_instance

            cls.from_domain = classmethod(wrapped_from_domain)
