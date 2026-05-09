from enum import Enum


class SentimentArc(str, Enum):
    CRESCENDO_POSITIVE = "CRESCENDO_POSITIVE"
    CRESCENDO_NEGATIVE = "CRESCENDO_NEGATIVE"
    FLAT = "FLAT"
