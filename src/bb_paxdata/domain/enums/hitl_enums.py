"""HITL Formula Validation Dashboard enum definitions."""

from enum import Enum


class HumanVerdict(str, Enum):
    """Possible human review verdicts for formula validation logs."""

    CONFIRMED_FAIL = "CONFIRMED_FAIL"
    CONFIRMED_PASS = "CONFIRMED_PASS"
    CORRECTED = "CORRECTED"


class AuditActionType(str, Enum):
    """Types of actions recorded in the formula validation audit trail."""

    REVIEW_STARTED = "REVIEW_STARTED"
    VERDICT_SUBMITTED = "VERDICT_SUBMITTED"
    CORRECTED = "CORRECTED"
    ROLLED_BACK = "ROLLED_BACK"
    ESCALATED = "ESCALATED"


class PermissionLevel(str, Enum):
    """RBAC permission levels for reviewer assignments."""

    VIEW = "view"
    VERDICT = "verdict"
    CORRECT = "correct"
    ESCALATE = "escalate"
    ADMIN = "admin"


class ReviewerScopeType(str, Enum):
    """Types of scope a reviewer assignment can cover."""

    FORMULA = "formula"
    SPEAKER = "speaker"
    PANEL = "panel"
    COUNTRY = "country"
    GLOBAL = "global"


class ConfidenceLevel(str, Enum):
    """Confidence level for HITL review decisions."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DataQualityFlag(str, Enum):
    """Flags for data quality issues that affect formula validation."""

    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class TriagePriority(str, Enum):
    """Auto-triage priority levels for formula FAIL queue."""

    NORMAL = "NORMAL"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    SOVEREIGN_PRIORITY = "SOVEREIGN_PRIORITY"
    CRITICAL = "CRITICAL"
