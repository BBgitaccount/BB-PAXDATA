"""Drift detection algorithms for temporal analysis."""

import math
from collections import Counter
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

MIN_SEGMENT_SIZE = 10
MAX_LAG = 2


def detect_sentiment_drift(
    sentiment_series: list[float], threshold: float = 0.3, drift_threshold: float = 2.0
) -> list[dict[str, Any]]:
    """
    Detect sentiment drift using CUSUM (Cumulative Sum) algorithm.

    Args:
        sentiment_series: List of sentiment scores
        threshold: Threshold for CUSUM detection
        drift_threshold: Drift detection threshold

    Returns:
        List of drift points with start/end indices
    """
    if len(sentiment_series) < MIN_SEGMENT_SIZE:
        return []

    try:
        # Calculate mean and standard deviation
        mean_val = np.mean(sentiment_series)
        std_val = np.std(sentiment_series)

        if std_val == 0:
            return []

        # Initialize CUSUM statistics
        cusum_pos = 0.0
        cusum_neg = 0.0

        drift_points = []
        in_drift = False
        drift_start = 0
        peak_sum = 0.0

        for i, value in enumerate(sentiment_series):
            # Standardize value
            z_score = (value - mean_val) / std_val

            # Update CUSUM statistics
            cusum_pos = max(0.0, float(cusum_pos + z_score - threshold))
            cusum_neg = min(0.0, float(cusum_neg + z_score + threshold))

            # Check for drift
            if not in_drift and (
                cusum_pos > drift_threshold or cusum_neg < -drift_threshold
            ):
                # Drift detected
                drift_start = i
                in_drift = True
                peak_sum = abs(cusum_pos) + abs(cusum_neg)

            if in_drift:
                peak_sum = max(peak_sum, abs(cusum_pos) + abs(cusum_neg))

            if (
                in_drift
                and abs(cusum_pos) < threshold / 2
                and abs(cusum_neg) < threshold / 2
            ):
                # Drift ended
                drift_points.append(
                    {
                        "start_index": max(0, drift_start - MAX_LAG),  # Include context
                        "end_index": min(len(sentiment_series) - 1, i + MAX_LAG),
                        "confidence": min(1.0, peak_sum / drift_threshold),
                        "magnitude": abs(value - sentiment_series[drift_start]),
                    }
                )
                in_drift = False

        return drift_points

    except Exception as e:
        logger.error(f"Error in sentiment drift detection: {e}")
        return []


def detect_topic_drift(
    topic_distributions: list[str],
    window_size: int = 5,
    divergence_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """
    Detect topic drift using Jensen-Shannon divergence.

    Args:
        topic_distributions: List of topic labels
        window_size: Size of sliding window
        divergence_threshold: Threshold for drift detection

    Returns:
        List of drift points
    """
    if len(topic_distributions) < window_size * 2:
        return []

    try:
        drift_points = []

        # Create sliding windows
        for i in range(window_size, len(topic_distributions) - window_size):
            # Get topic distributions for windows
            window1_topics = topic_distributions[i - window_size : i]
            window2_topics = topic_distributions[i : i + window_size]

            # Convert to probability distributions
            dist1 = _topics_to_distribution(window1_topics)
            dist2 = _topics_to_distribution(window2_topics)

            # Calculate Jensen-Shannon divergence
            js_divergence = _jensen_shannon_divergence(dist1, dist2)

            if js_divergence > divergence_threshold:
                confidence = 0.5 + 0.5 * (
                    1.0
                    - math.exp(
                        -(js_divergence - divergence_threshold) / divergence_threshold
                    )
                )
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(topic_distributions) - 1, i + window_size),
                        "confidence": min(1.0, confidence),
                        "divergence": js_divergence,
                    }
                )

        return drift_points

    except Exception as e:
        logger.error(f"Error in topic drift detection: {e}")
        return []


def detect_lexical_drift(
    word_counts: list[int], window_size: int = 5, mattr_threshold: float = 0.3
) -> list[dict[str, Any]]:
    """
    Detect lexical drift using Moving-Average Type-Token Ratio (MATTR).

    Args:
        word_counts: List of word counts per sentence
        window_size: Size of sliding window
        mattr_threshold: Threshold for drift detection

    Returns:
        List of drift points
    """
    if len(word_counts) < window_size * 2:
        return []

    try:
        drift_points = []

        # Calculate MATTR for sliding windows
        mattr_values = []
        for i in range(window_size, len(word_counts) - window_size):
            window_counts = word_counts[i - window_size : i + window_size]

            # Calculate MATTR (simplified as coefficient of variation)
            if np.mean(window_counts) > 0:
                mattr = float(np.std(window_counts) / np.mean(window_counts))
            else:
                mattr = 0.0

            mattr_values.append(mattr)

        # Detect changes in MATTR
        for i in range(1, len(mattr_values)):
            change = abs(mattr_values[i] - mattr_values[i - 1])

            if change > mattr_threshold:
                confidence = 0.5 + 0.5 * (
                    1.0 - math.exp(-(change - mattr_threshold) / mattr_threshold)
                )
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(word_counts) - 1, i + window_size),
                        "confidence": min(1.0, confidence),
                        "mattr_change": change,
                    }
                )

        return drift_points

    except Exception as e:
        logger.error(f"Error in lexical drift detection: {e}")
        return []


def detect_tone_drift(
    tone_series: list[str], transition_threshold: float = 0.4
) -> list[dict[str, Any]]:
    """
    Detect tone drift using Markov transition matrix analysis.

    Args:
        tone_series: List of tone labels
        transition_threshold: Threshold for transition change

    Returns:
        List of drift points
    """
    if len(tone_series) < MIN_SEGMENT_SIZE:
        return []

    try:
        # Get unique tones
        unique_tones = list(set(tone_series))
        tone_to_idx = {tone: i for i, tone in enumerate(unique_tones)}

        # Build transition matrices for sliding windows
        window_size = max(5, len(tone_series) // 10)
        drift_points = []

        for i in range(window_size, len(tone_series) - window_size):
            # Build transition matrix for first window
            window1 = tone_series[i - window_size : i]
            matrix1 = _build_transition_matrix(window1, tone_to_idx)

            # Build transition matrix for second window
            window2 = tone_series[i : i + window_size]
            matrix2 = _build_transition_matrix(window2, tone_to_idx)

            # Calculate matrix difference
            matrix_diff = np.linalg.norm(matrix2 - matrix1, "fro")

            if matrix_diff > transition_threshold:
                confidence = 0.5 + 0.5 * (
                    1.0
                    - math.exp(
                        -(matrix_diff - transition_threshold) / transition_threshold
                    )
                )
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(tone_series) - 1, i + window_size),
                        "confidence": min(1.0, confidence),
                        "transition_change": matrix_diff,
                    }
                )

        return drift_points

    except Exception as e:
        logger.error(f"Error in tone drift detection: {e}")
        return []


def detect_risk_trajectory_drift(
    risk_scores: list[int], slope_threshold: float = 0.5
) -> list[dict[str, Any]]:
    """
    Detect risk trajectory drift using slope change detection.

    Args:
        risk_scores: List of risk scores
        slope_threshold: Threshold for slope change

    Returns:
        List of drift points
    """
    if len(risk_scores) < MIN_SEGMENT_SIZE:
        return []

    try:
        drift_points = []
        window_size = max(3, len(risk_scores) // 8)

        for i in range(window_size, len(risk_scores) - window_size):
            # Calculate slope for first window
            x1 = np.arange(len(risk_scores[i - window_size : i]))
            y1 = np.array(risk_scores[i - window_size : i])
            slope1 = _calculate_slope(x1, y1)

            # Calculate slope for second window
            x2 = np.arange(len(risk_scores[i : i + window_size]))
            y2 = np.array(risk_scores[i : i + window_size])
            slope2 = _calculate_slope(x2, y2)

            # Calculate slope change
            slope_change = abs(slope2 - slope1)

            if slope_change > slope_threshold:
                confidence = 0.5 + 0.5 * (
                    1.0 - math.exp(-(slope_change - slope_threshold) / slope_threshold)
                )
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(risk_scores) - 1, i + window_size),
                        "confidence": min(1.0, confidence),
                        "slope_change": slope_change,
                    }
                )

        return drift_points

    except Exception as e:
        logger.error(f"Error in risk trajectory drift detection: {e}")
        return []


def _topics_to_distribution(topics: list[str]) -> dict[str, float]:
    """Convert list of topics to probability distribution."""
    if not topics:
        return {}

    topic_counts = Counter(topics)
    total = len(topics)

    return {topic: count / total for topic, count in topic_counts.items()}


def _jensen_shannon_divergence(
    dist1: dict[str, float], dist2: dict[str, float]
) -> float:
    """Calculate Jensen-Shannon divergence between two distributions."""
    # Get all unique topics
    all_topics = set(dist1.keys()) | set(dist2.keys())

    # Create probability arrays
    p1 = np.array([dist1.get(topic, 0.0) for topic in all_topics])
    p2 = np.array([dist2.get(topic, 0.0) for topic in all_topics])

    # Add small epsilon to avoid log(0)
    epsilon = 1e-10
    p1 = p1 + epsilon
    p2 = p2 + epsilon

    # Normalize
    p1 = p1 / np.sum(p1)
    p2 = p2 / np.sum(p2)

    # Calculate Jensen-Shannon divergence
    m = 0.5 * (p1 + p2)

    kl1 = np.sum(p1 * np.log(p1 / m))
    kl2 = np.sum(p2 * np.log(p2 / m))

    js_div = 0.5 * (kl1 + kl2)

    return float(js_div)


def _build_transition_matrix(
    tone_series: list[str], tone_to_idx: dict[str, int]
) -> np.ndarray:
    """Build Markov transition matrix from tone series."""
    n_tones = len(tone_to_idx)
    matrix = np.zeros((n_tones, n_tones))

    for i in range(len(tone_series) - 1):
        current_tone = tone_series[i]
        next_tone = tone_series[i + 1]

        if current_tone in tone_to_idx and next_tone in tone_to_idx:
            current_idx = tone_to_idx[current_tone]
            next_idx = tone_to_idx[next_tone]
            matrix[current_idx, next_idx] += 1

    # Normalize rows to get probabilities
    row_sums = matrix.sum(axis=1)
    for i in range(n_tones):
        if row_sums[i] > 0:
            matrix[i] = matrix[i] / row_sums[i]

    return matrix


def _calculate_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate slope using linear regression."""
    if len(x) < MAX_LAG:
        return 0.0

    # Use least squares to find slope
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if denominator == 0:
        return 0.0

    return float(numerator / denominator)


def detect_red_line_flexibility(
    risk_signals: list[int],
    stances: list[str],
) -> dict[str, Any]:
    """
    B1: Red Line Flexibility Index.
    If at t0, Risk_Signal == 3 (RED_LINE), and at t1, Risk_Signal == 1 and Stance == HEDGE
    then concession_detected = True.
    """
    concession_count = 0
    red_line_count = 0

    for i in range(len(risk_signals) - 1):
        if risk_signals[i] == 3:
            red_line_count += 1
            if risk_signals[i + 1] <= 1 and (
                stances[i + 1].upper() == "HEDGE" or "HEDGE" in stances[i + 1].upper()
            ):
                concession_count += 1

    flexibility_index = concession_count / red_line_count if red_line_count > 0 else 0.0
    return {
        "concession_detected": concession_count > 0,
        "red_line_flexibility_index": round(flexibility_index, 4),
        "red_line_count": red_line_count,
        "concession_count": concession_count,
    }


def detect_action_discourse_gap(
    commitments: list[str],
    has_action: list[bool],
) -> dict[str, Any]:
    """
    B5: Action-Discourse Gap.
    If the same high-commitment expression (e.g. 'will implement') is repeated 3+ times
    without actions, stalling_flag = True.
    """
    if len(commitments) < 3:
        return {
            "commitment_repetition_count": 0,
            "action_discourse_gap_score": 0.0,
            "stalling_flag": False,
        }

    repeats = 0
    max_repeats = 0
    last_comm = None

    for idx, comm in enumerate(commitments):
        # We only check repeats when there's no action
        action_taken = has_action[idx] if idx < len(has_action) else False
        if not action_taken and comm:
            if comm == last_comm:
                repeats += 1
            else:
                repeats = 1
            max_repeats = max(max_repeats, repeats)
        else:
            repeats = 0
        last_comm = comm

    stalling_flag = max_repeats >= 3
    score = min(max_repeats / 10.0, 1.0)
    return {
        "commitment_repetition_count": max_repeats,
        "action_discourse_gap_score": round(score, 4),
        "stalling_flag": stalling_flag,
    }


def calculate_mtld(tokens: list[str], threshold: float = 0.72) -> float:
    """
    A5: Measure of Textual Lexical Diversity (MTLD).
    Calculates vocabulary richness based on the stabilization point of TTR.
    """
    if not tokens:
        return 0.0

    def mtld_dir(toks: list[str]) -> float:
        factors = 0.0
        now_toks = []
        for t in toks:
            now_toks.append(t.lower())
            ttr = len(set(now_toks)) / len(now_toks)
            if ttr < threshold:
                factors += 1.0
                now_toks = []
        if now_toks:
            ttr = len(set(now_toks)) / len(now_toks)
            if ttr < 1.0:
                factors += (1.0 - ttr) / (1.0 - threshold)
        return len(toks) / max(factors, 0.0001)

    forward = mtld_dir(tokens)
    backward = mtld_dir(list(reversed(tokens)))
    return round((forward + backward) / 2.0, 4)


def estimate_sentiment_garch_volatility(
    sentiment_series: list[float],
    omega: float = 0.05,
    alpha: float = 0.15,
    beta: float = 0.8,
) -> dict[str, Any]:
    """
    A7: Sentiment Volatility GARCH(1,1).
    Recursively estimate conditional variance sigma^2_t = omega + alpha * eps^2_{t-1} + beta * sigma^2_{t-1}.
    """
    if not sentiment_series:
        return {"sentiment_volatility": 0.0, "volatility_regime": "LOW_VOLATILITY"}

    mean_val = sum(sentiment_series) / len(sentiment_series)
    residuals = [x - mean_val for x in sentiment_series]

    current_variance = (
        sum(r**2 for r in residuals) / len(residuals) if len(residuals) > 0 else 0.01
    )
    if current_variance == 0:
        current_variance = 0.01

    volatilities = []
    for r in residuals:
        current_variance = omega + alpha * (r**2) + beta * current_variance
        volatilities.append(math.sqrt(current_variance))

    last_vol = volatilities[-1] if volatilities else 0.0
    if last_vol > 0.4:
        regime = "HIGH_VOLATILITY"
    elif last_vol > 0.15:
        regime = "ARCH_EFFECTS"
    else:
        regime = "LOW_VOLATILITY"

    return {
        "sentiment_volatility": round(last_vol, 6),
        "volatility_regime": regime,
        "volatilities_series": [round(v, 6) for v in volatilities],
    }


def calculate_entity_salience_half_life(counts: list[int]) -> dict[str, Any]:
    """
    B8: Entity Salience Half-Life.
    Fits counts to f(t) = f0 * exp(-lambda * t) using regression on log(counts + 1).
    """
    if len(counts) < 2:
        return {
            "salience_half_life": 999.0,
            "decay_rate": 0.0,
            "agenda_permanence": "STRUCTURAL",
        }

    x = np.arange(len(counts))
    y = np.log1p(np.array(counts, dtype=float))

    x_mean = np.mean(x)
    y_mean = np.mean(y)

    x_diff = x - x_mean
    y_diff = y - y_mean

    num = np.sum(x_diff * y_diff)
    den = np.sum(x_diff**2)

    b = float(num / den) if den != 0 else 0.0
    decay_rate = -b

    if decay_rate > 0.001:
        half_life = math.log(2.0) / decay_rate
    else:
        half_life = 999.0  # Stable

    if half_life < 2.0:
        permanence = "FLASH"
    elif half_life < 5.0:
        permanence = "TACTICAL"
    elif half_life < 15.0:
        permanence = "STRATEGIC"
    else:
        permanence = "STRUCTURAL"

    return {
        "salience_half_life": round(half_life, 4),
        "decay_rate": round(decay_rate, 4),
        "agenda_permanence": permanence,
    }


def calculate_lexical_entropy(tokens: list[str]) -> float:
    """Calculate Shannon entropy of the token distribution."""
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = len(tokens)
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return round(entropy, 4)


def detect_entropy_constriction(
    entropy_series: list[float],
    threshold: float = -0.1,
) -> dict[str, Any]:
    """
    B10: Lexical Entropy Constriction.
    Triggers flag if shannon entropy drops substantially over the series.
    """
    if len(entropy_series) < 2:
        return {
            "shannon_entropy": entropy_series[-1] if entropy_series else 0.0,
            "entropy_delta": 0.0,
            "lexical_constriction_flag": False,
        }

    delta = entropy_series[-1] - entropy_series[0]
    flag = delta < threshold
    return {
        "shannon_entropy": round(entropy_series[-1], 4),
        "entropy_delta": round(delta, 4),
        "lexical_constriction_flag": flag,
    }


def detect_illocutionary_drift(
    speech_act_series: list[str],
    force_modifiers: list[str | None],
    window_size: int = 3,
    confidence_threshold: float = 0.5,
    min_commissive_ratio: float = 0.5,
) -> list[dict[str, Any]]:
    """Detects illocutionary drift from COMMISSIVE to DIRECTIVE within a sliding window.

    [Reference: Searle's Speech Act Theory, Illocutionary Force & Drift.]
    """
    if len(speech_act_series) < window_size:
        return []

    drift_points = []
    for i in range(window_size - 1, len(speech_act_series)):
        prev_window = speech_act_series[i - window_size + 1 : i]
        current_act = speech_act_series[i]

        if current_act != "DIRECTIVE":
            continue

        comm_count = prev_window.count("COMMISSIVE")
        window_len = len(prev_window)
        base_conf = comm_count / window_len if window_len > 0 else 0.0

        # Explicit ratio gate
        if base_conf < min_commissive_ratio:
            continue

        # Modifier adjustment
        mod_adj = _compute_modifier_adjustment(force_modifiers[i])
        final_conf = min(1.0, base_conf * (1.0 + mod_adj))

        if final_conf >= confidence_threshold:
            drift_points.append(
                {
                    "start_index": i - window_size + 1,
                    "end_index": i,
                    "confidence": round(final_conf, 4),
                    "magnitude": round(final_conf * 1.5, 2),
                    "before_state": "COMMISSIVE",
                    "after_state": f"DIRECTIVE:{force_modifiers[i] or 'none'}",
                    "commissive_ratio": round(base_conf, 4),
                }
            )
    return drift_points


def _compute_modifier_adjustment(modifier: str | None) -> float:
    if not modifier:
        return 0.0
    mod_lower = modifier.lower()
    if mod_lower in (
        "strongly",
        "categorically",
        "absolutely",
        "şiddetle",
        "kesinlikle",
        "kati",
        "mutlak",
    ):
        return 0.2
    if mod_lower in ("respectfully", "saygıyla"):
        return -0.1
    return 0.0
