"""Event payload upcaster registry for schema versioning and backward compatibility."""

from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Type definition for upcasting function: takes a payload dict, returns new payload dict
UpcasterFunc = Callable[[dict[str, Any]], dict[str, Any]]


class EventUpcasterRegistry:
    """Registry to manage and run event payload upcasters for consecutive schema versions."""

    def __init__(self) -> None:
        # Maps event_type -> list of upcasters.
        # Index i represents the transition from version (i + 1) to (i + 2).
        self._upcasters: dict[str, list[UpcasterFunc]] = {}
        # Maps event_type -> latest known schema version (default to 1)
        self._latest_versions: dict[str, int] = {}

    def register_upcaster(
        self,
        event_type: str,
        from_version: int,
        to_version: int,
        upcaster_fn: UpcasterFunc,
    ) -> None:
        """Register an upcasting function for a specific event type and version transition.

        The transition must be consecutive (from_version + 1 == to_version).
        """
        if from_version + 1 != to_version:
            raise ValueError(
                f"Upcaster must target consecutive versions. Got: {from_version} -> {to_version}"
            )
        if from_version < 1:
            raise ValueError(f"from_version must be >= 1. Got: {from_version}")

        self._upcasters.setdefault(event_type, [])
        upcaster_list = self._upcasters[event_type]

        # Pad the list with None values if we register out of order
        while len(upcaster_list) < from_version:
            upcaster_list.append(None)

        upcaster_list[from_version - 1] = upcaster_fn

        # Track the latest version registered
        current_latest = self._latest_versions.get(event_type, 1)
        self._latest_versions[event_type] = max(current_latest, to_version)

        logger.info(
            "Registered upcaster",
            event_type=event_type,
            from_version=from_version,
            to_version=to_version,
        )

    def get_latest_version(self, event_type: str) -> int:
        """Return the latest version registered for the given event type. Default is 1."""
        return self._latest_versions.get(event_type, 1)

    def upcast(
        self,
        event_type: str,
        payload: dict[str, Any],
        current_version: int,
    ) -> tuple[dict[str, Any], int]:
        """Progressively upcasts a payload from its current version to the latest version.

        Returns a tuple of (upcasted_payload, final_version).
        """
        latest_version = self.get_latest_version(event_type)

        if current_version >= latest_version:
            return payload, current_version

        upcaster_list = self._upcasters.get(event_type, [])
        upcasted_payload = dict(payload)

        v = current_version
        while v < latest_version:
            idx = v - 1
            if idx < len(upcaster_list) and upcaster_list[idx] is not None:
                upcast_fn = upcaster_list[idx]
                try:
                    upcasted_payload = upcast_fn(upcasted_payload)
                except Exception as e:
                    logger.error(
                        "Error during event upcasting",
                        event_type=event_type,
                        from_version=v,
                        to_version=v + 1,
                        error=str(e),
                    )
                    # Stop upcasting on failure and return what we have so far
                    return upcasted_payload, v
            v += 1

        return upcasted_payload, latest_version


# Global singleton instance
global_upcaster_registry = EventUpcasterRegistry()


# --- Default Upcasters Registration ---


def upcast_analysis_completed_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Upcasts AnalysisCompleted event payload from v1 to v2.

    Standardizes 'sentiment_score' to 'ai_sentiment_score' and defaults 'coherence_score'.
    """
    new_payload = dict(payload)
    if "sentiment_score" in new_payload:
        new_payload["ai_sentiment_score"] = new_payload.pop("sentiment_score")
    if "coherence_score" not in new_payload:
        new_payload["coherence_score"] = 1.0
    return new_payload


# Register default upcasters
global_upcaster_registry.register_upcaster(
    event_type="AnalysisCompleted",
    from_version=1,
    to_version=2,
    upcaster_fn=upcast_analysis_completed_v1_to_v2,
)
