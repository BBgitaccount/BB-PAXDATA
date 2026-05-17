from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

from spacy.tokens import Doc, Token

from bb_paxdata.domain.models.power_index import PowerIndex


class PowerIndexCalculator:
    """Van Dijk (1993) CDA kaynaklı güç indeksi hesaplama servisi.

    Authority Markers + Dominance Patterns + Legitimation Strategies
    """

    # 1. Authority Markers — otorite kurma ifadeleri
    AUTHORITY_CUES: frozenset[str] = frozenset(
        {
            "insist",
            "demand",
            "require",
            "expect",
            "call on",
            "urge",
            "it is imperative",
            "must",
            "need to",
            "have to",
            "should",
            "we will not accept",
            "cannot allow",
            "will not permit",
            "categorically",
            "unequivocally",
            "firmly",
            "strongly",
        }
    )

    # 2. Dominance Patterns — baskı örüntüleri
    DOMINANCE_CUES: frozenset[str] = frozenset(
        {
            # Agent deletion (pasif voice ile sorumlu aktör gizleme)
            "was agreed",
            "was decided",
            "was rejected",
            "was accepted",
            # Topicalization (konuşmacının gündemi dayatması)
            "firstly",
            "above all",
            "most importantly",
            "primarily",
            # Directives (emir kipi)
            "let us",
            "we must",
            "it is necessary",
            "there is a need",
        }
    )

    # 3. Legitimation Strategies — meşrulaştırma referansları
    LEGITIMATION_CUES: frozenset[str] = frozenset(
        {
            "international law",
            "un resolution",
            "security council",
            "democratic principles",
            "human rights",
            "geneva convention",
            "charter",
            "treaty",
            "agreement",
            "accord",
            "protocol",
            "international community",
            "global consensus",
            "norms",
            "precedent",
            "customary law",
            "obligation",
            "duty",
        }
    )

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp

    async def calculate(
        self, text: str, speaker_id: str, segment_id: str
    ) -> PowerIndex:
        """Metin üzerinde Van Dijk CDA güç indeksi hesapla."""
        doc: Doc = self._nlp(text)
        tokens = list(doc)
        token_count = len(tokens)

        if token_count == 0:
            return PowerIndex(speaker_id=speaker_id, segment_id=segment_id)

        # Sayım
        auth_count = self._count_cues(text, tokens, self.AUTHORITY_CUES)
        dom_count = self._count_cues(text, tokens, self.DOMINANCE_CUES)
        legit_count = self._count_cues(text, tokens, self.LEGITIMATION_CUES)

        # Yoğunluk (density) = count / total_tokens
        auth_density = auth_count / token_count
        dom_density = dom_count / token_count
        legit_density = legit_count / token_count

        # Pasif voice detection (dominance pattern)
        passive_count = sum(
            1
            for token in tokens
            if token.tag_ == "VBN" and any(c.dep_ == "auxpass" for c in token.children)
        )
        passive_density = passive_count / token_count

        return PowerIndex(
            speaker_id=speaker_id,
            segment_id=segment_id,
            authority_markers=auth_density,
            dominance_patterns=dom_density
            + passive_density,  # Pasif voice dominance'a eklenir
            legitimation_strategies=legit_density,
        )

    def _count_cues(
        self, text: str, tokens: Sequence[Token], cue_set: frozenset[str]
    ) -> int:
        """Phrase ve single-word cue sayımı."""
        count = 0
        text_lower = text.lower()

        # Phrase match
        for cue in cue_set:
            if " " in cue:
                # Count occurrences of the phrase
                idx = text_lower.find(cue)
                while idx != -1:
                    count += 1
                    idx = text_lower.find(cue, idx + 1)

        # Single token match
        single_cues = {c for c in cue_set if " " not in c}
        for token in tokens:
            if token.lemma_ in single_cues or token.lower_ in single_cues:
                count += 1

        return count
