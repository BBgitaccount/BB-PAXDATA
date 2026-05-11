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
        # Contraction map — encode (apostrophe → underscore)
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
        }

        tl = text.lower()

        # Step 1: encode contractions
        for contraction, encoded in contraction_map.items():
            tl = tl.replace(contraction, encoded)

        # Step 2: tokenize — includes Turkish chars and underscore/hyphen
        raw_tokens = re.findall(r"\b[a-zğüşıöç'_-]+\b", tl)

        # Step 3: decode back (won_t → won't so negation list matches)
        decode_map = {v: k for k, v in contraction_map.items()}
        tokens = [decode_map.get(tok, tok) for tok in raw_tokens]

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
                for phrase, v in sorted(
                    self.DIPLO_LEXICON.items(), key=lambda x: -len(x[0])
                )
                if re.search(r"\b" + re.escape(phrase) + r"\b", tl)
            )
            * 0.05
        )

        # Clamp adjustment to [-2.0, 2.0]
        adj = max(-2.0, min(2.0, adj))

        # Blend with VADER compound
        vader_compound = self._vader_analyzer.polarity_scores(text)["compound"]
        diplo = float(round(max(-1.0, min(1.0, vader_compound + adj)), 4))
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
            for phrase, val in sorted(
                self.DIPLO_LEXICON.items(), key=lambda x: -len(x[0])
            ):
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
        vader_score = self._vader_analyzer.polarity_scores(text)["compound"]
        return float(round(max(-1.0, min(1.0, vader_score + adj)), 4))

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

        return SentimentResult(
            score=final_score,
            emotion_category=emotion_category,
            negation_aware_score=negation_aware_score,
            confidence=confidence,
        )
