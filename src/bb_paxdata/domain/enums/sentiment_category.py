from enum import Enum


class SentimentCategory(str, Enum):
    COOPERATIVE = "cooperative"
    CONSTRUCTIVE = "constructive"
    NEUTRAL_CAUTIOUS = "neutral_cautious"
    CONCERNED = "concerned"
    CONFRONTATIONAL = "confrontational"
