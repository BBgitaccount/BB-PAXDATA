"""Violation logging and reporting for data contract violations."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ViolationLogger:
    """Logs data contract violations to database and files."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or Path("logs/violations")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = structlog.get_logger(__name__)

    def log_violation(
        self,
        violation_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
        file_path: str | None = None,
    ) -> None:
        """
        Log a data contract violation.

        Args:
            violation_type: Type of violation (e.g., "SCHEMA_ERROR", "INPUT_VALIDATION")
            severity: Severity level (e.g., "LOW", "MEDIUM", "HIGH", "CRITICAL")
            message: Human-readable violation message
            details: Additional violation details
            file_path: Related file path if applicable
        """
        violation_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "violation_type": violation_type,
            "severity": severity,
            "message": message,
            "details": details or {},
            "file_path": file_path,
        }

        # Log to structured logger
        self.logger.warning("Data contract violation", **violation_record)

        # Write to violation log file
        log_file = (
            self.log_dir / f"violations_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        )

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(violation_record, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.error(
                "Failed to write violation to file",
                log_file=str(log_file),
                error=str(e),
            )

    def log_schema_violation(
        self,
        schema_name: str,
        validation_error: str,
        failure_cases: Any,
        row_count: int,
    ) -> None:
        """Log a schema validation violation."""
        self.log_violation(
            violation_type="SCHEMA_ERROR",
            severity="HIGH",
            message=f"Schema validation failed for {schema_name}",
            details={
                "schema_name": schema_name,
                "validation_error": validation_error,
                "failure_cases": str(failure_cases),
                "row_count": row_count,
            },
        )

    def log_input_violation(self, file_path: str, failed_checks: list[str]) -> None:
        """Log an input validation violation."""
        self.log_violation(
            violation_type="INPUT_VALIDATION",
            severity="MEDIUM",
            message=f"Input validation failed for {file_path}",
            details={
                "failed_checks": failed_checks,
            },
            file_path=file_path,
        )

    def get_violation_summary(self, days: int = 7) -> dict[str, Any]:
        """
        Get summary of violations in the last N days.

        Args:
            days: Number of days to look back

        Returns:
            Summary statistics
        """
        summary = {
            "total_violations": 0,
            "by_type": {},
            "by_severity": {},
            "by_file": {},
            "recent_violations": [],
        }

        # This would typically query a database or read log files
        # For now, return empty summary
        return summary
