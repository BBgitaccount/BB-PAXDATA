from enum import StrEnum


# TODO(DEAD-10): AnomalySeverity uses UPPERCASE string values ("LOW", "HIGH", etc.)
# which are stored in the `drift_events` DB table (column: severity) as Literal["LOW",
# "MEDIUM", "HIGH", "CRITICAL"]. Before this can be aliased to SeverityLevel (lowercase),
# run an Alembic migration:
#   op.execute("UPDATE drift_events SET severity = LOWER(severity)")
# Then replace this entire file with: AnomalySeverity = SeverityLevel
class AnomalySeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
