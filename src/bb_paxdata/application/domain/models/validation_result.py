from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..enums import (
    EvidenceType,
    FailCategory,
    LogLevel,
    ValidationCheckType,
)


class ValidationResult(BaseModel):
    """Represents the result of validation checks performed on data."""

    id: str = Field(..., description="Unique identifier for the validation result")
    entity_id: str = Field(..., description="ID of the entity being validated")
    entity_type: str = Field(..., description="Type of entity being validated")

    # Validation summary
    overall_status: str = Field(
        ..., description="Overall validation status (passed, failed, partial)"
    )
    total_checks: int = Field(..., ge=0, description="Total number of checks performed")
    passed_checks: int = Field(..., ge=0, description="Number of checks that passed")
    failed_checks: int = Field(..., ge=0, description="Number of checks that failed")
    skipped_checks: int = Field(
        default=0, ge=0, description="Number of checks that were skipped"
    )

    # Scores and metrics
    overall_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Overall validation score"
    )
    confidence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in validation results"
    )
    severity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Severity of failures"
    )

    # Individual check results
    check_results: dict[ValidationCheckType, bool] = Field(
        default_factory=dict, description="Results of individual validation checks"
    )
    check_details: dict[ValidationCheckType, str] = Field(
        default_factory=dict, description="Details for each check"
    )
    check_scores: dict[ValidationCheckType, float] = Field(
        default_factory=dict, description="Scores for each check"
    )

    # Failure analysis
    fail_categories: list[FailCategory] = Field(
        default_factory=list, description="Categories of failures"
    )
    critical_failures: list[ValidationCheckType] = Field(
        default_factory=list, description="Critical failures"
    )
    warning_failures: list[ValidationCheckType] = Field(
        default_factory=list, description="Warning-level failures"
    )

    # Evidence and context
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Types of evidence used in validation"
    )
    evidence_summary: str | None = Field(
        default=None, description="Summary of evidence used"
    )

    # Temporal information
    validation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When validation was performed",
    )
    validation_duration: float | None = Field(
        default=None, description="Duration of validation process"
    )

    # Validation configuration
    validation_version: str | None = Field(
        default=None, description="Version of validation rules used"
    )
    validator_id: str | None = Field(
        default=None, description="ID of the validator system"
    )
    validation_parameters: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Parameters used for validation"
    )

    # Recommendations and actions
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations based on validation results"
    )
    required_actions: list[str] = Field(
        default_factory=list, description="Required actions to fix issues"
    )
    optional_actions: list[str] = Field(
        default_factory=list, description="Optional improvements"
    )

    # Logging and debugging
    log_level: LogLevel | None = Field(
        default=LogLevel.INFO, description="Log level for this validation"
    )
    log_entries: list[str] = Field(
        default_factory=list, description="Log entries from validation process"
    )
    debug_info: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Debug information"
    )

    # Status and lifecycle
    is_resolved: bool = Field(
        default=False, description="Whether validation issues have been resolved"
    )
    resolution_method: str | None = Field(
        default=None, description="Method used to resolve issues"
    )
    resolution_timestamp: datetime | None = Field(
        default=None, description="When issues were resolved"
    )

    # Revalidation tracking
    revalidation_count: int = Field(
        default=0, ge=0, description="Number of revalidations performed"
    )
    previous_validation_id: str | None = Field(
        default=None, description="ID of previous validation if this is a revalidation"
    )

    # Notes and metadata
    summary: str | None = Field(
        default=None, description="Brief summary of validation results"
    )
    detailed_report: str | None = Field(
        default=None, description="Detailed validation report"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Additional metadata"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
