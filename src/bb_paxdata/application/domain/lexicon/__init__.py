"""
Domain lexicon sub-package for BB-PAXDATA.

Provides Turkish and English lexical resources for diplomatic NLP analysis.
"""

from .en_diplo_lexicon import DIPLO_LEXICON_EN, NEGATION_WORDS_EN
from .en_stopwords import STOPWORDS_EN
from .tr_diplo_lexicon import DIPLO_LEXICON_TR, NEGATION_WORDS_TR
from .tr_stopwords import STOPWORDS_TR

__all__ = [
    "DIPLO_LEXICON_EN",
    "DIPLO_LEXICON_TR",
    "NEGATION_WORDS_EN",
    "NEGATION_WORDS_TR",
    "STOPWORDS_EN",
    "STOPWORDS_TR",
]
