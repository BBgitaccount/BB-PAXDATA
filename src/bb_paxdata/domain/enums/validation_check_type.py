from enum import Enum


class ValidationCheckType(str, Enum):
    SENTIMENT = "sentiment"
    EMOTION = "emotion"
    RISK = "risk"
    DEMAND = "demand"
    TOPIC = "topic"
    HEDGING = "hedging"
    FRAME = "frame"
    APPRAISAL = "appraisal"
    AUDIENCE = "audience"
    MANIPULATION = "manipulation"
    POLITENESS = "politeness"
    EVIDENCE = "evidence"
