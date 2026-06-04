from typing import Any

from pydantic import BaseModel, Field

from bb_paxdata.domain.enums.anomaly_severity import AnomalySeverity


class RuleAnomaly(BaseModel):
    """Represents a rule-triggered anomaly from plugin evaluation."""

    rule_id: str = Field(..., description="Unique identifier for the rule")
    rule_name: str = Field(..., description="Name of the anomaly rule")
    severity: AnomalySeverity = Field(..., description="Severity level of the anomaly")
    description: str = Field(..., description="Details about the triggered anomaly")
    affected_segments: list[str] = Field(
        default_factory=list, description="Cümle veya metin kesitleri"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Ek skor ve parametreler"
    )


class RuleHealthReport(BaseModel):
    """Health status and metrics of loaded anomaly detection rules."""

    total_rules: int = Field(..., description="Total number of rules (active + failed)")
    active_rules: int = Field(
        ..., description="Number of successfully loaded active rules"
    )
    failed_rules: list[tuple[str, str]] = Field(
        default_factory=list, description="List of (rule_name, error) for failed rules"
    )
    last_reload: str = Field(..., description="ISO timestamp of last rules reload")
