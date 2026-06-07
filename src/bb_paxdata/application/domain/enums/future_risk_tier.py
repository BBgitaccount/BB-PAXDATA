from enum import Enum


class FutureRiskTier(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_ANALYZED = "NOT_ANALYZED"
