from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .models import Analysis, AnomalyResult, AnomalySeverity

if TYPE_CHECKING:
    from .context import AnalysisContext


@runtime_checkable
class AnomalyRule(Protocol):
    """
    Tüm anomali kuralları bu protokolü implement etmelidir.
    Protocol-based architecture ile loose coupling sağlanır.
    """

    @property
    def rule_id(self) -> str:
        """Kuralın benzersiz kimliği."""
        ...

    @property
    def rule_name(self) -> str:
        """Kuralın insan tarafından okunabilir adı."""
        ...

    @property
    def severity(self) -> AnomalySeverity:
        """Kuralın varsayılan şiddet seviyesi."""
        ...

    def evaluate(
        self, analysis: Analysis, context: "AnalysisContext"
    ) -> AnomalyResult | None:
        """
        Analiz nesnesini değerlendirir.

        Args:
            analysis: Immutable analiz verisi.
            context: Harici servisler ve cache sağlayan bağlam.

        Returns:
            Anomali bulunursa AnomalyResult, yoksa None.
        """
        ...
