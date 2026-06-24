"""Model Registry - Manages model versions and deployment status.

Handles registration, promotion, and deprecation of model versions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class ModelVersion(BaseModel):
    """Model version schema."""

    version_id: uuid.UUID
    model_type: str  # "weight_set" | "spacy_ner" | "prompt_version"
    version_tag: str  # e.g. "v2.3.1"
    artifacts_path: str  # local path or S3 key
    status: str  # "shadow" | "production" | "deprecated"
    deployed_at: datetime
    metrics: dict  # F1, correction_rate, etc.


class ModelRegistry:
    """Registry for managing model versions and deployment status."""

    def __init__(self, session_factory):
        """Initialize model registry.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self.session_factory = session_factory

    async def register_model(
        self,
        model_type: str,
        version_tag: str,
        artifacts_path: str,
        metrics: dict[str, Any],
    ) -> ModelVersion:
        """Register a new model version.

        Args:
            model_type: Type of model (weight_set, spacy_ner, prompt_version)
            version_tag: Version tag (e.g., "v2.3.1")
            artifacts_path: Path to model artifacts
            metrics: Model performance metrics

        Returns:
            Registered ModelVersion
        """
        try:
            version = ModelVersion(
                version_id=uuid.uuid4(),
                model_type=model_type,
                version_tag=version_tag,
                artifacts_path=artifacts_path,
                status="shadow",
                deployed_at=datetime.now(timezone.utc),
                metrics=metrics,
            )

            # Persist to database
            await self._persist_version(version)

            logger.info(
                "model_registered",
                version_id=version.version_id,
                model_type=model_type,
                version_tag=version_tag,
            )

            return version

        except Exception as e:
            logger.error("model_registration_failed", error=str(e))
            raise

    async def get_production_version(self, model_type: str) -> ModelVersion | None:
        """Get current production version for a model type.

        Args:
            model_type: Type of model

        Returns:
            Production ModelVersion or None
        """
        try:
            async with self.session_factory():
                # Query model_versions table for production status
                # For now, return placeholder
                return None

        except Exception as e:
            logger.error("get_production_version_failed", error=str(e))
            return None

    async def get_shadow_version(self, model_type: str) -> ModelVersion | None:
        """Get current shadow version for a model type.

        Args:
            model_type: Type of model

        Returns:
            Shadow ModelVersion or None
        """
        try:
            async with self.session_factory():
                # Query model_versions table for shadow status
                # For now, return placeholder
                return None

        except Exception as e:
            logger.error("get_shadow_version_failed", error=str(e))
            return None

    async def promote_shadow_to_production(self, shadow_version_id: uuid.UUID) -> None:
        """Promote shadow version to production.

        Args:
            shadow_version_id: ID of shadow version to promote
        """
        try:
            async with self.session_factory():
                # Get shadow version
                shadow_version = await self._get_version_by_id(shadow_version_id)
                if not shadow_version:
                    raise ValueError(f"Shadow version {shadow_version_id} not found")

                # Get current production version
                production_version = await self.get_production_version(
                    shadow_version.model_type
                )

                # Deprecate old production version
                if production_version:
                    await self.deprecate_version(production_version.version_id)

                # Promote shadow to production
                shadow_version.status = "production"
                await self._update_version(shadow_version)

                logger.info(
                    "shadow_promoted_to_production",
                    version_id=shadow_version_id,
                    model_type=shadow_version.model_type,
                )

        except Exception as e:
            logger.error("promote_shadow_failed", error=str(e))
            raise

    async def deprecate_version(self, version_id: uuid.UUID) -> None:
        """Deprecate a model version.

        Args:
            version_id: ID of version to deprecate
        """
        try:
            async with self.session_factory():
                # Update version status to deprecated
                # For now, just log
                logger.info("version_deprecated", version_id=version_id)

        except Exception as e:
            logger.error("deprecate_version_failed", error=str(e))
            raise

    async def _persist_version(self, version: ModelVersion) -> None:
        """Persist model version to database.

        Args:
            version: ModelVersion to persist
        """
        try:
            # Insert into model_versions table
            # For now, just log
            logger.info("persist_model_version", version_id=version.version_id)
        except Exception as e:
            logger.error("persist_version_failed", error=str(e))

    async def _get_version_by_id(self, version_id: uuid.UUID) -> ModelVersion | None:
        """Get model version by ID.

        Args:
            version_id: Version ID

        Returns:
            ModelVersion or None
        """
        try:
            # Query model_versions table
            # For now, return None
            return None
        except Exception as e:
            logger.error("get_version_by_id_failed", error=str(e))
            return None

    async def _update_version(self, version: ModelVersion) -> None:
        """Update model version in database.

        Args:
            version: ModelVersion to update
        """
        try:
            # Update model_versions table
            # For now, just log
            logger.info("update_model_version", version_id=version.version_id)
        except Exception as e:
            logger.error("update_version_failed", error=str(e))
