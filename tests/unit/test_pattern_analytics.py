from bb_paxdata.interfaces.cli.commands.build import (
    classify_pattern_subtype,
    match_keyword_with_boundaries,
)


def test_match_keyword_with_boundaries_english():
    # True matches
    assert match_keyword_with_boundaries("if", "if you do this") is True
    assert match_keyword_with_boundaries("if", "what if we go?") is True

    # False matches (substrings)
    assert match_keyword_with_boundaries("if", "manifest destiny") is False
    assert match_keyword_with_boundaries("if", "shift gears") is False


def test_match_keyword_with_boundaries_turkish():
    # True matches
    assert match_keyword_with_boundaries("şayet", "şayet gelirseniz") is True
    assert (
        match_keyword_with_boundaries("koşuluyla", "kabul etme koşuluyla onayladım")
        is True
    )

    # False matches
    assert match_keyword_with_boundaries("eğer", "değer biçmek") is False


def test_classify_pattern_subtype():
    # Conditional
    assert classify_pattern_subtype("conditional", "if") == "hypothesis"
    assert classify_pattern_subtype("conditional", "provided that") == "precondition"
    assert classify_pattern_subtype("conditional", "koşuluyla") == "precondition"

    # Commitment
    assert classify_pattern_subtype("commitment", "we will") == "promise"
    assert classify_pattern_subtype("commitment", "commit") == "official_pledge"

    # Threat
    assert classify_pattern_subtype("threat", "otherwise") == "consequence_clause"
    assert classify_pattern_subtype("threat", "consequences") == "warning_clause"

    # Concession
    assert classify_pattern_subtype("concession", "however") == "contrast"
    assert classify_pattern_subtype("concession", "although") == "concession"

    # Appeal
    assert classify_pattern_subtype("appeal", "we call upon") == "exhortation"
    assert (
        classify_pattern_subtype("appeal", "international community")
        == "audience_appeal"
    )

    # Unknown
    assert classify_pattern_subtype("appeal", "nonexistent") == "unknown"


def test_context_bounds_segment_sentences():
    # Simulates the prev/next context logic used in build.py
    sentences = [
        "First sentence of segment.",
        "Middle sentence containing conditional if.",
        "Last sentence of segment.",
    ]

    # Let's test contexts for each index (1-indexed matching build.py loop)
    # Index 1 (First sentence)
    sent_idx = 1
    prev_sent = sentences[sent_idx - 2] if sent_idx >= 2 else "[START]"
    next_sent = sentences[sent_idx] if sent_idx < len(sentences) else "[END]"
    assert prev_sent == "[START]"
    assert next_sent == "Middle sentence containing conditional if."

    # Index 2 (Middle sentence)
    sent_idx = 2
    prev_sent = sentences[sent_idx - 2] if sent_idx >= 2 else "[START]"
    next_sent = sentences[sent_idx] if sent_idx < len(sentences) else "[END]"
    assert prev_sent == "First sentence of segment."
    assert next_sent == "Last sentence of segment."

    # Index 3 (Last sentence)
    sent_idx = 3
    prev_sent = sentences[sent_idx - 2] if sent_idx >= 2 else "[START]"
    next_sent = sentences[sent_idx] if sent_idx < len(sentences) else "[END]"
    assert prev_sent == "Middle sentence containing conditional if."
    assert next_sent == "[END]"
