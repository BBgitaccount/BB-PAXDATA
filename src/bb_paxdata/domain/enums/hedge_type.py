from __future__ import annotations

from enum import StrEnum


class HedgeType(StrEnum):
    """Salager-Meyer (1997) 7-kategori hedging şeması.

    Hyland (1998) ile kesişen kategoriler (MODAL_VERBS, LEXICAL_VERBS)
    aynı semantik alana işaret eder. Faz 1'de `HedgeDensity` ve
    `HedgeTypeRatio` formülleri bu enum üzerinden hesaplanacaktır.

    References:
        - Salager-Meyer, F. (1997). Hedges and Textual Communicative
          Function in Medical English Written Discourse.
        - Hyland, K. (1998). Hedging in Scientific Research Articles.
    """

    NONE = "none"

    # 1. Salager-Meyer Category 1 + Hyland overlap
    MODAL_VERBS = "modal_verbs"
    """Epistemic modal verbs: may, might, could, would."""

    # 2. Salager-Meyer Category 2 + Hyland overlap
    LEXICAL_VERBS = "lexical_verbs"
    """Hedging lexical verbs: suggest, indicate, appear, seem."""

    # 3. Salager-Meyer Category 3
    MODAL_PHRASES = "modal_phrases"
    """Multi-word epistemic phrases: it is possible that..."""

    # 4. Salager-Meyer Category 4
    APPROXIMATORS = "approximators"
    """Scalar approximators: approximately, roughly, about, sort of."""

    # 5. Salager-Meyer Category 5
    INTRODUCTORY_PHRASES = "introductory_phrases"
    """Speaker stance framing: in our view, from our perspective."""

    # 6. Salager-Meyer Category 6
    IF_CLAUSES = "if_clauses"
    """Conditional hedges: if true, if confirmed, should this occur."""

    # 7. Salager-Meyer Category 7
    COMPOUND_HEDGES = "compound_hedges"
    """Nested/multi-layer hedges: it might be suggested that..."""

    @property
    def default_weight(self) -> float:
        """Faz 1'de `HedgeDensity` formülünde kullanılacak ağırlık.

        Şu an varsayılan değerler placeholder'dır; ampirik kalibrasyon
        Faz 1'de yapılacaktır (ACADEMIC_FOUNDATIONS.md Bölüm 2, A2).
        """
        weights: dict[HedgeType, float] = {
            HedgeType.NONE: 0.0,
            HedgeType.MODAL_VERBS: 1.0,
            HedgeType.LEXICAL_VERBS: 1.0,
            HedgeType.MODAL_PHRASES: 1.2,
            HedgeType.APPROXIMATORS: 0.8,
            HedgeType.INTRODUCTORY_PHRASES: 1.1,
            HedgeType.IF_CLAUSES: 1.3,
            HedgeType.COMPOUND_HEDGES: 1.5,
        }
        return weights[self]

    @property
    def is_lexical(self) -> bool:
        """Hyland'ın lexical/non-lexical ayrımına göre sınıflandırma.

        `HedgeTypeRatio = LexicalHedge% / NonLexicalHedge%` hesabında
        kullanılır (ACADEMIC_FOUNDATIONS.md, A2 Formül Önerisi).
        """
        return self in {
            HedgeType.LEXICAL_VERBS,
            HedgeType.APPROXIMATORS,
        }
