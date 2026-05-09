from enum import Enum


class DkiStance(str, Enum):
    CONSTRUCTIVE = "CONSTRUCTIVE"
    CRITICAL = "CRITICAL"
    BALANCED = "BALANCED"
    AMBIGUOUS = "AMBIGUOUS"
