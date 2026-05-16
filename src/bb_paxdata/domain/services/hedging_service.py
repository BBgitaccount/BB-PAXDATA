"""Hedging analysis service for diplomatic discourse.

This service detects and analyzes hedging language in diplomatic discourse.
It identifies different types of hedging expressions and calculates hedging scores
to measure the level of uncertainty or indirectness in communication.
"""

import re
from typing import Any, ClassVar

from ...application.protocols import BaseService, HedgingResult, HedgingServiceProtocol
from ...domain.enums import HedgeType


class HedgingService(BaseService, HedgingServiceProtocol):
    """Service for hedging language analysis."""

    # Hedging lexicon organized by category (from DatabaseBuilder_v5_8.py)
    HEDGING_LEXICON: ClassVar[dict[str, list[str]]] = {
        "epistemic_high": [
            "might",
            "could",
            "may",
            "perhaps",
            "possibly",
            "probably",
            "arguably",
            "conceivably",
            "theoretically",
            "hypothetically",
            "it seems",
            "it appears",
            "i believe",
            "i think",
            "i suppose",
            "i suspect",
            "i guess",
            "i imagine",
            "i reckon",
        ],
        "epistemic_medium": [
            "tend to",
            "typically",
            "generally",
            "usually",
            "often",
            "frequently",
            "commonly",
            "in most cases",
            "by and large",
            "for the most part",
            "as a rule",
            "normally",
            "ordinarily",
        ],
        "anti_hedge": [
            "definitely",
            "certainly",
            "clearly",
            "obviously",
            "undoubtedly",
            "unquestionably",
            "absolutely",
            "surely",
            "without doubt",
            "no doubt",
            "in fact",
            "actually",
            "indeed",
            "really",
        ],
        "approximator": [
            "about",
            "approximately",
            "roughly",
            "around",
            "nearly",
            "almost",
            "close to",
            "in the vicinity of",
            "in the neighborhood of",
            "more or less",
            "or so",
            "somewhere",
            "somehow",
            "somewhat",
        ],
        "shield": [
            "i'm not sure",
            "i'm not certain",
            "i don't know",
            "i'm not expert",
            "i'm no expert",
            "i could be wrong",
            "i may be mistaken",
            "correct me if i'm wrong",
            "as far as i know",
            "to my knowledge",
            "from my perspective",
            "in my opinion",
            "personally",
        ],
        "attribution": [
            "according to",
            "reportedly",
            "allegedly",
            "supposedly",
            "apparently",
            "it is said",
            "it is reported",
            "it is claimed",
            "it is suggested",
            "it is believed",
            "it is thought",
            "it is understood",
            "it is assumed",
        ],
    }

    # Map category names to HedgeType enum
    CATEGORY_MAPPING: ClassVar[dict[str, HedgeType]] = {
        "epistemic_high": HedgeType.MODAL_VERBS,
        "epistemic_medium": HedgeType.LEXICAL_VERBS,
        "anti_hedge": HedgeType.MODAL_VERBS,  # Fallback or need to handle better
        "approximator": HedgeType.APPROXIMATORS,
        "shield": HedgeType.INTRODUCTORY_PHRASES,
        "attribution": HedgeType.MODAL_PHRASES,
    }

    def __init__(self) -> None:
        """Initialize the hedging service."""
        super().__init__()
        # Pre-compile regex patterns for better performance
        self._compile_patterns()

    def analyze(self, text: str, **kwargs: Any) -> Any:
        """Analyze hedging in text.

        Args:
            text: The text to analyze
            **kwargs: Additional analysis parameters

        Returns:
            HedgingResult containing hedging analysis
        """
        return self.analyze_hedging(text)

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for hedging detection."""
        self._patterns = {}

        for category, terms in self.HEDGING_LEXICON.items():
            # Create word-boundary regex patterns for each term
            patterns = []
            for term in terms:
                # Escape special regex characters and add word boundaries
                escaped_term = re.escape(term)
                pattern = rf"\b{escaped_term}\b"
                patterns.append(pattern)

            # Combine all patterns for this category
            self._patterns[category] = re.compile("|".join(patterns), re.IGNORECASE)

    def analyze_hedging(self, text: str) -> HedgingResult:
        """Analyze hedging language in text.

        Args:
            text: The text to analyze

        Returns:
            HedgingResult containing hedging score and categories
        """
        detected_categories = []
        hedging_score = 0.0
        total_matches = 0

        # Check each hedging category
        for category, pattern in self._patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected_categories.append(self.CATEGORY_MAPPING[category])
                total_matches += len(matches)

                # Different weights for different categories
                if category == "epistemic_high":
                    hedging_score += len(matches) * 0.8
                elif category == "epistemic_medium":
                    hedging_score += len(matches) * 0.5
                elif category == "anti_hedge":
                    hedging_score -= (
                        len(matches) * 0.3
                    )  # Negative weight for anti-hedges
                elif category == "approximator":
                    hedging_score += len(matches) * 0.4
                elif category == "shield":
                    hedging_score += len(matches) * 0.6
                elif category == "attribution":
                    hedging_score += len(matches) * 0.3

        # Normalize score to 0-1 range
        if total_matches > 0:
            # Base normalization
            normalized_score = hedging_score / max(1, total_matches)
            # Adjust for text length (longer texts naturally have more matches)
            word_count = len(text.split())
            length_factor = min(
                1.0, word_count / 50.0
            )  # Normalize to 50 words as baseline
            normalized_score = normalized_score / length_factor
        else:
            normalized_score = 0.0

        # Clamp to 0-1 range
        final_score = max(0.0, min(1.0, normalized_score))

        # Calculate confidence based on match consistency
        confidence = min(1.0, total_matches / 3.0) if total_matches > 0 else 0.3

        return HedgingResult(
            score=final_score, categories=detected_categories, confidence=confidence
        )

    def get_hedging_statistics(self, text: str) -> dict[str, int]:
        """Get detailed statistics for each hedging category.

        Args:
            text: The text to analyze

        Returns:
            Dictionary mapping category names to match counts
        """
        stats = {}

        for category, pattern in self._patterns.items():
            matches = pattern.findall(text)
            stats[category] = len(matches)

        return stats

    def is_hedged_sentence(self, text: str, threshold: float = 0.1) -> bool:
        """Determine if a sentence contains hedging language.

        Args:
            text: The text to check
            threshold: Minimum hedging score to consider as hedged

        Returns:
            True if the text is hedged above the threshold
        """
        result = self.analyze_hedging(text)
        return result.score >= threshold

    def get_dominant_hedging_type(self, text: str) -> HedgeType:
        """Get the dominant hedging type in the text.

        Args:
            text: The text to analyze

        Returns:
            The most frequently detected hedging type
        """
        stats = self.get_hedging_statistics(text)

        if not stats or all(count == 0 for count in stats.values()):
            return HedgeType.NONE

        # Find category with highest count
        dominant_level = max(stats, key=lambda k: float(stats[k]))
        max_count = stats[dominant_level]

        if max_count == 0:
            return HedgeType.NONE

        return self.CATEGORY_MAPPING.get(dominant_level, HedgeType.NONE)
