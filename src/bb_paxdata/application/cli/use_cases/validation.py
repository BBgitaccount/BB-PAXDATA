from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()


class Severity(str, Enum):
    CRITICAL = "CRITICAL"  # Urgent intervention needed
    WARNING = "WARNING"  # Data quality might be affected
    INFO = "INFO"  # Informational


@dataclass(frozen=True)
class ValidationIssue:
    check_name: str
    severity: Severity
    message: str
    affected_rows: int | None = None
    suggested_fix: str | None = None
    details: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check_name,
            "severity": self.severity.value,
            "message": self.message,
            "affected_rows": self.affected_rows,
            "suggested_fix": self.suggested_fix,
        }


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue]
    total_checks: int
    duration_sec: float

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total_checks": self.total_checks,
            "duration_sec": self.duration_sec,
            "critical": self.critical_count,
            "warnings": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
        }


class SchemaChecker(Protocol):
    async def check_alembic_head(self, session: Any) -> ValidationIssue | None: ...
    async def check_foreign_keys(self, session: Any) -> list[ValidationIssue]: ...
    async def check_column_types(self, session: Any) -> list[ValidationIssue]: ...


class DataChecker(Protocol):
    async def check_orphan_transcripts(
        self, session: Any
    ) -> ValidationIssue | None: ...
    async def check_analytic_completeness(
        self, session: Any
    ) -> ValidationIssue | None: ...
    async def check_score_ranges(self, session: Any) -> list[ValidationIssue]: ...
    async def check_null_mandatory_fields(
        self, session: Any
    ) -> list[ValidationIssue]: ...
    async def check_duplicate_transcripts(
        self, session: Any
    ) -> ValidationIssue | None: ...


class ValidationUseCase:
    """
    Five-dimensional DB validation orchestrator.
    All checks run independently; if one fails, others continue.
    """

    def __init__(
        self,
        schema_checker: SchemaChecker,
        data_checker: DataChecker,
        session_factory: Any,
    ) -> None:
        self._schema = schema_checker
        self._data = data_checker
        self._factory = session_factory
        self._log = logger.bind(use_case="validation")

    async def execute(self) -> ValidationResult:
        start = time.monotonic()
        issues: list[ValidationIssue] = []
        checks = 0

        async with self._factory() as session:
            # -- Dimension 1: Schema --------------------------------------
            checks += 1
            if issue := await self._schema.check_alembic_head(session):
                issues.append(issue)

            checks += 1
            issues.extend(await self._schema.check_foreign_keys(session))

            checks += 1
            issues.extend(await self._schema.check_column_types(session))

            # -- Dimension 2: Reference Integrity -------------------------
            checks += 1
            if issue := await self._data.check_orphan_transcripts(session):
                issues.append(issue)

            # -- Dimension 3: Data Completeness ---------------------------
            checks += 1
            if issue := await self._data.check_analytic_completeness(session):
                issues.append(issue)

            checks += 1
            issues.extend(await self._data.check_null_mandatory_fields(session))

            # -- Dimension 4: Score Ranges --------------------------------
            checks += 1
            issues.extend(await self._data.check_score_ranges(session))

            # -- Dimension 5: Anomaly Detection ---------------------------
            checks += 1
            if issue := await self._data.check_duplicate_transcripts(session):
                issues.append(issue)

        critical = sum(1 for i in issues if i.severity == Severity.CRITICAL)
        self._log.info(
            "validation_complete",
            checks=checks,
            issues=len(issues),
            critical=critical,
            duration=round(time.monotonic() - start, 3),
        )

        return ValidationResult(
            passed=critical == 0,
            issues=issues,
            total_checks=checks,
            duration_sec=round(time.monotonic() - start, 3),
        )
