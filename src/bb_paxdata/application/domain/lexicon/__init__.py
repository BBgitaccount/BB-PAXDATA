"""
Domain lexicon sub-package for BB-PAXDATA.

Provides Turkish-language lexical resources for diplomatic NLP analysis.
"""

from .tr_diplo_lexicon import DIPLO_LEXICON_TR, NEGATION_WORDS_TR
from .tr_stopwords import STOPWORDS_TR

__all__ = ["DIPLO_LEXICON_TR", "NEGATION_WORDS_TR", "STOPWORDS_TR"]
