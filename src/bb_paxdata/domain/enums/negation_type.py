from enum import Enum


class NegationType(str, Enum):
    """Morante & Blanco (2012) SemEval-2012 Task 7 negasyon taksonomisi."""

    SURFACE = "surface"  # Açık yazılışsal negasyon (not, never, no)
    SYNTACTIC = "syntactic"  # Dependency-parse tabanlı scope
    SEMANTIC = "semantic"  # Ortük anlamsal negasyon (fail, deny, refuse)
    SCOPE_WIDE = "scope_wide"  # Çok-clause'lu geniş kapsam
