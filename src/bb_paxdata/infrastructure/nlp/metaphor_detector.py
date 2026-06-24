"""Metaphor Detector - Detects metaphors using lexicon and context validation.

Implements lexicon-based metaphor detection with context validation.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MetaphorDetector:
    """Metaphor detector using lexicon and context validation.

    Detects metaphors in diplomatic discourse using a lexicon of
    metaphorical expressions and validates them in context.
    """

    def __init__(self, lexicon_path: str | None = None):
        """Initialize metaphor detector.

        Args:
            lexicon_path: Path to metaphor lexicon JSON file
        """
        self.lexicon_path = lexicon_path or self._default_lexicon_path()
        self._lexicon = None

    def _default_lexicon_path(self) -> str:
        """Get default lexicon path.

        Returns:
            Default path to lexicon file
        """
        # Default to data/metaphor_lexicon.json
        return str(
            Path(__file__).parent.parent.parent.parent
            / "data"
            / "metaphor_lexicon.json"
        )

    async def initialize(self) -> None:
        """Initialize metaphor detector by loading lexicon.

        Should be called before first use.
        """
        try:
            if self._lexicon is None:
                self._lexicon = await asyncio.get_event_loop().run_in_executor(
                    None, self._load_lexicon
                )
                logger.info("metaphor_lexicon_loaded", lexicon_path=self.lexicon_path)
        except Exception as e:
            logger.error("metaphor_lexicon_load_failed", error=str(e))
            self._lexicon = {}

    def _load_lexicon(self) -> dict[str, Any]:
        """Load metaphor lexicon from JSON file.

        Returns:
            Lexicon dictionary
        """
        lexicon_path = Path(self.lexicon_path)

        if not lexicon_path.exists():
            logger.warning("metaphor_lexicon_not_found", path=self.lexicon_path)
            return self._default_lexicon()

        with open(lexicon_path, encoding="utf-8") as f:
            return json.load(f)

    def _default_lexicon(self) -> dict[str, Any]:
        """Get default metaphor lexicon.

        Returns:
            Default lexicon with common diplomatic metaphors
        """
        return {
            "war_metaphors": {
                "battle": ["fight", "struggle", "conflict"],
                "attack": ["criticize", "oppose", "challenge"],
                "defend": ["protect", "support", "maintain"],
                "retreat": ["withdraw", "back down", "concede"],
                "victory": ["success", "achievement", "triumph"],
                "defeat": ["failure", "loss", "setback"],
            },
            "journey_metaphors": {
                "path": ["route", "way", "direction"],
                "roadblock": ["obstacle", "barrier", "challenge"],
                "milestone": ["achievement", "progress", "step"],
                "destination": ["goal", "objective", "target"],
                "detour": ["deviation", "alternative", "change"],
            },
            "building_metaphors": {
                "foundation": ["basis", "groundwork", "base"],
                "construct": ["build", "create", "establish"],
                "collapse": ["fail", "break down", "crumble"],
                "support": ["back", "uphold", "sustain"],
                "structure": ["framework", "system", "organization"],
            },
            "nature_metaphors": {
                "grow": ["develop", "expand", "increase"],
                "bloom": ["flourish", "thrive", "prosper"],
                "wither": ["decline", "fade", "deteriorate"],
                "root": ["origin", "source", "cause"],
                "branch": ["division", "extension", "offshoot"],
            },
        }

    async def detect_metaphors(self, text: str) -> dict[str, Any]:
        """Detect metaphors in text.

        Args:
            text: Input text

        Returns:
            Dictionary with detected metaphors and validation results
        """
        try:
            await self.initialize()

            # Detect metaphorical expressions
            metaphor_candidates = self._detect_candidates(text)

            # Validate in context
            validated_metaphors = await self._validate_context(
                text, metaphor_candidates
            )

            return {
                "original_text": text,
                "metaphor_candidates": metaphor_candidates,
                "validated_metaphors": validated_metaphors,
                "metaphor_count": len(validated_metaphors),
                "metaphor_types": self._count_metaphor_types(validated_metaphors),
            }

        except Exception as e:
            logger.error("metaphor_detection_failed", error=str(e))
            return self._fallback_detection(text)

    def _detect_candidates(self, text: str) -> list[dict[str, Any]]:
        """Detect metaphorical expression candidates.

        Args:
            text: Input text

        Returns:
            List of metaphor candidates
        """
        candidates = []
        text_lower = text.lower()

        if not self._lexicon:
            return candidates

        # Check each metaphor category
        for category, metaphors in self._lexicon.items():
            for metaphor, variants in metaphors.items():
                # Check for metaphor and its variants
                all_forms = [metaphor, *variants]
                for form in all_forms:
                    if form in text_lower:
                        candidates.append(
                            {
                                "metaphor": metaphor,
                                "form": form,
                                "category": category,
                                "position": text_lower.find(form),
                                "context": self._extract_context(
                                    text, text_lower.find(form), len(form)
                                ),
                            }
                        )

        return candidates

    def _extract_context(self, text: str, position: int, length: int) -> str:
        """Extract context around a metaphor.

        Args:
            text: Original text
            position: Position of metaphor
            length: Length of metaphor

        Returns:
            Context string
        """
        context_window = 50
        start = max(0, position - context_window)
        end = min(len(text), position + length + context_window)
        return text[start:end]

    async def _validate_context(
        self, text: str, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Validate metaphor candidates in context.

        Args:
            text: Original text
            candidates: Metaphor candidates

        Returns:
            List of validated metaphors
        """
        validated = []

        for candidate in candidates:
            # Simple validation: check if context contains related words
            if self._is_valid_context(candidate["context"], candidate["category"]):
                validated.append(
                    {
                        **candidate,
                        "validated": True,
                        "confidence": self._compute_confidence(candidate),
                    }
                )

        return validated

    def _is_valid_context(self, context: str, category: str) -> bool:
        """Check if context supports metaphor interpretation.

        Args:
            context: Context string
            category: Metaphor category

        Returns:
            True if context supports metaphor
        """
        # Simple heuristic: check for context words that support metaphor
        context_lower = context.lower()

        # Category-specific validation
        if category == "war_metaphors":
            war_context_words = ["conflict", "fight", "struggle", "opponent", "enemy"]
            return any(word in context_lower for word in war_context_words)
        elif category == "journey_metaphors":
            journey_context_words = ["progress", "move", "forward", "step", "way"]
            return any(word in context_lower for word in journey_context_words)
        elif category == "building_metaphors":
            building_context_words = ["construct", "build", "establish", "create"]
            return any(word in context_lower for word in building_context_words)
        elif category == "nature_metaphors":
            nature_context_words = ["grow", "develop", "change", "evolve"]
            return any(word in context_lower for word in nature_context_words)

        # Default: accept if context contains metaphor
        return True

    def _compute_confidence(self, candidate: dict[str, Any]) -> float:
        """Compute confidence score for metaphor detection.

        Args:
            candidate: Metaphor candidate

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Simple confidence based on context length and category match
        context_length = len(candidate["context"])
        base_confidence = 0.5

        if context_length > 30:
            base_confidence += 0.2
        if context_length > 50:
            base_confidence += 0.2

        return min(base_confidence, 1.0)

    def _count_metaphor_types(self, metaphors: list[dict[str, Any]]) -> dict[str, int]:
        """Count metaphors by type.

        Args:
            metaphors: List of validated metaphors

        Returns:
            Dictionary of metaphor type counts
        """
        counts = {}
        for metaphor in metaphors:
            category = metaphor["category"]
            counts[category] = counts.get(category, 0) + 1
        return counts

    def _fallback_detection(self, text: str) -> dict[str, Any]:
        """Fallback detection when lexicon is unavailable.

        Args:
            text: Input text

        Returns:
            Fallback detection result
        """
        return {
            "original_text": text,
            "metaphor_candidates": [],
            "validated_metaphors": [],
            "metaphor_count": 0,
            "metaphor_types": {},
            "fallback_used": True,
        }
