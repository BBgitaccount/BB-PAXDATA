from bb_paxdata.infrastructure.nlp.liwc_proxy import LIWCProxyService


def test_liwc_cognitive_processing():
    service = LIWCProxyService()
    text = "We think this negotiation is correct because we understand the policy."
    # Words: We (1) think (2) this (3) negotiation (4) is (5) correct (6) because (7) we (8) understand (9) the (10) policy (11)
    # causal hits: "because" -> 1
    # insight hits: "think", "understand" -> 2
    # cognitive processing score: (1 + 2) / 11 = 3/11 = 0.2727...
    result = service.analyze(text)
    assert result.cognitive_processing_score > 0.1
    assert result.causal_word_ratio > 0.05
    assert result.certainty_vs_tentative_ratio >= 0.0


def test_liwc_certainty_vs_tentative():
    service = LIWCProxyService()
    text = "We are absolutely sure that we will never accept this maybe."
    # certainty: "absolutely", "sure", "never"
    # tentative: "maybe"
    result = service.analyze(text)
    assert result.certainty_vs_tentative_ratio > 1.0


def test_liwc_cognitive_empty():
    service = LIWCProxyService()
    result = service.analyze("")
    assert result.cognitive_processing_score == 0.0
    assert result.causal_word_ratio == 0.0
    assert result.certainty_vs_tentative_ratio == 0.0
