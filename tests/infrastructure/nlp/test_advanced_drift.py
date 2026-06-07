from bb_paxdata.application.domain.services.drift_algorithms import (
    calculate_entity_salience_half_life,
    calculate_lexical_entropy,
    calculate_mtld,
    detect_action_discourse_gap,
    detect_entropy_constriction,
    detect_red_line_flexibility,
    estimate_sentiment_garch_volatility,
)


def test_detect_red_line_flexibility():
    risk_signals = [3, 3, 1, 0]
    stances = ["DIRECT", "DIRECT", "HEDGE", "NEUTRAL"]
    result = detect_red_line_flexibility(risk_signals, stances)
    assert result["concession_detected"] is True
    assert result["red_line_flexibility_index"] == 0.5


def test_detect_action_discourse_gap():
    commitments = [
        "will implement",
        "will implement",
        "will implement",
        "will implement",
    ]
    has_action = [False, False, False, False]
    result = detect_action_discourse_gap(commitments, has_action)
    assert result["stalling_flag"] is True
    assert result["commitment_repetition_count"] == 4


def test_calculate_mtld():
    tokens = ["apple", "banana", "cherry", "date", "elderberry"] * 5
    mtld = calculate_mtld(tokens)
    assert mtld > 0.0


def test_estimate_sentiment_garch_volatility():
    sentiment_series = [0.1, -0.2, 0.3, -0.4, 0.5, -0.5, 0.6, -0.6, 0.7, -0.7]
    result = estimate_sentiment_garch_volatility(sentiment_series)
    assert "sentiment_volatility" in result
    assert result["sentiment_volatility"] >= 0.0


def test_calculate_entity_salience_half_life():
    counts = [100, 50, 25, 12, 6, 3]
    result = calculate_entity_salience_half_life(counts)
    assert result["salience_half_life"] < 5.0  # Quick decay
    assert result["agenda_permanence"] in [
        "FLASH",
        "TACTICAL",
        "STRATEGIC",
        "STRUCTURAL",
    ]


def test_entropy_constriction():
    tokens_start = ["apple", "banana", "cherry", "date", "elderberry"] * 4
    tokens_end = ["apple"] * 20
    entropy_start = calculate_lexical_entropy(tokens_start)
    entropy_end = calculate_lexical_entropy(tokens_end)
    result = detect_entropy_constriction([entropy_start, entropy_end])
    assert result["lexical_constriction_flag"] is True
