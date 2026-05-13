"""
Token-level attribution for explainability in BB-PAXDATA.
"""

from bb_paxdata.domain.models.explanation import TokenContribution
from bb_paxdata.domain.services.sentiment_service import SentimentService


def token_level_attribution(
    text: str, service: SentimentService
) -> list[TokenContribution]:
    """
    Calculate the contribution of each token to the overall sentiment score.

    Args:
        text: The text to analyze.
        service: An instance of SentimentService to access its lexicon and logic.

    Returns:
        A list of TokenContribution objects.
    """
    tokens = service.tokenize_words(text)
    lexicon = service.DIPLO_LEXICON
    negation_words = service.NEGATION_WORDS
    window_size = service.NEGATION_WINDOW

    contributions = []

    for i, tok in enumerate(tokens):
        # Default contribution
        sentiment_contrib = 0.0
        risk_contrib = 0.0
        explanation = "Nötr kelime."

        # Check lexicon match
        # (Simplified: only check single word match for attribution)
        if tok in lexicon:
            val = lexicon[tok]

            # Check for negation in window
            window = tokens[max(0, i - window_size) : i]
            negator = next((neg for neg in window if neg in negation_words), None)

            if negator:
                sentiment_contrib = -val * 0.8
                explanation = (
                    f"'{tok}' ({val}) kelimesi '{negator}' tarafından "
                    f"olumsuzlandığı için etkisi tersine çevrildi."
                )
            else:
                sentiment_contrib = val
                explanation = f"'{tok}' kelimesi sözlükte {val} değerine sahiptir."

            # If negative, it contributes to risk
            if sentiment_contrib < 0:
                risk_contrib = abs(sentiment_contrib) * 10

        contributions.append(
            TokenContribution(
                token=tok,
                sentiment_contrib=sentiment_contrib,
                risk_contrib=risk_contrib,
                explanation=explanation,
            )
        )

    return contributions
