from typing import Any, Protocol, runtime_checkable

from bb_paxdata.domain.models.rule_anomaly import RuleAnomaly


@runtime_checkable
class AnomalyRule(Protocol):
    """Protocol that all dynamically loaded cross-anomaly rule plugins must satisfy."""

    @property
    def rule_id(self) -> str:
        """Unique ID of the rule."""
        ...

    @property
    def rule_name(self) -> str:
        """Human-readable name of the rule."""
        ...

    def evaluate(self, analysis_context: Any) -> list[RuleAnomaly]:
        """Evaluate the analysis context and return a list of triggered anomalies."""
        ...

    def get_metadata(self) -> dict[str, Any]:
        """Get description, version, and other metadata of the rule."""
        ...
