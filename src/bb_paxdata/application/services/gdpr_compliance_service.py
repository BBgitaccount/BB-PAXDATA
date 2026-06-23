"""GDPR Article 30 compliance report service."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from bb_paxdata.application.domain.models.audit_log import AuditLogEntry


class GDPRComplianceService:
    """Service for generating GDPR Article 30 compliance reports."""

    @staticmethod
    def generate_article_30_report(
        entries: list[AuditLogEntry],
        report_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Generate a GDPR Article 30 compliance report from audit log entries.

        Article 30 requires records of processing activities including:
        - Purposes of processing
        - Categories of data subjects and personal data
        - Categories of recipients
        - Retention periods
        - Security measures

        Args:
            entries: List of audit log entries
            report_date: Date of the report (defaults to now)

        Returns:
            Dictionary containing the compliance report
        """
        if report_date is None:
            report_date = datetime.utcnow()

        # Analyze entries for compliance information
        resource_types = Counter(e.resource_type for e in entries)
        actions = Counter(e.action for e in entries)
        actors = Counter(e.actor_id for e in entries)

        # Group by resource type to understand data processing purposes
        processing_activities = GDPRComplianceService._analyze_processing_activities(
            entries
        )

        # Identify data subjects (actors)
        data_subjects = GDPRComplianceService._analyze_data_subjects(entries)

        # Identify recipients (who accessed the data)
        recipients = GDPRComplianceService._analyze_recipients(entries)

        # Security measures (from action types)
        security_measures = GDPRComplianceService._analyze_security_measures(entries)

        return {
            "report_metadata": {
                "report_date": report_date.isoformat(),
                "report_type": "GDPR Article 30 - Records of Processing Activities",
                "total_entries_analyzed": len(entries),
                "date_range": {
                    "start": (
                        min(e.timestamp for e in entries).isoformat()
                        if entries
                        else None
                    ),
                    "end": (
                        max(e.timestamp for e in entries).isoformat()
                        if entries
                        else None
                    ),
                },
            },
            "processing_activities": processing_activities,
            "data_subjects": data_subjects,
            "recipients": recipients,
            "security_measures": security_measures,
            "statistics": {
                "total_resource_types": len(resource_types),
                "total_actions": len(actions),
                "total_actors": len(actors),
                "most_common_resource_type": (
                    resource_types.most_common(1)[0] if resource_types else None
                ),
                "most_common_action": actions.most_common(1)[0] if actions else None,
            },
        }

    @staticmethod
    def _analyze_processing_activities(
        entries: list[AuditLogEntry],
    ) -> list[dict[str, Any]]:
        """Analyze processing activities by resource type."""
        activities = []

        # Group by resource type
        from collections import defaultdict

        by_resource = defaultdict(list)
        for entry in entries:
            by_resource[entry.resource_type].append(entry)

        for resource_type, resource_entries in by_resource.items():
            actions_count = Counter(e.action for e in resource_entries)
            actors = set(e.actor_id for e in resource_entries)

            # Determine purpose based on actions
            purposes = GDPRComplianceService._infer_purposes(actions_count.keys())

            activities.append(
                {
                    "resource_type": resource_type,
                    "purposes": purposes,
                    "actions_distribution": dict(actions_count),
                    "data_accessors": list(actors),
                    "total_operations": len(resource_entries),
                }
            )

        return activities

    @staticmethod
    def _analyze_data_subjects(entries: list[AuditLogEntry]) -> list[dict[str, Any]]:
        """Analyze data subjects (actors) and their data access patterns."""
        subjects = []

        # Group by actor
        from collections import defaultdict

        by_actor = defaultdict(list)
        for entry in entries:
            by_actor[entry.actor_id].append(entry)

        for actor_id, actor_entries in by_actor.items():
            resource_types = set(e.resource_type for e in actor_entries)
            actions = set(e.action for e in actor_entries)

            subjects.append(
                {
                    "actor_id": actor_id,
                    "resource_types_accessed": list(resource_types),
                    "actions_performed": list(actions),
                    "total_operations": len(actor_entries),
                    "first_activity": min(
                        e.timestamp for e in actor_entries
                    ).isoformat(),
                    "last_activity": max(
                        e.timestamp for e in actor_entries
                    ).isoformat(),
                }
            )

        # Sort by total operations (most active first)
        subjects.sort(key=lambda x: x["total_operations"], reverse=True)

        return subjects

    @staticmethod
    def _analyze_recipients(entries: list[AuditLogEntry]) -> list[dict[str, Any]]:
        """Analyze who received or accessed data."""
        recipients = []

        # Group by actor as recipient
        from collections import defaultdict

        by_actor = defaultdict(list)
        for entry in entries:
            by_actor[entry.actor_id].append(entry)

        for actor_id, actor_entries in by_actor.items():
            resource_types = set(e.resource_type for e in actor_entries)
            access_count = len(actor_entries)

            recipients.append(
                {
                    "recipient_id": actor_id,
                    "resource_types_received": list(resource_types),
                    "access_count": access_count,
                }
            )

        # Sort by access count
        recipients.sort(key=lambda x: x["access_count"], reverse=True)

        return recipients

    @staticmethod
    def _analyze_security_measures(entries: list[AuditLogEntry]) -> dict[str, Any]:
        """Analyze security measures based on audit log patterns."""
        actions = [e.action for e in entries]

        # Detect security-related actions
        security_actions = {
            "AUTHENTICATION": "a" in actions,
            "AUTHORIZATION": "AUTHORIZE" in actions or "APPROVE" in actions,
            "AUDIT_LOGGING": "AUDIT" in actions or "REVIEW" in actions,
            "ACCESS_CONTROL": "ACCESS" in actions or "PERMISSION" in actions,
            "DATA_ENCRYPTION": "ENCRYPT" in actions,
        }

        # Check for IP address logging (security measure)
        has_ip_logging = any(e.ip_address for e in entries)

        # Check for user agent logging
        has_ua_logging = any(e.user_agent for e in entries)

        # Check for correlation ID (traceability)
        has_correlation = any(e.correlation_id for e in entries)

        return {
            "implemented_measures": {
                "authentication": security_actions["AUTHENTICATION"],
                "authorization": security_actions["AUTHORIZATION"],
                "audit_logging": security_actions["AUDIT_LOGGING"],
                "access_control": security_actions["ACCESS_CONTROL"],
                "ip_address_logging": has_ip_logging,
                "user_agent_logging": has_ua_logging,
                "traceability": has_correlation,
            },
            "hash_chain_verification": True,  # Implemented in audit log
        }

    @staticmethod
    def _infer_purposes(actions: set[str]) -> list[str]:
        """Infer processing purposes from action types."""
        purposes = []

        action_str = " ".join(actions).lower()

        if any(a in action_str for a in ["create", "add", "insert"]):
            purposes.append("Data Collection")
        if any(a in action_str for a in ["update", "modify", "edit"]):
            purposes.append("Data Maintenance")
        if any(a in action_str for a in ["delete", "remove"]):
            purposes.append("Data Deletion")
        if any(a in action_str for a in ["read", "get", "fetch", "retrieve"]):
            purposes.append("Data Access")
        if any(a in action_str for a in ["analyze", "process", "complete"]):
            purposes.append("Data Processing")
        if any(a in action_str for a in ["export", "download"]):
            purposes.append("Data Transfer")
        if any(a in action_str for a in ["audit", "review", "approve"]):
            purposes.append("Compliance Monitoring")

        return purposes if purposes else ["General Data Processing"]
