from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

STANCE_LEXICON = {
    "modal_verbs": [
        "can",
        "could",
        "may",
        "might",
        "must",
        "shall",
        "should",
        "will",
        "would",
        "ought",
    ],
    "hedges": [
        "perhaps",
        "possibly",
        "maybe",
        "likely",
        "unlikely",
        "probably",
        "apparent",
        "seemed",
        "appears",
        "suggests",
        "claims",
        "allegedly",
        "sort of",
        "kind of",
    ],
    "boosters": [
        "definitely",
        "certainly",
        "clearly",
        "obviously",
        "always",
        "never",
        "absolutely",
        "extremely",
        "totally",
        "entirely",
        "in fact",
        "indeed",
        "undoubtedly",
    ],
    "attitude_markers": [
        "unfortunately",
        "fortunately",
        "surprisingly",
        "interestingly",
        "alarmingly",
        "regrettably",
        "hopefully",
        "disappointingly",
        "rightly",
        "wrongly",
    ],
}

STANCE_WEIGHTS = {
    "modal_verbs": 1.0,
    "hedges": 0.8,
    "boosters": 1.2,
    "attitude_markers": 1.0,
}


class StanceDensityCalculator:
    """
    Implements Biber-style stance marker density (Biber 1988).

    Academic Source:
    Biber, D. (1988). Variation across speech and writing. Cambridge University Press.
    """

    def __init__(
        self,
        lexicon: dict[str, list[str]] | None = None,
        weights: dict[str, float] | None = None,
    ):
        self.lexicon = lexicon or STANCE_LEXICON
        self.weights = weights or STANCE_WEIGHTS

    async def calculate(self, tokens: list[str], speaker_id: str) -> float:
        """
        Return stance density score: sum(counts * weights) / total_tokens * 1000.
        """
        if not tokens:
            return 0.0

        total_tokens = len(tokens)
        token_set = [t.lower() for t in tokens]

        weighted_sum = 0.0
        details = {}

        for category, markers in self.lexicon.items():
            weight = self.weights.get(category, 1.0)
            count = 0
            for marker in markers:
                # Simple marker search (can be improved with spaCy matcher)
                count += token_set.count(marker)

            weighted_sum += count * weight
            details[category] = count

        # Normalize to 1000 tokens
        density = (weighted_sum / total_tokens) * 1000

        logger.debug(
            "stance_density.calculated",
            speaker_id=speaker_id,
            density=density,
            details=details,
        )

        return float(density)
