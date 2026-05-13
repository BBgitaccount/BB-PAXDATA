"""
Language-specific normalization sub-package.

Provides Arabic, Cyrillic and Turkish character normalization utilities.
"""

from .arabic import normalize_arabic
from .cyrillic import normalize_cyrillic
from .turkish import normalize_turkish

__all__ = ["normalize_arabic", "normalize_cyrillic", "normalize_turkish"]
