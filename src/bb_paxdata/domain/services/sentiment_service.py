"""Sentiment analysis service using DIPLO lexicon with negation awareness.

This service implements sentiment analysis using the DIPLO (Diplomatic Discourse)
lexicon with negation-aware scoring. It provides both standard sentiment analysis
and negation-aware sentiment analysis for diplomatic discourse analysis.
"""

import re
from typing import Any, ClassVar

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ...application.protocols import (
    BaseService,
    SentimentResult,
    SentimentServiceProtocol,
)
from ...domain.enums import SentimentCategory
from ...domain.models.sentence import Sentence


class SentimentService(BaseService, SentimentServiceProtocol):
    """Service for sentiment analysis using DIPLO lexicon with negation awareness."""

    # DIPLO diplomatic sentiment lexicon (from DatabaseBuilder_v5_8.py)
    DIPLO_LEXICON: ClassVar[dict[str, float]] = {
        # Extreme Negative (-0.7 to -0.9)
        "genocide": -0.8,
        "massacre": -0.8,
        "terrorism": -0.7,
        "terrorist": -0.7,
        "terror": -0.7,
        "premeditated starvation": -0.8,
        "imperial collapse": -0.7,
        # Strong Negative (-0.5 to -0.6)
        "aggression": -0.6,
        "aggressive": -0.6,
        "aggressor": -0.6,
        "chemical weapons": -0.6,
        "starvation": -0.6,
        "famine": -0.6,
        "apartheid": -0.6,
        "ontological rot": -0.6,
        "atrocity": -0.6,
        "immense destruction": -0.6,
        "destruction": -0.6,
        "unprovoked": -0.6,
        "war": -0.6,
        "devastating war": -0.6,
        "senseless war": -0.6,
        "coup": -0.5,
        "occupation": -0.5,
        "hegemony": -0.5,
        "siege": -0.5,
        "proxy war": -0.5,
        "illegal annexation": -0.5,
        "tragedy": -0.5,
        "casualties": -0.5,
        "martyrs": -0.5,
        "suffering": -0.5,
        "displacement": -0.5,
        "refugees": -0.5,
        "impunity": -0.5,
        "blackmail": -0.5,
        "repressive": -0.5,
        # Mid Negative (-0.3 to -0.4)
        "deadlock": -0.4,
        "impasse": -0.4,
        "double standards": -0.4,
        "disinformation": -0.4,
        "conflict": -0.4,
        "failed": -0.4,
        "extremism": -0.4,
        "fragmentation": -0.4,
        "cyberattack": -0.4,
        "polarization": -0.4,
        "sanction": -0.3,
        "sanctions": -0.3,
        "tension": -0.3,
        "threat": -0.3,
        "instability": -0.3,
        "unstable": -0.3,
        "turbulent": -0.3,
        "unpredictable": -0.3,
        # Low Negative (-0.1 to -0.2)
        "dependence": -0.2,
        "uncertainty": -0.2,
        "concern": -0.2,
        "zero-sum": -0.2,
        "fatigue": -0.2,
        "fragile": -0.1,
        # Extreme Positive (+0.6 to +0.8)
        "comprehensive peace": 0.7,
        "just peace": 0.6,
        "peace": 0.6,
        "peaceful coexistence": 0.6,
        "non-aggression": 0.6,
        # Strong Positive (+0.4 to +0.5)
        "anticipatory leadership": 0.5,
        "ceasefire": 0.5,
        "consensus": 0.5,
        "radical inclusion": 0.5,
        "reconciliation": 0.5,
        "prosperity": 0.5,
        "dialogue": 0.5,
        "negotiations": 0.5,
        "shared responsibility": 0.5,
        "accountability": 0.4,
        "cooperation": 0.4,
        "partnership": 0.4,
        "integration": 0.4,
        "normalization": 0.4,
        "sovereignty": 0.4,
        "diplomatic": 0.4,
        "solidarity": 0.4,
        "mediation": 0.4,
        "de-escalation": 0.4,
        "collective security": 0.4,
        "human rights": 0.4,
        "humanitarian aid": 0.4,
        "territorial integrity": 0.4,
        "win-win": 0.4,
        # Mid Positive (+0.2 to +0.3)
        "multilateral": 0.3,
        "multilateralism": 0.3,
        "multipolarity": 0.3,
        "resilience": 0.3,
        "inclusive": 0.3,
        "prevention": 0.3,
        "connectivity": 0.3,
        "deterrence": 0.3,
        "neutrality": 0.3,
        "reform": 0.2,
        "agreement": 0.2,
        "treaty": 0.2,
        # Low Positive (+0.1)
        "transition": 0.1,
        "stability": 0.1,
        "stable": 0.1,
        "stabilization": 0.1,
    }

    # Extended negation words list
    NEGATION_WORDS: ClassVar[list[str]] = [
        "not",
        "no",
        "never",
        "none",
        "nothing",
        "neither",
        "nowhere",
        "without",
        "lack",
        "lacks",
        "lacking",
        "lacked",
        "absent",
        "absence",
        "deny",
        "denies",
        "denied",
        "reject",
        "rejects",
        "rejected",
        "refuse",
        "refuses",
        "refused",
        "oppose",
        "opposes",
        "opposed",
        "against",
        "anti",
        "counter",
        "dis",
        "mis",
        "in",
        "im",
        "il",
        "ir",
        "un",
        "cannot",
        "can't",
        "couldn't",
        "wouldn't",
        "shouldn't",
        "mustn't",
        "mightn't",
        "needn't",
        "don't",
        "doesn't",
        "didn't",
        "won't",
        "isn't",
        "aren't",
        "wasn't",
        "weren't",
        "haven't",
        "hasn't",
        "hadn't",
    ]

    # Configuration constants
    NEGATION_WINDOW: ClassVar[int] = 4

    def __init__(self) -> None:
        """Initialize the sentiment service with VADER analyzer."""
        super().__init__()
        self._vader_analyzer = SentimentIntensityAnalyzer()

    def tokenize_words(self, text: str) -> list[str]:
        """Tokenize text into words with basic preprocessing.

        Args:
            text: Input text to tokenize

        Returns:
            List of word tokens
        """
        # Contraction map for better tokenization
        contraction_map = {
            "won't": "won_t",
            "don't": "don_t",
            "doesn't": "doesn_t",
            "didn't": "didn_t",
            "can't": "can_t",
            "couldn't": "couldn_t",
            "shouldn't": "shouldn_t",
            "wouldn't": "wouldn_t",
            "isn't": "isn_t",
            "aren't": "aren_t",
            "wasn't": "wasn_t",
            "weren't": "weren_t",
            "haven't": "haven_t",
            "hasn't": "hasn_t",
            "hadn't": "hadn_t",
            "mustn't": "mustn_t",
            "needn't": "needn_t",
            "shan't": "shan_t",
            "n't": "_nt",  # general fallback
        }

        # Apply contraction mapping
        for contraction, replacement in contraction_map.items():
            text = text.replace(contraction, replacement)

        # Basic tokenization: lowercase, split on non-word characters
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def diplo_sentiment(self, text: str) -> float:
        """Calculate DIPLO sentiment score for text.

        Args:
            text: Input text to analyze

        Returns:
            Sentiment score from -1 to 1
        """
        tokens = self.tokenize_words(text)
        if not tokens:
            return 0.0

        # Calculate sentiment using DIPLO lexicon
        sentiment_scores = []
        for token in tokens:
            # Check for exact matches first
            if token in self.DIPLO_LEXICON:
                sentiment_scores.append(self.DIPLO_LEXICON[token])
            else:
                # Check for partial matches in multi-word phrases
                for phrase, score in self.DIPLO_LEXICON.items():
                    if token in phrase.split():
                        sentiment_scores.append(
                            score * 0.5
                        )  # Reduced weight for partial matches
                        break

        if not sentiment_scores:
            return 0.0

        # Return average sentiment score
        return sum(sentiment_scores) / len(sentiment_scores)

    def negation_aware_diplo(self, text: str) -> float:
        """Calculate negation-aware DIPLO sentiment score.

        Args:
            text: Input text to analyze

        Returns:
            Negation-aware sentiment score from -1 to 1
        """
        tokens = self.tokenize_words(text)
        if not tokens:
            return 0.0

        sentiment_scores = []
        negation_positions = []

        # Find negation words and their positions
        for i, token in enumerate(tokens):
            if token in self.NEGATION_WORDS:
                negation_positions.append(i)

        # Calculate sentiment with negation awareness
        for i, token in enumerate(tokens):
            base_score = 0.0

            # Get base sentiment score
            if token in self.DIPLO_LEXICON:
                base_score = self.DIPLO_LEXICON[token]
            else:
                # Check for partial matches
                for phrase, score in self.DIPLO_LEXICON.items():
                    if token in phrase.split():
                        base_score = score * 0.5
                        break

            # Check if token is within negation window
            is_negated = False
            for neg_pos in negation_positions:
                if abs(i - neg_pos) <= self.NEGATION_WINDOW:
                    is_negated = True
                    break

            # Apply negation if detected
            if is_negated and base_score != 0.0:
                base_score = -base_score

            sentiment_scores.append(base_score)

        if not sentiment_scores:
            return 0.0

        return sum(sentiment_scores) / len(sentiment_scores)

    def _classify_emotion(self, sentiment_score: float) -> SentimentCategory:
        """Classify emotion category based on sentiment score.

        Args:
            sentiment_score: Sentiment score from -1 to 1

        Returns:
            Emotion category
        """
        if sentiment_score <= -0.6:
            return SentimentCategory.CONFRONTATIONAL
        elif sentiment_score <= -0.1:
            return SentimentCategory.CONCERNED
        elif sentiment_score <= 0.1:
            return SentimentCategory.NEUTRAL_CAUTIOUS
        elif sentiment_score <= 0.4:
            return SentimentCategory.CONSTRUCTIVE
        else:
            return SentimentCategory.COOPERATIVE

    def analyze(self, sentence: Sentence, **kwargs: Any) -> SentimentResult:
        """Analyze sentiment of a sentence.

        Args:
            sentence: The sentence to analyze

        Returns:
            SentimentResult containing sentiment scores and categories
        """
        text = sentence.text

        # Calculate negation-aware DIPLO sentiment
        negation_aware_score = self.negation_aware_diplo(text)

        # Get VADER sentiment for comparison
        vader_scores = self._vader_analyzer.polarity_scores(text)
        vader_compound = vader_scores["compound"]

        # Use negation-aware score as primary, but blend with VADER for robustness
        final_score = (negation_aware_score * 0.7) + (vader_compound * 0.3)

        # Classify emotion category
        emotion_category = self._classify_emotion(final_score)

        # Calculate confidence based on agreement between methods
        confidence = 1.0 - abs(negation_aware_score - vader_compound) / 2.0
        confidence = max(0.3, min(1.0, confidence))  # Clamp between 0.3 and 1.0

        return SentimentResult(
            score=final_score,
            emotion_category=emotion_category,
            negation_aware_score=negation_aware_score,
            confidence=confidence,
        )
