from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisContext:
    """
    Analiz sırasında gerekli olan harici servisleri ve
    servis çağrısı sonuçlarını saklayan bağlam (Context).
    """

    ner_service: Any
    risk_service: Any
    hedging_service: Any
    framing_service: Any
    speaker_service: Any
    dependency_service: Any
    recovery_engine: Any
    spacy_pipeline: Any
    svo_extractor: Any
    _cache: dict[str, Any] = field(default_factory=dict, repr=False)

    def get_cached(self, key: str, compute_fn: Callable[[], Any]) -> Any:
        """
        Servis çağrılarını memoize eder.

        Args:
            key: Cache anahtarı.
            compute_fn: Veri bulunamazsa çalıştırılacak fonksiyon.
        """
        if key not in self._cache:
            self._cache[key] = compute_fn()
        return self._cache[key]
