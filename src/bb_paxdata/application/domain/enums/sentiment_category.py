from enum import StrEnum


class SentimentCategory(StrEnum):
    COOPERATIVE = "cooperative"
    CONSTRUCTIVE = "constructive"
    NEUTRAL_CAUTIOUS = "neutral_cautious"
    CONCERNED = "concerned"
    CONFRONTATIONAL = "confrontational"
