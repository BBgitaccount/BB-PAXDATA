from abc import ABC, abstractmethod

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity
from ..core.protocols import AnomalyRule


class BaseAnomalyRule(ABC, AnomalyRule):
    """
    Tüm anomali kuralları için ortak davranışları barındıran temel sınıf.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str: ...

    @property
    @abstractmethod
    def rule_name(self) -> str: ...

    @property
    @abstractmethod
    def severity(self) -> AnomalySeverity: ...

    @abstractmethod
    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        """Kuralın ana mantığı burada implement edilir."""
        ...
