"""AI Fail Check service for validation and quality control.

This service provides comprehensive validation and quality control for AI analysis
results. It implements multiple validation checks, consistency verification,
and failure detection mechanisms to ensure high-quality AI outputs.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ...domain.enums import ValidationCheckType


class ValidationStatus(Enum):
    """Validation check status."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    check_type: ValidationCheckType
    status: ValidationStatus
    score: float
    explanation: str
    discrepancy: float | None = None
    confidence: float = 1.0


@dataclass
class FailCheckResult:
    """Result of fail check analysis."""

    overall_status: ValidationStatus
    pass_count: int
    fail_count: int
    warning_count: int
    total_checks: int
    health_score: float
    validation_results: list[ValidationResult]
    fail_reasons: list[str]
    recommendations: list[str]


class AIFailCheck:
    """AI fail check and validation service."""

    def __init__(self) -> None:
        """Initialize the fail check service."""
        # Validation thresholds
        self.thresholds = {
            "sentiment_tolerance": 0.35,
            "risk_tolerance": 2.0,
            "hedging_tolerance": 0.30,
            "manipulation_tolerance": 0.30,
            "politeness_tolerance": 0.25,
            "min_confidence": 0.5,
            "max_response_time": 120.0,
        }

        # Validation weights
        self.check_weights = {
            ValidationCheckType.SENTIMENT: 0.2,
            ValidationCheckType.RISK: 0.2,
            ValidationCheckType.HEDGING: 0.15,
            ValidationCheckType.MANIPULATION: 0.15,
            ValidationCheckType.POLITENESS: 0.1,
            ValidationCheckType.TOPIC: 0.1,
            ValidationCheckType.FRAME: 0.05,
            ValidationCheckType.APPRAISAL: 0.025,
            ValidationCheckType.AUDIENCE: 0.025,
        }

    def validate_ai_response(
        self,
        ai_response: dict[str, Any],
        formula_response: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> FailCheckResult:
        """Perform comprehensive validation of AI response.

        Args:
            ai_response: AI analysis results
            formula_response: Formula-based analysis results
            context: Optional context information

        Returns:
            Comprehensive fail check result
        """
        validation_results = []

        # Perform all validation checks
        validation_results.append(
            self._check_sentiment_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_risk_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_hedging_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_manipulation_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_politeness_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_topic_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_frame_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_appraisal_consistency(ai_response, formula_response)
        )
        validation_results.append(
            self._check_audience_consistency(ai_response, formula_response)
        )

        # Additional quality checks
        validation_results.append(self._check_response_quality(ai_response))
        validation_results.append(self._check_data_completeness(ai_response))
        validation_results.append(self._check_logical_consistency(ai_response))

        # Calculate overall results
        return self._calculate_overall_result(validation_results)

    def _check_sentiment_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check sentiment analysis consistency."""
        ai_sentiment = ai_response.get("sentiment_score", 0.0)
        formula_sentiment = formula_response.get("sentiment_score", 0.0)

        discrepancy = abs(ai_sentiment - formula_sentiment)
        tolerance = self.thresholds["sentiment_tolerance"]

        if discrepancy <= tolerance:
            status = ValidationStatus.PASS
            explanation = (
                f"Sentiment scores consistent (discrepancy: {discrepancy:.3f})"
            )
        elif discrepancy <= tolerance * 2:
            status = ValidationStatus.WARNING
            explanation = (
                f"Sentiment scores moderately inconsistent "
                f"(discrepancy: {discrepancy:.3f})"
            )
        else:
            status = ValidationStatus.FAIL
            explanation = (
                f"Sentiment scores highly inconsistent (discrepancy: {discrepancy:.3f})"
            )

        return ValidationResult(
            check_type=ValidationCheckType.SENTIMENT,
            status=status,
            score=1.0 - (discrepancy / (tolerance * 2)),  # Normalize to 0-1
            explanation=explanation,
            discrepancy=discrepancy,
        )

    def _check_risk_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check risk assessment consistency."""
        ai_risk = ai_response.get("risk_score", 0.0)
        formula_risk = formula_response.get("risk_score", 0.0)

        discrepancy = abs(ai_risk - formula_risk)
        tolerance = self.thresholds["risk_tolerance"]

        if discrepancy <= tolerance:
            status = ValidationStatus.PASS
            explanation = f"Risk scores consistent (discrepancy: {discrepancy:.2f})"
        elif discrepancy <= tolerance * 2:
            status = ValidationStatus.WARNING
            explanation = (
                f"Risk scores moderately inconsistent "
                f"(discrepancy: {discrepancy:.2f})"
            )
        else:
            status = ValidationStatus.FAIL
            explanation = (
                f"Risk scores highly inconsistent (discrepancy: {discrepancy:.2f})"
            )

        return ValidationResult(
            check_type=ValidationCheckType.RISK,
            status=status,
            score=1.0 - (discrepancy / (tolerance * 2)),
            explanation=explanation,
            discrepancy=discrepancy,
        )

    def _check_hedging_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check hedging analysis consistency."""
        ai_hedging = ai_response.get("hedging_score", 0.0)
        formula_hedging = formula_response.get("hedging_score", 0.0)

        discrepancy = abs(ai_hedging - formula_hedging)
        tolerance = self.thresholds["hedging_tolerance"]

        if discrepancy <= tolerance:
            status = ValidationStatus.PASS
            explanation = f"Hedging scores consistent (discrepancy: {discrepancy:.3f})"
        elif discrepancy <= tolerance * 2:
            status = ValidationStatus.WARNING
            explanation = (
                f"Hedging scores moderately inconsistent "
                f"(discrepancy: {discrepancy:.3f})"
            )
        else:
            status = ValidationStatus.FAIL
            explanation = (
                f"Hedging scores highly inconsistent (discrepancy: {discrepancy:.3f})"
            )

        return ValidationResult(
            check_type=ValidationCheckType.HEDGING,
            status=status,
            score=1.0 - (discrepancy / (tolerance * 2)),
            explanation=explanation,
            discrepancy=discrepancy,
        )

    def _check_manipulation_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check manipulation analysis consistency."""
        ai_manipulation = ai_response.get("manipulation_score", 0.0)
        formula_manipulation = formula_response.get("manipulation_score", 0.0)

        discrepancy = abs(ai_manipulation - formula_manipulation)
        tolerance = self.thresholds["manipulation_tolerance"]

        if discrepancy <= tolerance:
            status = ValidationStatus.PASS
            explanation = (
                f"Manipulation scores consistent (discrepancy: {discrepancy:.3f})"
            )
        elif discrepancy <= tolerance * 2:
            status = ValidationStatus.WARNING
            explanation = (
                f"Manipulation scores moderately inconsistent "
                f"(discrepancy: {discrepancy:.3f})"
            )
        else:
            status = ValidationStatus.FAIL
            explanation = (
                f"Manipulation scores highly inconsistent "
                f"(discrepancy: {discrepancy:.3f})"
            )

        return ValidationResult(
            check_type=ValidationCheckType.MANIPULATION,
            status=status,
            score=1.0 - (discrepancy / (tolerance * 2)),
            explanation=explanation,
            discrepancy=discrepancy,
        )

    def _check_politeness_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check politeness analysis consistency."""
        ai_politeness = ai_response.get("politeness_score", 0.0)
        formula_politeness = formula_response.get("politeness_score", 0.0)

        discrepancy = abs(ai_politeness - formula_politeness)
        tolerance = self.thresholds["politeness_tolerance"]

        if discrepancy <= tolerance:
            status = ValidationStatus.PASS
            explanation = (
                f"Politeness scores consistent (discrepancy: {discrepancy:.3f})"
            )
        elif discrepancy <= tolerance * 2:
            status = ValidationStatus.WARNING
            explanation = (
                f"Politeness scores moderately inconsistent "
                f"(discrepancy: {discrepancy:.3f})"
            )
        else:
            status = ValidationStatus.FAIL
            explanation = (
                f"Politeness scores highly inconsistent "
                f"(discrepancy: {discrepancy:.3f})"
            )

        return ValidationResult(
            check_type=ValidationCheckType.POLITENESS,
            status=status,
            score=1.0 - (discrepancy / (tolerance * 2)),
            explanation=explanation,
            discrepancy=discrepancy,
        )

    def _check_topic_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check topic analysis consistency."""
        ai_topic = ai_response.get("dominant_topic", "")
        formula_topic = formula_response.get("dominant_topic", "")

        if ai_topic == formula_topic:
            status = ValidationStatus.PASS
            score = 1.0
            explanation = f"Topic analysis consistent: {ai_topic}"
        elif ai_topic and formula_topic:
            status = ValidationStatus.WARNING
            score = 0.5
            explanation = (
                f"Topic analysis differs: AI={ai_topic}, Formula={formula_topic}"
            )
        else:
            status = ValidationStatus.FAIL
            score = 0.0
            explanation = "Missing topic analysis in one or both responses"

        return ValidationResult(
            check_type=ValidationCheckType.TOPIC,
            status=status,
            score=score,
            explanation=explanation,
        )

    def _check_frame_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check frame analysis consistency."""
        ai_frame = ai_response.get("frame_type", "")
        formula_frame = formula_response.get("frame_type", "")

        if ai_frame == formula_frame:
            status = ValidationStatus.PASS
            score = 1.0
            explanation = f"Frame analysis consistent: {ai_frame}"
        elif ai_frame and formula_frame:
            status = ValidationStatus.WARNING
            score = 0.5
            explanation = (
                f"Frame analysis differs: AI={ai_frame}, " f"Formula={formula_frame}"
            )
        else:
            status = ValidationStatus.FAIL
            score = 0.0
            explanation = "Missing frame analysis in one or both responses"

        return ValidationResult(
            check_type=ValidationCheckType.FRAME,
            status=status,
            score=score,
            explanation=explanation,
        )

    def _check_appraisal_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check appraisal attitude consistency."""
        ai_appraisal = ai_response.get("appraisal_attitude", "")
        formula_appraisal = formula_response.get("appraisal_attitude", "")

        if ai_appraisal == formula_appraisal:
            status = ValidationStatus.PASS
            score = 1.0
            explanation = f"Appraisal attitude consistent: {ai_appraisal}"
        elif ai_appraisal and formula_appraisal:
            status = ValidationStatus.WARNING
            score = 0.5
            explanation = (
                f"Appraisal attitude differs: AI={ai_appraisal}, "
                f"Formula={formula_appraisal}"
            )
        else:
            status = ValidationStatus.FAIL
            score = 0.0
            explanation = "Missing appraisal attitude in one or both responses"

        return ValidationResult(
            check_type=ValidationCheckType.APPRAISAL,
            status=status,
            score=score,
            explanation=explanation,
        )

    def _check_audience_consistency(
        self, ai_response: dict[str, Any], formula_response: dict[str, Any]
    ) -> ValidationResult:
        """Check audience type consistency."""
        ai_audience = ai_response.get("audience_type", "")
        formula_audience = formula_response.get("audience_type", "")

        if ai_audience == formula_audience:
            status = ValidationStatus.PASS
            score = 1.0
            explanation = f"Audience type consistent: {ai_audience}"
        elif ai_audience and formula_audience:
            status = ValidationStatus.WARNING
            score = 0.5
            explanation = (
                f"Audience type differs: AI={ai_audience}, Formula={formula_audience}"
            )
        else:
            status = ValidationStatus.FAIL
            score = 0.0
            explanation = "Missing audience type in one or both responses"

        return ValidationResult(
            check_type=ValidationCheckType.AUDIENCE,
            status=status,
            score=score,
            explanation=explanation,
        )

    def _check_response_quality(self, ai_response: dict[str, Any]) -> ValidationResult:
        """Check overall response quality."""
        issues = []

        # Check for required fields
        required_fields = ["sentiment_score", "risk_score", "hedging_score"]
        missing_fields = [
            field for field in required_fields if field not in ai_response
        ]
        if missing_fields:
            issues.append(f"Missing fields: {missing_fields}")

        # Check for valid score ranges
        score_fields = [
            "sentiment_score",
            "hedging_score",
            "manipulation_score",
            "politeness_score",
        ]
        for field in score_fields:
            if field in ai_response:
                score = ai_response[field]
                if not isinstance(score, int | float) or not (-1 <= score <= 1):
                    issues.append(f"Invalid {field}: {score}")

        # Check risk score range
        if "risk_score" in ai_response:
            risk_score = ai_response["risk_score"]
            if not isinstance(risk_score, int | float) or not (0 <= risk_score <= 10):
                issues.append(f"Invalid risk_score: {risk_score}")

        if not issues:
            status = ValidationStatus.PASS
            score = 1.0
            explanation = "Response quality check passed"
        else:
            status = ValidationStatus.FAIL
            score = 0.0
            explanation = f"Quality issues: {'; '.join(issues)}"

        return ValidationResult(
            check_type=ValidationCheckType.QUALITY,
            status=status,
            score=score,
            explanation=explanation,
        )

    def _check_data_completeness(self, ai_response: dict[str, Any]) -> ValidationResult:
        """Check data completeness."""
        expected_fields = [
            "sentiment_score",
            "risk_score",
            "hedging_score",
            "manipulation_score",
            "politeness_score",
            "dominant_topic",
            "frame_type",
            "appraisal_attitude",
            "audience_type",
        ]

        present_fields = [field for field in expected_fields if field in ai_response]
        completeness = len(present_fields) / len(expected_fields)

        if completeness >= 0.9:
            status = ValidationStatus.PASS
            explanation = (
                f"Data complete ({len(present_fields)}/{len(expected_fields)} fields)"
            )
        elif completeness >= 0.7:
            status = ValidationStatus.WARNING
            explanation = (
                f"Data partially complete "
                f"({len(present_fields)}/{len(expected_fields)} fields)"
            )
        else:
            status = ValidationStatus.FAIL
            explanation = (
                f"Data incomplete ({len(present_fields)}/{len(expected_fields)} fields)"
            )

        return ValidationResult(
            check_type=ValidationCheckType.COMPLETENESS,
            status=status,
            score=completeness,
            explanation=explanation,
        )

    def _check_logical_consistency(
        self, ai_response: dict[str, Any]
    ) -> ValidationResult:
        """Check logical consistency within AI response."""
        issues = []

        sentiment = ai_response.get("sentiment_score", 0.0)
        risk = ai_response.get("risk_score", 0.0)
        manipulation = ai_response.get("manipulation_score", 0.0)
        politeness = ai_response.get("politeness_score", 0.0)

        # Check for logical inconsistencies
        if sentiment > 0.5 and risk > 7.0:
            issues.append("High positive sentiment with high risk may be inconsistent")

        if manipulation > 0.7 and politeness > 0.8:
            issues.append(
                "High manipulation with high politeness may indicate "
                "velvet glove approach"
            )

        if risk > 8.0 and sentiment > 0.3:
            issues.append(
                "High risk with positive sentiment may indicate strategic framing"
            )

        if not issues:
            status = ValidationStatus.PASS
            score = 1.0
            explanation = "Logical consistency check passed"
        else:
            status = ValidationStatus.WARNING
            score = 0.5
            explanation = f"Potential logical inconsistencies: {'; '.join(issues)}"

        return ValidationResult(
            check_type=ValidationCheckType.LOGICAL,
            status=status,
            score=score,
            explanation=explanation,
        )

    def _calculate_overall_result(
        self, validation_results: list[ValidationResult]
    ) -> FailCheckResult:
        """Calculate overall validation result.

        Args:
            validation_results: List of individual validation results

        Returns:
            Overall fail check result
        """
        pass_count = sum(
            1 for r in validation_results if r.status == ValidationStatus.PASS
        )
        fail_count = sum(
            1 for r in validation_results if r.status == ValidationStatus.FAIL
        )
        warning_count = sum(
            1 for r in validation_results if r.status == ValidationStatus.WARNING
        )
        total_checks = len(validation_results)

        # Calculate weighted health score
        weighted_scores = []
        for result in validation_results:
            weight = self.check_weights.get(result.check_type, 0.1)
            weighted_scores.append(result.score * weight)

        health_score = sum(weighted_scores) if weighted_scores else 0.0

        # Determine overall status
        if fail_count == 0:
            overall_status = ValidationStatus.PASS
        elif fail_count > total_checks * 0.3:  # More than 30% fails
            overall_status = ValidationStatus.FAIL
        else:
            overall_status = ValidationStatus.WARNING

        # Collect fail reasons and recommendations
        fail_reasons = [
            r.explanation
            for r in validation_results
            if r.status == ValidationStatus.FAIL
        ]
        recommendations = self._generate_recommendations(validation_results)

        return FailCheckResult(
            overall_status=overall_status,
            pass_count=pass_count,
            fail_count=fail_count,
            warning_count=warning_count,
            total_checks=total_checks,
            health_score=health_score,
            validation_results=validation_results,
            fail_reasons=fail_reasons,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self, validation_results: list[ValidationResult]
    ) -> list[str]:
        """Generate recommendations based on validation results.

        Args:
            validation_results: Validation results

        Returns:
            List of recommendations
        """
        recommendations = []

        # Analyze failure patterns
        failed_checks = [
            r for r in validation_results if r.status == ValidationStatus.FAIL
        ]

        if failed_checks:
            failed_types = [r.check_type for r in failed_checks]

            if ValidationCheckType.SENTIMENT in failed_types:
                recommendations.append(
                    "Review sentiment analysis parameters and training data"
                )

            if ValidationCheckType.RISK in failed_types:
                recommendations.append("Adjust risk assessment thresholds and criteria")

            if ValidationCheckType.HEDGING in failed_types:
                recommendations.append("Refine hedging language detection patterns")

            if ValidationCheckType.MANIPULATION in failed_types:
                recommendations.append("Update manipulation detection algorithms")

            if ValidationCheckType.QUALITY in failed_types:
                recommendations.append(
                    "Improve AI model output formatting and completeness"
                )

        # General recommendations
        if len(failed_checks) > 3:
            recommendations.append(
                "Consider retraining AI model with updated diplomatic "
                "discourse examples"
            )

        warning_checks = [
            r for r in validation_results if r.status == ValidationStatus.WARNING
        ]
        if len(warning_checks) > len(failed_checks):
            recommendations.append(
                "Monitor warning patterns and adjust validation thresholds"
            )

        return recommendations
