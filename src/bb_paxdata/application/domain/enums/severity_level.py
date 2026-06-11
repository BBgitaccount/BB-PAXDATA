from __future__ import annotations

from enum import StrEnum


class SeverityLevel(StrEnum):
    """Canonical ordinal severity scale used across BB-PAXDATA.

    Enums that share this exact LOW/MEDIUM/HIGH/CRITICAL schema with lowercase
    string values are defined as type aliases of this class. This is the single
    source of truth for severity ordering.

    Enums NOT aliased here (require a separate migration or have extra values):
      - AnomalySeverity: uppercase string values ("LOW", "HIGH") — DB: drift_events.severity
      - FutureRiskTier:  uppercase + NOT_ANALYZED extra value
      - RiskLevel:       lowercase but includes NONE="none"

    References:
        - DEAD-10 refactor: Copeland taxonomy enum consolidation.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
