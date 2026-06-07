from enum import Enum


class EvidenceType(str, Enum):
    STATISTICAL = "statistical"
    HISTORICAL = "historical"
    AUTHORITY = "authority"
    ANECDOTAL = "anecdotal"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    NONE = "none"
