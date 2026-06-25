from enum import StrEnum


# TODO(DEAD-10): FutureRiskTier uses UPPERCASE values and includes NOT_ANALYZED,
# making it incompatible with SeverityLevel. Normalize to lowercase and drop or
# map NOT_ANALYZED before aliasing.
class FutureRiskTier(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_ANALYZED = "NOT_ANALYZED"
