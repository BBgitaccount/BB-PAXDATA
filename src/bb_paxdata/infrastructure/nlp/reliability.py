# src/bb_paxdata/infrastructure/nlp/reliability.py
from __future__ import annotations

from typing import Any


def nominal_distance(v1: Any, v2: Any) -> float:
    return 0.0 if v1 == v2 else 1.0


def interval_distance(v1: Any, v2: Any) -> float:
    try:
        return (float(v1) - float(v2)) ** 2
    except (ValueError, TypeError):
        return 1.0  # Fallback to nominal if not numeric


def krippendorff_alpha(
    reliability_data: list[list[Any]], metric: str = "nominal"
) -> float:
    """
    Computes Krippendorff's Alpha reliability coefficient.

    reliability_data: list of lists of shape (n_coders, n_items).
                      Missing data should be represented as None.
    metric: "nominal" or "interval"
    """
    if not reliability_data or not reliability_data[0]:
        return 0.0

    n_coders = len(reliability_data)
    n_items = len(reliability_data[0])

    distance_fn = interval_distance if metric == "interval" else nominal_distance

    # Convert reliability data to item-centric format (n_items, n_coders)
    items_data = []
    for j in range(n_items):
        item_vals = [
            reliability_data[i][j]
            for i in range(n_coders)
            if reliability_data[i][j] is not None
        ]
        items_data.append(item_vals)

    # Filter items that have at least 2 annotations
    valid_items = [vals for vals in items_data if len(vals) >= 2]
    if not valid_items:
        return 0.0

    # 1. Observed Disagreement (Do)
    total_pairs_observed = 0
    sum_distances_observed = 0.0

    for vals in valid_items:
        n_i = len(vals)
        for idx1 in range(n_i):
            for idx2 in range(idx1 + 1, n_i):
                v1 = vals[idx1]
                v2 = vals[idx2]
                sum_distances_observed += distance_fn(v1, v2)
                total_pairs_observed += 1

    if total_pairs_observed == 0:
        return 1.0

    avg_distance_observed = sum_distances_observed / total_pairs_observed

    # 2. Expected Disagreement (De)
    # Collect all valid annotations in the dataset
    all_vals = []
    for vals in items_data:
        all_vals.extend(vals)

    n_total = len(all_vals)
    if n_total < 2:
        return 0.0

    sum_distances_expected = 0.0
    total_pairs_expected = 0

    for idx1 in range(n_total):
        for idx2 in range(idx1 + 1, n_total):
            v1 = all_vals[idx1]
            v2 = all_vals[idx2]
            sum_distances_expected += distance_fn(v1, v2)
            total_pairs_expected += 1

    if total_pairs_expected == 0:
        return 0.0

    avg_distance_expected = sum_distances_expected / total_pairs_expected

    if avg_distance_expected == 0.0:
        # If no expected disagreement exists, check if observed is also zero
        return 1.0 if avg_distance_observed == 0.0 else 0.0

    alpha = 1.0 - (avg_distance_observed / avg_distance_expected)
    return round(alpha, 6)
