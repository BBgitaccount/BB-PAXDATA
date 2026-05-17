from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class RecoveryFailureConfig:
    """Recovery failure kuralı konfigürasyonu."""

    min_levels: int = 6
    required_schema_compliant: bool = False


class RecoveryFailureRule(BaseAnomalyRule):
    """
    ID: RULE_RECOVERY_FAILURE
    Mantık: AI çıktısının 6 seviyeli recovery sürecinden geçmesine rağmen
           hala şemaya uygun olmaması ve verinin kayıp olarak işaretlenmesi.
    """

    def __init__(self, config: RecoveryFailureConfig | None = None):
        self._config = config or RecoveryFailureConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_RECOVERY_FAILURE"

    @property
    def rule_name(self) -> str:
        return "Recovery Failure (Kurtarma Hatası)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.CRITICAL

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        data_id = analysis.metadata.get("data_id")
        if not data_id:
            return None

        try:
            # RecoveryEngine loglarını al
            recovery_log = context.recovery_engine.get_recovery_log(data_id)
        except Exception:
            return None

        levels_attempted = recovery_log.get("levels_attempted", 0)
        final_valid = recovery_log.get("final_valid", True)
        schema_compliant = recovery_log.get("schema_compliant", True)

        # Eğer veri geçerli ise veya 6 seviye tamamlanmadıysa anomali yoktur
        if (
            final_valid
            or schema_compliant
            or levels_attempted < self._config.min_levels
        ):
            return None

        # 6 seviye tamamlanmış ve hala invalid ise kesin anomali
        confidence = 0.98 if levels_attempted >= 6 else 0.7

        error_trace = recovery_log.get("error_trace", [])
        error_type = "unknown"
        if error_trace:
            last_error = error_trace[-1].lower()
            if "structural" in last_error:
                error_type = "structural"
            elif "semantic" in last_error:
                error_type = "semantic"
            elif "type" in last_error:
                error_type = "type_mismatch"

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=confidence,
            description=f"Veri kurtarma süreci {levels_attempted} seviye sonunda başarısız oldu.",
            affected_segments=[
                SegmentRef(
                    segment_id=(
                        analysis.transcript.segments[0].segment_id
                        if analysis.transcript.segments
                        else "unknown"
                    ),
                    start_time=0.0,
                    end_time=analysis.transcript.total_duration,
                )
            ],
            metadata={
                "levels_attempted": levels_attempted,
                "final_valid": final_valid,
                "schema_compliant": schema_compliant,
                "error_type": error_type,
                "error_trace": error_trace[:10],
            },
        )
