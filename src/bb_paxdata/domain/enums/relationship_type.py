from enum import Enum


class RelationshipType(str, Enum):
    ALLY = "ALLY"
    ADVERSARY = "ADVERSARY"
    PARTNER = "PARTNER"
    CAUTIOUS = "CAUTIOUS"
    NEUTRAL = "NEUTRAL"
