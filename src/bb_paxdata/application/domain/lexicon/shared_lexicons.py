"""Shared lexical resources used by multiple NLP services."""

GRADUATION_FORCE_UP: frozenset[str] = frozenset(
    {
        "deeply",
        "extremely",
        "profoundly",
        "sharply",
        "categorically",
        "strongly",
        "utterly",
        "absolutely",
        "completely",
        "entirely",
        "highly",
        "greatly",
        "severely",
        "seriously",
        "fundamentally",
        "blatantly",
        "flagrantly",
        "undeniably",
        "unequivocally",
        # Anti-hedge overlap (also in HedgingService.HEDGING_LEXICON["anti_hedge"]):
        "definitely",
        "certainly",
    }
)

GRADUATION_FORCE_DOWN: frozenset[str] = frozenset(
    {
        "slightly",
        "somewhat",
        "marginally",
        "barely",
        "hardly",
        "mildly",
        "partially",
        "relatively",
        "rather",
        "quite",
        "a bit",
        "a little",
        "to some extent",
        "in some ways",
    }
)
