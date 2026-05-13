"""Drift detection algorithms for temporal analysis."""

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

        for i, value in enumerate(sentiment_series):
            # Standardize value
            z_score = (value - mean_val) / std_val

            # Update CUSUM statistics
            cusum_pos = max(0.0, cusum_pos + z_score - threshold)
            cusum_neg = min(0.0, cusum_neg + z_score + threshold)

            # Check for drift
            if not in_drift and (
                cusum_pos > drift_threshold or cusum_neg < -drift_threshold
            ):
                # Drift detected
                drift_start = i
                in_drift = True

            elif (
                in_drift
                and abs(cusum_pos) < threshold / 2
                and abs(cusum_neg) < threshold / 2
            ):
                # Drift ended
                drift_points.append(
                    {
                        "start_index": max(0, drift_start - MAX_LAG),  # Include context
                        "end_index": min(len(sentiment_series) - 1, i + MAX_LAG),
                        "confidence": min(
                            1.0, (abs(cusum_pos) + abs(cusum_neg)) / drift_threshold
                        ),
                        "magnitude": abs(
                            sentiment_series[i] - sentiment_series[drift_start]
                        ),
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
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(topic_distributions) - 1, i + window_size),
                        "confidence": min(1.0, js_divergence / divergence_threshold),
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
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(word_counts) - 1, i + window_size),
                        "confidence": min(1.0, change / mattr_threshold),
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
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(tone_series) - 1, i + window_size),
                        "confidence": min(1.0, matrix_diff / transition_threshold),
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
                drift_points.append(
                    {
                        "start_index": max(0, i - window_size),
                        "end_index": min(len(risk_scores) - 1, i + window_size),
                        "confidence": min(1.0, slope_change / slope_threshold),
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
