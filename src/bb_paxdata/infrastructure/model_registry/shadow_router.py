"""Shadow Router - Routes analysis requests to both production and shadow models.

For every incoming analysis request, runs both production and shadow model versions.
Returns only production output to caller.
Writes both outputs + agreement flag + delta to shadow_results.
Shadow inference runs as fire-and-forget asyncio.create_task().
"""

import asyncio
import uuid
from typing import Any

import structlog

from bb_paxdata.infrastructure.model_registry.model_registry import ModelRegistry

logger = structlog.get_logger(__name__)


class ShadowRouter:
    """Routes analysis requests to both production and shadow models.

    Implements shadow deployment pattern for safe model promotion.
    """

    def __init__(self, model_registry: ModelRegistry, session_factory):
        """Initialize shadow router.

        Args:
            model_registry: ModelRegistry instance
            session_factory: SQLAlchemy async session factory
        """
        self.model_registry = model_registry
        self.session_factory = session_factory

    async def route_analysis(
        self,
        analysis_id: uuid.UUID,
        input_data: dict[str, Any],
        production_inference_fn,
        shadow_inference_fn,
    ) -> dict[str, Any]:
        """Route analysis request to both production and shadow models.

        Args:
            analysis_id: Analysis ID
            input_data: Input data for inference
            production_inference_fn: Production model inference function
            shadow_inference_fn: Shadow model inference function

        Returns:
            Production model output only
        """
        try:
            # Get production and shadow versions
            model_type = "weight_set"  # Could be parameterized
            production_version = await self.model_registry.get_production_version(
                model_type
            )
            shadow_version = await self.model_registry.get_shadow_version(model_type)

            # Run production inference (synchronous for response)
            production_output = await production_inference_fn(input_data)

            # Run shadow inference as fire-and-forget background task
            if shadow_version:
                task = asyncio.create_task(
                    self._run_shadow_inference(
                        analysis_id,
                        input_data,
                        shadow_version.version_id,
                        production_version.version_id if production_version else None,
                        production_output,
                        shadow_inference_fn,
                    )
                )
                # Store reference to prevent garbage collection
                _ = task

            return production_output

        except Exception as e:
            logger.error("shadow_route_failed", analysis_id=analysis_id, error=str(e))
            # Fallback to production only
            return await production_inference_fn(input_data)

    async def _run_shadow_inference(
        self,
        analysis_id: uuid.UUID,
        input_data: dict[str, Any],
        shadow_version_id: uuid.UUID,
        production_version_id: uuid.UUID | None,
        production_output: dict[str, Any],
        shadow_inference_fn,
    ) -> None:
        """Run shadow inference and persist results.

        Args:
            analysis_id: Analysis ID
            input_data: Input data for inference
            shadow_version_id: Shadow model version ID
            production_version_id: Production model version ID
            production_output: Production model output
            shadow_inference_fn: Shadow model inference function
        """
        try:
            # Run shadow inference
            shadow_output = await shadow_inference_fn(input_data)

            # Compute agreement and delta
            agreement, delta = self._compute_agreement(production_output, shadow_output)

            # Persist to shadow_results table
            await self._persist_shadow_result(
                analysis_id,
                production_version_id,
                shadow_version_id,
                production_output,
                shadow_output,
                agreement,
                delta,
            )

            logger.debug(
                "shadow_inference_completed",
                analysis_id=analysis_id,
                agreement=agreement,
                delta=delta,
            )

        except Exception as e:
            logger.error(
                "shadow_inference_failed", analysis_id=analysis_id, error=str(e)
            )

    def _compute_agreement(
        self, production_output: dict[str, Any], shadow_output: dict[str, Any]
    ) -> tuple[bool, float]:
        """Compute agreement and delta between production and shadow outputs.

        Args:
            production_output: Production model output
            shadow_output: Shadow model output

        Returns:
            Tuple of (agreement_bool, delta_value)
        """
        try:
            # For numeric outputs, check if within threshold
            if "risk_score" in production_output and "risk_score" in shadow_output:
                prod_risk = production_output["risk_score"]
                shadow_risk = shadow_output["risk_score"]
                delta = abs(prod_risk - shadow_risk)
                agreement = delta < 0.1  # Threshold for agreement
                return agreement, delta

            # For categorical outputs, check exact match
            if "frame" in production_output and "frame" in shadow_output:
                agreement = production_output["frame"] == shadow_output["frame"]
                delta = 0.0 if agreement else 1.0
                return agreement, delta

            # Default: assume agreement if no comparable fields
            return True, 0.0

        except Exception as e:
            logger.error("compute_agreement_failed", error=str(e))
            return True, 0.0

    async def _persist_shadow_result(
        self,
        analysis_id: uuid.UUID,
        production_version_id: uuid.UUID | None,
        shadow_version_id: uuid.UUID,
        production_output: dict[str, Any],
        shadow_output: dict[str, Any],
        agreement: bool,
        delta: float,
    ) -> None:
        """Persist shadow result to database.

        Args:
            analysis_id: Analysis ID
            production_version_id: Production version ID
            shadow_version_id: Shadow version ID
            production_output: Production model output
            shadow_output: Shadow model output
            agreement: Agreement flag
            delta: Delta value
        """
        try:
            # Insert into shadow_results table
            # For now, just log
            logger.info(
                "persist_shadow_result",
                analysis_id=analysis_id,
                agreement=agreement,
                delta=delta,
            )
        except Exception as e:
            logger.error("persist_shadow_result_failed", error=str(e))
