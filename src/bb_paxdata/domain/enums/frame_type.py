from enum import Enum


class FrameType(str, Enum):
    CONFLICT_FRAME = "conflict_frame"
    SECURITY_FRAME = "security_frame"
    HUMANITARIAN_FRAME = "humanitarian_frame"
    LEGAL_FRAME = "legal_frame"
    NEGOTIATION_FRAME = "negotiation_frame"
    OCCUPATION_FRAME = "occupation_frame"
    TWO_STATE_FRAME = "two_state_frame"
    EFFECTIVENESS_FRAME = "effectiveness_frame"
    SOVEREIGNTY_FRAME = "sovereignty_frame"
    MULTILATERAL_FRAME = "multilateral_frame"
    THREAT_FRAME = "threat_frame"
    DETERRENCE_FRAME = "deterrence_frame"
    PEACE_FRAME = "peace_frame"
    NEUTRAL = "neutral"
