import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .context import AnalysisContext
from .models import Analysis, AnomalyResult
from .protocols import AnomalyRule

logger = logging.getLogger(__name__)


class CrossAnomalyService:
    """
    Tüm anomali kurallarını koordine eden merkezi servis.
    Thread-safe ve concurrent evaluation destekler.
    """

    def __init__(self, max_workers: int = 4):
        self._rules: dict[str, AnomalyRule] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def register_rule(self, rule: AnomalyRule) -> None:
        """Kuralı sisteme kaydeder."""
        with self._lock:
            self._rules[rule.rule_id] = rule

    def unregister_rule(self, rule_id: str) -> None:
        """Kuralı sistemden çıkarır."""
        with self._lock:
            self._rules.pop(rule_id, None)

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> list[AnomalyResult]:
        """
        Tüm kayıtlı kuralları paralel olarak çalıştırır.
        """
        with self._lock:
            rules = list(self._rules.values())

        futures = {}
        results = []

        for rule in rules:
            future = self._executor.submit(self._safe_evaluate, rule, analysis, context)
            futures[future] = rule

        for future in as_completed(futures):
            try:
                result = future.result(timeout=30)
                if result is not None:
                    results.append(result)
            except Exception as e:
                rule = futures[future]
                logger.exception(f"Rule {rule.rule_id} failed: {e}")

        # Confidence score'a göre azalan sırada döndür
        results.sort(key=lambda r: r.confidence_score, reverse=True)
        return results

    def evaluate_single(
        self, rule_id: str, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        """Belirli bir kuralı çalıştırır."""
        with self._lock:
            rule = self._rules.get(rule_id)
        if rule is None:
            return None
        return self._safe_evaluate(rule, analysis, context)

    def _safe_evaluate(
        self, rule: AnomalyRule, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        """Kuralı hata yakalayarak çalıştırır."""
        try:
            return rule.evaluate(analysis, context)
        except Exception as e:
            logger.exception(f"Rule {rule.rule_id} evaluation error: {e}")
            return None

    def shutdown(self):
        """Servisi kapatır."""
        self._executor.shutdown(wait=True)
