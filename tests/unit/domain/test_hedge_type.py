from bb_paxdata.domain.enums.hedge_type import HedgeType


def test_hedge_type_values():
    assert HedgeType.MODAL_VERBS == "modal_verbs"
    assert HedgeType.LEXICAL_VERBS == "lexical_verbs"
    assert HedgeType.MODAL_PHRASES == "modal_phrases"
    assert HedgeType.APPROXIMATORS == "approximators"
    assert HedgeType.INTRODUCTORY_PHRASES == "introductory_phrases"
    assert HedgeType.IF_CLAUSES == "if_clauses"
    assert HedgeType.COMPOUND_HEDGES == "compound_hedges"


def test_hedge_type_weights():
    assert HedgeType.MODAL_VERBS.default_weight == 1.0
    assert HedgeType.COMPOUND_HEDGES.default_weight == 1.5
    assert HedgeType.APPROXIMATORS.default_weight == 0.8


def test_hedge_type_is_lexical():
    assert HedgeType.LEXICAL_VERBS.is_lexical is True
    assert HedgeType.APPROXIMATORS.is_lexical is True
    assert HedgeType.MODAL_VERBS.is_lexical is False
    assert HedgeType.IF_CLAUSES.is_lexical is False
