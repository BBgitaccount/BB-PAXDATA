from enum import Enum


class DiplomaticTone(str, Enum):
    ASSERTIVE = "assertive"
    CONCILIATORY = "conciliatory"
    EVASIVE = "evasive"
    CONFRONTATIONAL = "confrontational"
    NEUTRAL = "neutral"
    PERSUASIVE = "persuasive"
    DEFENSIVE = "defensive"
