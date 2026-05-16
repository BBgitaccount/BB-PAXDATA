from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bb_paxdata.domain.enums.sentiment_polarity import SentimentPolarity


@dataclass(frozen=True)
class ModelSentiment:
    """Tek bir modelin duygu analizi sonucu."""

    model_name: str  # "vader", "bert", "flair"
    compound_score: float  # [-1.0, 1.0]
    polarity: SentimentPolarity
    confidence: float  # [0.0, 1.0]


@dataclass(frozen=True)
class EnsembleSentiment:
    """Bonacchi (2024) majority voting ensemble sonucu.

    Reference:
        - Bonacchi, C. et al. (2024). Political Uses of the Ancient Past
          on Social Media. PLOS ONE.
    """

    final_score: float
    final_polarity: SentimentPolarity
    model_votes: tuple[ModelSentiment, ...]
    agreement_score: float
    confidence: float
    method: str


@dataclass(frozen=True)
class LIWCScores:
    """Pennebaker (2015) LIWC2015 proxy skorları.

    Faz 7'de SBI'nin "otoritatif/savunmacı söylem" alt boyutuna
    `clout` ve `analytic` skorları katkı sağlar.

    Reference:
        - Pennebaker, J.W. et al. (2015). LIWC2015.
    """

    clout: float | None = None
    analytic: float | None = None
    authenticity: float | None = None
    tone: float | None = None
    word_count: int = 0
