from typing import Any

import numpy as np


class StatisticalUtils:
    """
    Tekrar eden istatistiksel hesaplamalar için yardımcı sınıf.
    """

    @staticmethod
    def compute_variance(scores: list[float]) -> float:
        """Listenin varyansını hesaplar (Sample variance)."""
        if len(scores) < 2:
            return 0.0
        return float(np.var(scores, ddof=1))

    @staticmethod
    def compute_std(scores: list[float]) -> float:
        """Standart sapmayı hesaplar."""
        if len(scores) < 2:
            return 0.0
        return float(np.std(scores, ddof=1))

    @staticmethod
    def compute_z_score(value: float, mean: float, std: float) -> float:
        """Z-skorunu hesaplar."""
        if std == 0:
            return float("inf") if value != mean else 0.0
        return (value - mean) / std

    @staticmethod
    def sliding_window(items: list[Any], window_size: int) -> list[list[Any]]:
        """Kayan pencere oluşturur."""
        if window_size > len(items) or window_size <= 0:
            return []
        return [items[i : i + window_size] for i in range(len(items) - window_size + 1)]

    @staticmethod
    def chi_square_test(
        observed: list[float], expected: list[float]
    ) -> tuple[float, float]:
        """Chi-square testi yapar."""
        from scipy.stats import chisquare

        stat, p = chisquare(f_obs=observed, f_exp=expected)
        return float(stat), float(p)

    @staticmethod
    def kl_divergence(p: list[float], q: list[float]) -> float:
        """Kullback-Leibler Divergence hesaplar."""
        epsilon = 1e-10
        p_arr = np.array(p) + epsilon
        q_arr = np.array(q) + epsilon

        # Normalize
        p_arr = p_arr / np.sum(p_arr)
        q_arr = q_arr / np.sum(q_arr)

        return float(np.sum(p_arr * np.log(p_arr / q_arr)))
