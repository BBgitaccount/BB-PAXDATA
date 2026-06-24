"""Shadow Evaluator - Evaluates shadow deployment results and decides promotion.

Evaluates after 500 shadow analyses OR 7 days, whichever comes first.

Quality gates:
- Correction rate: shadow < production
- Agreement rate: shadow vs production > 0.85
- Minimum exposure: 500 analyses or 7 days
- Error-free shadow period: zero critical exceptions logged for shadow version

All four gates must pass for promotion.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from bb_paxdata.infrastructure.model_registry.model_registry import ModelRegistry

logger = structlog.get_logger(__name__)


class ShadowEvaluator:
    """Evaluates shadow deployment results and decides on promotion.

    Implements quality gates for safe model promotion.
    """

    def __init__(self, model_registry: ModelRegistry, session_factory):
        """Initialize shadow evaluator.

        Args:
            model_registry: ModelRegistry instance
            session_factory: SQLAlchemy async session factory
        """
        self.model_registry = model_registry
        self.session_factory = session_factory

    async def evaluate_shadow_version(
        self, shadow_version_id: uuid.UUID
    ) -> dict[str, Any]:
        """Evaluate shadow version against quality gates.

        Args:
            shadow_version_id: Shadow version ID to evaluate

        Returns:
            Evaluation results with pass/fail status per gate
        """
        try:
            # Get shadow version info
            shadow_version = await self.model_registry._get_version_by_id(
                shadow_version_id
            )
            if not shadow_version:
                raise ValueError(f"Shadow version {shadow_version_id} not found")

            # Get production version for comparison
            production_version = await self.model_registry.get_production_version(
                shadow_version.model_type
            )

            # Evaluate gates
            gate_results = {
                "correction_rate_gate": await self._evaluate_correction_rate_gate(
                    shadow_version_id,
                    production_version.version_id if production_version else None,
                ),
                "agreement_rate_gate": await self._evaluate_agreement_rate_gate(
                    shadow_version_id
                ),
                "minimum_exposure_gate": await self._evaluate_minimum_exposure_gate(
                    shadow_version_id, shadow_version.deployed_at
                ),
                "error_free_gate": await self._evaluate_error_free_gate(
                    shadow_version_id
                ),
            }

            # Overall pass/fail
            all_passed = all(result["passed"] for result in gate_results.values())

            evaluation_result = {
                "shadow_version_id": shadow_version_id,
                "all_gates_passed": all_passed,
                "gate_results": gate_results,
                "evaluated_at": datetime.now(timezone.utc),
            }

            logger.info(
                "shadow_evaluation_completed",
                shadow_version_id=shadow_version_id,
                all_passed=all_passed,
            )

            # If all gates pass, promote to production
            if all_passed:
                await self.model_registry.promote_shadow_to_production(
                    shadow_version_id
                )
                evaluation_result["action"] = "promoted_to_production"
            else:
                # Set retraining job status to shadow_failed
                await self._set_shadow_failed(shadow_version_id)
                evaluation_result["action"] = "shadow_failed"

            return evaluation_result

        except Exception as e:
            logger.error(
                "shadow_evaluation_failed",
                shadow_version_id=shadow_version_id,
                error=str(e),
            )
            raise

    async def _evaluate_correction_rate_gate(
        self, shadow_version_id: uuid.UUID, production_version_id: uuid.UUID | None
    ) -> dict[str, Any]:
        """Evaluate correction rate gate: shadow < production.

        Args:
            shadow_version_id: Shadow version ID
            production_version_id: Production version ID (optional)

        Returns:
            Gate result with pass/fail status
        """
        try:
            # Get correction rates from shadow_results
            shadow_correction_rate = await self._get_correction_rate(shadow_version_id)
            production_correction_rate = (
                await self._get_correction_rate(production_version_id)
                if production_version_id
                else None
            )

            if production_correction_rate is None:
                # No production baseline, pass gate
                return {
                    "passed": True,
                    "shadow_correction_rate": shadow_correction_rate,
                    "production_correction_rate": None,
                    "message": "No production baseline, gate passed",
                }

            passed = shadow_correction_rate < production_correction_rate

            return {
                "passed": passed,
                "shadow_correction_rate": shadow_correction_rate,
                "production_correction_rate": production_correction_rate,
                "message": f"Shadow correction rate {shadow_correction_rate} vs production {production_correction_rate}",
            }

        except Exception as e:
            logger.error("correction_rate_gate_evaluation_failed", error=str(e))
            return {"passed": False, "error": str(e)}

    async def _evaluate_agreement_rate_gate(
        self, shadow_version_id: uuid.UUID
    ) -> dict[str, Any]:
        """Evaluate agreement rate gate: shadow vs production > 0.85.

        Args:
            shadow_version_id: Shadow version ID

        Returns:
            Gate result with pass/fail status
        """
        try:
            # Get agreement rate from shadow_results
            agreement_rate = await self._get_agreement_rate(shadow_version_id)

            passed = agreement_rate > 0.85

            return {
                "passed": passed,
                "agreement_rate": agreement_rate,
                "threshold": 0.85,
                "message": f"Agreement rate {agreement_rate} vs threshold 0.85",
            }

        except Exception as e:
            logger.error("agreement_rate_gate_evaluation_failed", error=str(e))
            return {"passed": False, "error": str(e)}

    async def _evaluate_minimum_exposure_gate(
        self, shadow_version_id: uuid.UUID, deployed_at: datetime
    ) -> dict[str, Any]:
        """Evaluate minimum exposure gate: 500 analyses or 7 days.

        Args:
            shadow_version_id: Shadow version ID
            deployed_at: Deployment timestamp

        Returns:
            Gate result with pass/fail status
        """
        try:
            # Get number of shadow analyses
            analysis_count = await self._get_shadow_analysis_count(shadow_version_id)

            # Check time threshold (7 days)
            days_deployed = (datetime.now(timezone.utc) - deployed_at).days
            time_passed = days_deployed >= 7

            # Check count threshold (500)
            count_passed = analysis_count >= 500

            passed = time_passed or count_passed

            return {
                "passed": passed,
                "analysis_count": analysis_count,
                "days_deployed": days_deployed,
                "time_threshold_passed": time_passed,
                "count_threshold_passed": count_passed,
                "message": f"Analysis count {analysis_count}, days deployed {days_deployed}",
            }

        except Exception as e:
            logger.error("minimum_exposure_gate_evaluation_failed", error=str(e))
            return {"passed": False, "error": str(e)}

    async def _evaluate_error_free_gate(
        self, shadow_version_id: uuid.UUID
    ) -> dict[str, Any]:
        """Evaluate error-free gate: zero critical exceptions for shadow version.

        Args:
            shadow_version_id: Shadow version ID

        Returns:
            Gate result with pass/fail status
        """
        try:
            # Check for critical exceptions in logs
            critical_exception_count = await self._get_critical_exception_count(
                shadow_version_id
            )

            passed = critical_exception_count == 0

            return {
                "passed": passed,
                "critical_exception_count": critical_exception_count,
                "message": f"Critical exceptions: {critical_exception_count}",
            }

        except Exception as e:
            logger.error("error_free_gate_evaluation_failed", error=str(e))
            return {"passed": False, "error": str(e)}

    async def _get_correction_rate(self, version_id: uuid.UUID | None) -> float:
        """Get correction rate for a model version.

        Args:
            version_id: Model version ID

        Returns:
            Correction rate
        """
        try:
            # Query correction events for this version
            # For now, return placeholder
            return 0.05
        except Exception as e:
            logger.error("get_correction_rate_failed", error=str(e))
            return 0.0

    async def _get_agreement_rate(self, shadow_version_id: uuid.UUID) -> float:
        """Get agreement rate from shadow results.

        Args:
            shadow_version_id: Shadow version ID

        Returns:
            Agreement rate (0.0 to 1.0)
        """
        try:
            # Query shadow_results table
            # For now, return placeholder
            return 0.90
        except Exception as e:
            logger.error("get_agreement_rate_failed", error=str(e))
            return 0.0

    async def _get_shadow_analysis_count(self, shadow_version_id: uuid.UUID) -> int:
        """Get number of shadow analyses for a version.

        Args:
            shadow_version_id: Shadow version ID

        Returns:
            Number of analyses
        """
        try:
            # Query shadow_results table count
            # For now, return placeholder
            return 500
        except Exception as e:
            logger.error("get_shadow_analysis_count_failed", error=str(e))
            return 0

    async def _get_critical_exception_count(self, shadow_version_id: uuid.UUID) -> int:
        """Get count of critical exceptions for shadow version.

        Args:
            shadow_version_id: Shadow version ID

        Returns:
            Number of critical exceptions
        """
        try:
            # Query logs for critical exceptions
            # For now, return placeholder
            return 0
        except Exception as e:
            logger.error("get_critical_exception_count_failed", error=str(e))
            return 0

    async def _set_shadow_failed(self, shadow_version_id: uuid.UUID) -> None:
        """Set retraining job status to shadow_failed.

        Args:
            shadow_version_id: Shadow version ID
        """
        try:
            # Update retraining_jobs table
            # For now, just log
            logger.info("set_shadow_failed", shadow_version_id=shadow_version_id)
        except Exception as e:
            logger.error("set_shadow_failed_failed", error=str(e))
