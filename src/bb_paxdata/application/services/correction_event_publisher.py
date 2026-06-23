"""Correction Event Publisher service."""

from __future__ import annotations

from bb_paxdata.application.domain.models.correction_event import CorrectionEvent
from bb_paxdata.application.domain.ports.event_bus import EventBusPort


class CorrectionEventPublisher:
    """Publishes correction events to the event bus for Pattern Miner consumption."""

    def __init__(self, event_bus: EventBusPort) -> None:
        self._event_bus = event_bus

    async def publish_correction_created(self, event: CorrectionEvent) -> None:
        """
        Publish a correction event to the event bus.

        This triggers the Pattern Miner to analyze the new correction
        for systematic error patterns.
        """
        payload = {
            "event_id": event.id,
            "sentence_id": event.sentence_id,
            "field_corrected": event.field_corrected,
            "original_value": event.original_value,
            "corrected_value": event.corrected_value,
            "prompt_version": event.prompt_version,
            "ai_confidence": event.ai_confidence,
            "corrector_id": event.corrector_id,
            "timestamp": event.timestamp.isoformat(),
            "context_snapshot": event.context_snapshot,
            "delta": event.compute_delta(),
            "is_high_confidence_error": event.is_high_confidence_error(),
        }

        await self._event_bus.publish(
            channel="correction_events",
            event_type="CorrectionCreated",
            payload=payload,
        )
