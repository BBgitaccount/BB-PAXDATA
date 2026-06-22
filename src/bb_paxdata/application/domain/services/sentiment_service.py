"""Sentiment analysis service using DIPLO lexicon with negation awareness.

This service implements sentiment analysis using the DIPLO (Diplomatic Discourse)
lexicon with negation-aware scoring. It provides both standard sentiment analysis
and negation-aware sentiment analysis for diplomatic discourse analysis.

Formula alignment with DatabaseBuilder_v5_8.py:
- diplo_sentiment(): phrase-first sort + re.search word-boundary + sum*0.05 + VADER
- negation_aware_diplo(): left-only window [i-N:i], 0.8 attenuation + VADER blend
  Academic: Jia & Liang (2017); Socher et al. (2013)
"""

import re
from typing import Any, ClassVar

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ...protocols import (
    BaseService,
    SentimentResult,
    SentimentServiceProtocol,
)
from ..enums import SentimentCategory
from ..lexicon.en_diplo_lexicon import DIPLO_LEXICON_EN, NEGATION_WORDS_EN
from ..models.sentence import Sentence


class SentimentService(BaseService, SentimentServiceProtocol):
    """Service for sentiment analysis using DIPLO lexicon with negation awareness."""

    # DIPLO diplomatic sentiment lexicon (from en_diplo_lexicon.py)
    DIPLO_LEXICON: ClassVar[dict[str, float]] = DIPLO_LEXICON_EN

    # Pre-sorted list of lexicon items for performance (longest phrase matched first)
    SORTED_DIPLO_ITEMS: ClassVar[list[tuple[str, float]]] = sorted(
        DIPLO_LEXICON.items(), key=lambda x: -len(x[0])
    )

    # Extended negation words list (from en_diplo_lexicon.py)
    NEGATION_WORDS: ClassVar[list[str]] = list(NEGATION_WORDS_EN)

    # Configuration constants
    NEGATION_WINDOW: ClassVar[int] = 4

    def __init__(self) -> None:
        """Initialize the sentiment service with VADER analyzer."""
        super().__init__()
        self._vader_analyzer = SentimentIntensityAnalyzer()

    def tokenize_words(self, text: str) -> list[str]:
        """Tokenize text into words with contraction handling.

        Mirrors DatabaseBuilder_v5_8.py tokenize_words():
        - Encode contractions: won't → won_t (preserves negation structure)
        - Decode back after split: won_t → won't (keeps negation word recognizable)
        - Regex includes Turkish characters: [a-zA-ZğüşıöçĞÜŞİÖÇ'_-]+

        Args:
            text: Input text to tokenize

        Returns:
            List of lowercase word tokens
        """
        tl = text.lower()

        # Step 1: encode contractions (apostrophe between letters becomes underscore)
        tl = re.sub(r"([a-zğüşıöç])'([a-zğüşıöç])", r"\1_\2", tl)

        # Step 2: tokenize — includes Turkish chars and underscore/hyphen
        raw_tokens = re.findall(r"\b[a-zğüşıöç_-]+\b", tl)

        # Step 3: decode back (won_t → won't so negation list matches)
        tokens = [t.replace("_", "'") for t in raw_tokens]

        return tokens

    def diplo_sentiment(self, text: str) -> float:
        """Calculate DIPLO sentiment score for text.

        Mirrors DatabaseBuilder_v5_8.py diplo_sentiment():
        - Phrase-first sorting (longest phrase matched first)
        - Word-boundary regex matching (re.search \\b...\\b)
        - Adjustment = sum(matched_scores) * 0.05, clamped [-2, 2]
        - Final = VADER compound + adj, clamped [-1, 1]

        Args:
            text: Input text to analyze

        Returns:
            Sentiment score from -1 to 1
        """
        tl = text.lower()

        # Sum all matched phrase scores (phrase-first: longest first)
        adj = (
            sum(
                v
                for phrase, v in self.SORTED_DIPLO_ITEMS
                if re.search(r"\b" + re.escape(phrase) + r"\b", tl)
            )
            * 0.05
        )

        # Clamp adjustment to [-2.0, 2.0]
        adj = max(-2.0, min(2.0, adj))

        # Blend with VADER compound
        vader_compound = float(self._vader_analyzer.polarity_scores(text)["compound"])
        diplo = round(max(-1.0, min(1.0, vader_compound + adj)), 4)
        return diplo

    def negation_aware_diplo(self, text: str) -> float:
        """Calculate negation-aware DIPLO sentiment score.

        Mirrors DatabaseBuilder_v5_8.py negation_aware_diplo():
        - Phrase-first matching on DIPLO_LEXICON (longest phrase first)
        - LEFT-ONLY negation window: tokens[max(0, i-N):i] (Jia & Liang 2017)
        - Negated score = -val * 0.8 (polarity reversal + 0.8 attenuation)
        - Final = VADER compound + sum(scores)*0.05, clamped [-1, 1]

        Args:
            text: Input text to analyze

        Returns:
            Negation-aware sentiment score from -1 to 1
        """
        tokens = self.tokenize_words(text)
        if not tokens:
            return 0.0

        scores: list[float] = []

        for i, _tok in enumerate(tokens):
            # Match phrases starting at position i (phrase-first: longest first)
            for phrase, val in self.SORTED_DIPLO_ITEMS:
                phrase_words = phrase.split()
                end = i + len(phrase_words)
                if end <= len(tokens) and tokens[i:end] == phrase_words:
                    # LEFT-ONLY negation window [i-N : i]
                    window = tokens[max(0, i - self.NEGATION_WINDOW) : i]
                    if any(neg in window for neg in self.NEGATION_WORDS):
                        val = -val * 0.8  # reverse polarity + 0.8 attenuation
                    scores.append(val)
                    break  # longest match consumed; move to next token

        # Adjustment = sum(scores) * 0.05
        adj = sum(scores) * 0.05

        # Blend with VADER compound, clamp to [-1, 1]
        vader_score = float(self._vader_analyzer.polarity_scores(text)["compound"])
        return round(max(-1.0, min(1.0, vader_score + adj)), 4)

    def _classify_emotion(self, sentiment_score: float) -> SentimentCategory:
        """Classify emotion category based on sentiment score.

        Mirrors DatabaseBuilder_v5_8.py emotion category thresholds:
          confrontational  : diplo <= -0.40
          concerned        : -0.40 < diplo <= -0.10
          neutral_cautious : -0.10 < diplo < 0.10
          constructive     : 0.10 <= diplo < 0.35
          cooperative      : diplo >= 0.35

        Args:
            sentiment_score: Sentiment score from -1 to 1

        Returns:
            Emotion category
        """
        if sentiment_score <= -0.40:
            return SentimentCategory.CONFRONTATIONAL
        elif sentiment_score <= -0.10:
            return SentimentCategory.CONCERNED
        elif sentiment_score < 0.10:
            return SentimentCategory.NEUTRAL_CAUTIOUS
        elif sentiment_score < 0.35:
            return SentimentCategory.CONSTRUCTIVE
        else:
            return SentimentCategory.COOPERATIVE

    def analyze(self, sentence: Sentence, **kwargs: Any) -> SentimentResult:
        """Analyze sentiment of a sentence.

        Args:
            sentence: The sentence to analyze
            **kwargs: Optional LIWC proxy for LIWC analysis

        Returns:
            SentimentResult containing sentiment scores and categories
        """
        text = sentence.text

        # Calculate negation-aware DIPLO sentiment
        negation_aware_score = self.negation_aware_diplo(text)

        # Get VADER sentiment for comparison
        vader_scores = self._vader_analyzer.polarity_scores(text)
        vader_compound = vader_scores["compound"]

        # negation_aware_score is the legacy diplo_compound (VADER + adj).
        # We use it directly as the final analysis score.
        final_score = negation_aware_score

        # Classify emotion category
        emotion_category = self._classify_emotion(final_score)

        # Calculate confidence based on agreement between methods
        confidence = 1.0 - abs(negation_aware_score - vader_compound) / 2.0
        confidence = max(0.3, min(1.0, confidence))  # Clamp between 0.3 and 1.0

        # LIWC analysis if proxy provided
        liwc_scores = kwargs.get("liwc_scores")

        return SentimentResult(
            score=final_score,
            emotion_category=emotion_category,
            negation_aware_score=negation_aware_score,
            confidence=confidence,
            liwc_scores=liwc_scores,
        )
