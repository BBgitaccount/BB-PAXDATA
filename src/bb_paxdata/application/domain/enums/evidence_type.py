from enum import StrEnum


class EvidenceType(StrEnum):
    STATISTICAL = "statistical"
    HISTORICAL = "historical"
    AUTHORITY = "authority"
    ANECDOTAL = "anecdotal"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    NONE = "none"
