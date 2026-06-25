from enum import StrEnum


class ValidationCheckType(StrEnum):
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
    QUALITY = "quality"
    COMPLETENESS = "completeness"
    LOGICAL = "logical"
