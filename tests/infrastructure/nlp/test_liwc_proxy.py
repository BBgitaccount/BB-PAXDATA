from bb_paxdata.infrastructure.nlp.liwc_proxy import LIWCProxyService


def test_liwc_proxy_clout():
    service = LIWCProxyService()
    text = "We demand absolute authority and categorical mandate."
    result = service.analyze(text)
    print(f"\nDEBUG: clout={result.clout}, word_count={result.word_count}")
    assert result.clout > 0.3
    assert result.word_count == 7


def test_liwc_proxy_analytic():
    service = LIWCProxyService()
    text = "Therefore we evaluate this policy framework because of the system analysis."
    result = service.analyze(text)

    assert result.analytic > 0.3


def test_liwc_proxy_tone():
    service = LIWCProxyService()

    pos_text = "This is a positive and constructive cooperation for peace."
    pos_result = service.analyze(pos_text)
    assert pos_result.tone > 0.5

    neg_text = "The conflict and crisis represent a negative threat."
    neg_result = service.analyze(neg_text)
    assert neg_result.tone < -0.5


def test_liwc_proxy_empty():
    service = LIWCProxyService()
    result = service.analyze("")
    assert result.word_count == 0
    assert result.clout == 0.0
