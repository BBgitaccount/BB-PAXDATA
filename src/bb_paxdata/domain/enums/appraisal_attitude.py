from enum import Enum


class AppraisalAttitude(str, Enum):
    JUDGEMENT_NEGATIVE = "judgement_negative"
    JUDGEMENT_POSITIVE = "judgement_positive"
    AFFECT_NEGATIVE = "affect_negative"
    AFFECT_POSITIVE = "affect_positive"
    APPRECIATION = "appreciation"
    NEUTRAL = "neutral"
