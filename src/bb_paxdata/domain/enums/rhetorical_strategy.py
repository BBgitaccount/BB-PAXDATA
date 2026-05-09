from enum import Enum


class RhetoricalStrategy(str, Enum):
    APPEAL_TO_AUTHORITY = "appeal_to_authority"
    FALSE_EQUIVALENCE = "false_equivalence"
    EMOTIONAL_APPEAL = "emotional_appeal"
    SCAPEGOATING = "scapegoating"
    SOLIDARITY = "solidarity"
    THREAT_SIGNALING = "threat_signaling"
    DEFLECTION = "deflection"
    REFRAMING = "reframing"
    NONE = "none"
