from __future__ import annotations

import math
import re

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


class DetailedStanceScore(float):
    """Float subclass that carries additional stance/obfuscation metadata."""

    length_skew: float
    punctuation_spike: float
    extemporaneous_flag: bool
    emotional_arousal_index: float
    ccr_score: float
    commitment_strength: str

    def __new__(
        cls,
        value: float,
        length_skew: float,
        punctuation_spike: float,
        extemporaneous_flag: bool,
        emotional_arousal_index: float,
        ccr_score: float,
        commitment_strength: str,
    ) -> DetailedStanceScore:
        obj = super().__new__(cls, value)
        obj.length_skew = length_skew
        obj.punctuation_spike = punctuation_spike
        obj.extemporaneous_flag = extemporaneous_flag
        obj.emotional_arousal_index = emotional_arousal_index
        obj.ccr_score = ccr_score
        obj.commitment_strength = commitment_strength
        return obj


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
        Also computes additional punctuation skew and commitment/conditionality ratio.
        """
        if not tokens:
            return DetailedStanceScore(
                0.0,
                length_skew=0.0,
                punctuation_spike=0.0,
                extemporaneous_flag=False,
                emotional_arousal_index=0.0,
                ccr_score=0.0,
                commitment_strength="VAGUE",
            )

        total_tokens = len(tokens)
        token_set = [t.lower() for t in tokens]

        weighted_sum = 0.0
        details = {}

        for category, markers in self.lexicon.items():
            weight = self.weights.get(category, 1.0)
            count = 0
            for marker in markers:
                count += token_set.count(marker)

            weighted_sum += count * weight
            details[category] = count

        # Normalize to 1000 tokens
        density = (weighted_sum / total_tokens) * 1000

        # --- B4 & B7 Metrics ---
        text = " ".join(tokens)
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        sentence_count = max(1, len(sentences))
        sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]

        # Length Skew (CV of sentence lengths)
        mean_len = (
            sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0.0
        )
        if mean_len > 0:
            variance = sum((x - mean_len) ** 2 for x in sentence_lengths) / len(
                sentence_lengths
            )
            std_len = math.sqrt(variance)
            length_skew = std_len / mean_len
        else:
            length_skew = 0.0

        # Punctuation Spike
        excl_count = text.count("!")
        quest_count = text.count("?")
        punctuation_spike = (excl_count + quest_count) / sentence_count

        extemporaneous_flag = length_skew > 0.8
        emotional_arousal_index = (punctuation_spike * 4.0) + (length_skew * 1.5)

        # Commitment-Conditionality Ratio (CCR)
        commitment_words = {
            "will",
            "shall",
            "must",
            "guarantee",
            "commit",
            "şart",
            "zorunlu",
            "taahhüt",
            "edeceğiz",
            "yapacağız",
        }
        conditionality_words = {
            "would",
            "could",
            "might",
            "may",
            "perhaps",
            "possibly",
            "belki",
            "olabilir",
            "edebilir",
            "sanırım",
        }

        commitment_count = sum(1 for t in tokens if t.lower() in commitment_words)
        conditionality_count = sum(
            1 for t in tokens if t.lower() in conditionality_words
        )
        ccr_score = commitment_count / (conditionality_count + 1e-6)

        if ccr_score > 2.0:
            commitment_strength = "BINDING"
        elif ccr_score < 0.5:
            commitment_strength = "CONDITIONAL"
        else:
            commitment_strength = "VAGUE"

        logger.debug(
            "stance_density.calculated",
            speaker_id=speaker_id,
            density=density,
            details=details,
            length_skew=length_skew,
            punctuation_spike=punctuation_spike,
            ccr_score=ccr_score,
            commitment_strength=commitment_strength,
        )

        return DetailedStanceScore(
            float(density),
            length_skew=round(length_skew, 4),
            punctuation_spike=round(punctuation_spike, 4),
            extemporaneous_flag=extemporaneous_flag,
            emotional_arousal_index=round(emotional_arousal_index, 4),
            ccr_score=round(ccr_score, 4),
            commitment_strength=commitment_strength,
        )
