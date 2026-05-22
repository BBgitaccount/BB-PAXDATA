from bb_paxdata.infrastructure.nlp.readability import (
    ReadabilityAnalyzer,
    count_syllables,
    is_abstract_word,
)


def test_count_syllables_en():
    assert count_syllables("apple", "en") == 2
    assert count_syllables("banana", "en") == 3
    assert count_syllables("democracy", "en") == 4


def test_count_syllables_tr():
    assert count_syllables("elma", "tr") == 2
    assert count_syllables("demokrasi", "tr") == 4
    assert count_syllables("egemenlik", "tr") == 4


def test_is_abstract_word():
    assert is_abstract_word("democracy", "en") is True
    assert is_abstract_word("solidarity", "en") is True
    assert is_abstract_word("governmentalism", "en") is True
    assert is_abstract_word("egemenlik", "tr") is True
    assert is_abstract_word("istikrar", "tr") is True
    assert is_abstract_word("elma", "tr") is False


def test_readability_analyzer_en():
    analyzer = ReadabilityAnalyzer(language="en")
    text = (
        "The strategic obfuscation is highly relevant in diplomatic communications. "
        "We prioritize sovereignty, security, and solidarity across the alliance."
    )
    scores = analyzer.analyze(text)
    assert scores.word_count > 0
    assert scores.sentence_count == 2
    assert scores.gunning_fog > 0.0
    assert scores.abstract_words_ratio > 0.05
    assert scores.constructive_ambiguity_flag is True


def test_readability_analyzer_empty():
    analyzer = ReadabilityAnalyzer(language="en")
    scores = analyzer.analyze("")
    assert scores.word_count == 0
    assert scores.gunning_fog == 0.0
    assert scores.constructive_ambiguity_flag is False
