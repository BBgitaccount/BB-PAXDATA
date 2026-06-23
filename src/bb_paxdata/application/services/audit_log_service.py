"""Service for converting DomainEvents to AuditLogEntries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from bb_paxdata.application.domain.models.audit_log import AuditLogEntry


class AuditLogService:
    """Service for converting domain events to audit log entries."""

    @staticmethod
    def domain_event_to_audit_entry(
        event: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLogEntry:
        """
        Convert a domain event to an audit log entry.

        Args:
            event: Domain event dictionary with keys:
                - aggregate_type
                - aggregate_id
                - event_type
                - payload
                - actor_id
                - correlation_id
            ip_address: Optional IP address from request context
            user_agent: Optional user agent from request context

        Returns:
            AuditLogEntry instance
        """
        # Extract resource information from event
        aggregate_type = event.get("aggregate_type", "Unknown")
        aggregate_id = event.get("aggregate_id", "unknown")
        event_type = event.get("event_type", "UnknownAction")
        actor_id = event.get("actor_id", "system")
        correlation_id = event.get("correlation_id")
        payload = event.get("payload", {})

        # Determine action type from event type
        action = AuditLogService._map_event_to_action(event_type)

        # Extract before/after state from payload if available
        before_state = payload.get("before_state")
        after_state = payload.get("after_state")

        # If not explicitly provided, try to infer from payload
        if before_state is None and after_state is None:
            before_state, after_state = AuditLogService._infer_state_changes(
                payload, action
            )

        return AuditLogEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            action=action,
            resource_type=aggregate_type,
            resource_id=aggregate_id,
            before_state=before_state,
            after_state=after_state,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            hash_chain=None,  # Will be set by repository
        )

    @staticmethod
    def _map_event_to_action(event_type: str) -> str:
        """Map event type to audit action type."""
        event_type_lower = event_type.lower()

        # Common patterns
        if any(
            keyword in event_type_lower
            for keyword in ["created", "added", "inserted", "initialized"]
        ):
            return "CREATE"
        if any(
            keyword in event_type_lower
            for keyword in ["updated", "modified", "changed", "edited"]
        ):
            return "UPDATE"
        if any(keyword in event_type_lower for keyword in ["deleted", "removed"]):
            return "DELETE"
        if any(
            keyword in event_type_lower
            for keyword in ["completed", "finished", "done", "processed"]
        ):
            return "COMPLETE"
        if any(keyword in event_type_lower for keyword in ["started", "initiated"]):
            return "START"
        if any(keyword in event_type_lower for keyword in ["failed", "error"]):
            return "FAIL"
        if any(keyword in event_type_lower for keyword in ["approved", "accepted"]):
            return "APPROVE"
        if any(keyword in event_type_lower for keyword in ["rejected", "denied"]):
            return "REJECT"
        if any(keyword in event_type_lower for keyword in ["reviewed", "audited"]):
            return "REVIEW"

        # Default: use the event type itself
        return event_type.upper()

    @staticmethod
    def _infer_state_changes(
        payload: dict[str, Any], action: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """
        Infer before/after state from payload based on action type.

        Returns (before_state, after_state) tuple.
        """
        if action == "CREATE":
            return None, payload
        if action == "DELETE":
            return payload, None

        # For UPDATE and other actions, try to find explicit state fields
        if "old_value" in payload or "new_value" in payload:
            return payload.get("old_value"), payload.get("new_value")

        # If no explicit state, use the entire payload as after_state
        return None, payload
