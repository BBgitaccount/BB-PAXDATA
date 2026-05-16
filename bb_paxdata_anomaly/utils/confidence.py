import math


class ConfidenceCalculator:
    """
    Farklı kural tipleri için istatistiksel confidence skoru hesaplama araçları.
    """

    @staticmethod
    def from_z_score(z: float, max_z: float = 3.0) -> float:
        """Z-skorunu 0-1 arası confidence'a mapler."""
        clamped = min(abs(z), max_z)
        return clamped / max_z

    @staticmethod
    def from_kl_divergence(kl: float, expected_max: float = 5.0) -> float:
        """KL divergence'ı confidence skoruna çevirir."""
        return min(kl / expected_max, 1.0)

    @staticmethod
    def from_deviation(
        deviation: float, threshold: float, steepness: float = 4.0
    ) -> float:
        """Threshold üzerindeki sapmayı sigmoid-like mapler."""
        if deviation <= 0:
            return 0.0
        return min(1.0, (deviation / threshold) ** steepness)

    @staticmethod
    def from_binary_match(
        matches: int, total: int, base_confidence: float = 0.95
    ) -> float:
        """Binary eşleşmelerden confidence üretir."""
        if total == 0:
            return 0.0
        ratio = matches / total
        return min(1.0, base_confidence * ratio)

    @staticmethod
    def sigmoid(x: float, center: float = 0.0, steepness: float = 1.0) -> float:
        """Standart sigmoid fonksiyonu."""
        try:
            return 1.0 / (1.0 + math.exp(-steepness * (x - center)))
        except OverflowError:
            return 1.0 if x > center else 0.0
