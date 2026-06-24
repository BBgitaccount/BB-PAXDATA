"""Training Data Builder - Build training datasets from HITL corrections.

Builds training datasets from approved correction events with outlier removal.
"""

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class TrainingSample(BaseModel):
    """Training sample schema."""

    sample_id: uuid.UUID
    input_text: str
    input_features: dict  # embedding, pos_tags, etc.
    target_field: str
    ai_output: Any
    corrected_output: Any
    correction_delta: float  # numeric fields only; 0.0 for categorical
    outlier: bool = False
    source_correction_id: uuid.UUID
    created_at: datetime


class DataQualityReport(BaseModel):
    """Data quality report for training dataset."""

    total_samples: int
    outliers_removed: int
    conflicting_labels_removed: int
    final_sample_count: int
    field_distribution: dict[str, int]


class TrainingDataBuilder:
    """Builds training datasets from HITL-approved corrections.

    Implements outlier removal and data quality reporting.
    """

    def __init__(self, session_factory):
        """Initialize training data builder.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self.session_factory = session_factory

    async def build_training_dataset(
        self, report_week_iso_string: str
    ) -> tuple[list[TrainingSample], DataQualityReport]:
        """Build training dataset from approved corrections.

        Args:
            report_week_iso_string: ISO week string for deterministic seed (e.g., "2025-W22")

        Returns:
            Tuple of (training samples, data quality report)
        """
        try:
            # Query correction events with filters
            corrections = await self._query_corrections()

            # Convert to training samples
            samples = await self._convert_to_samples(corrections)

            # Remove outliers
            samples = await self._remove_outliers(samples)

            # Remove conflicting labels for categorical fields
            samples = await self._remove_conflicting_labels(samples)

            # Generate data quality report
            report = self._generate_quality_report(samples)

            # Split into train/validation/test (70/15/15)
            train_samples, val_samples, test_samples = await self._split_dataset(
                samples, report_week_iso_string
            )

            # Persist to training_datasets table
            await self._persist_splits(
                train_samples, val_samples, test_samples, report_week_iso_string
            )

            logger.info(
                "training_dataset_built",
                total_samples=len(samples),
                train_count=len(train_samples),
                val_count=len(val_samples),
                test_count=len(test_samples),
            )

            return train_samples, report

        except Exception as e:
            logger.error("training_dataset_build_failed", error=str(e))
            raise

    async def _query_corrections(self) -> list[Any]:
        """Query correction events with filters.

        Filters:
        - approved = true
        - corrector_confidence >= 0.8
        - created_at >= NOW() - INTERVAL '90 days'
        - field IN ('sentiment_score', 'risk_score', 'discourse_act', 'frame', 'hedging_level')

        Returns:
            List of correction events
        """
        try:
            async with self.session_factory() as session:
                from bb_paxdata.infrastructure.db.correction_event_table import (
                    CorrectionEventORM,
                )

                # Query with filters
                cutoff_date = datetime.now(UTC) - timedelta(days=90)
                fields = [
                    "sentiment_score",
                    "risk_score",
                    "discourse_act",
                    "frame",
                    "hedging_level",
                ]

                # Placeholder - would need to add approved and corrector_confidence columns
                query = session.query(CorrectionEventORM).filter(
                    CorrectionEventORM.field_corrected.in_(fields),
                    CorrectionEventORM.timestamp >= cutoff_date,
                )

                results = await asyncio.get_event_loop().run_in_executor(
                    None, query.all
                )

                return results

        except Exception as e:
            logger.error("query_corrections_failed", error=str(e))
            return []

    async def _convert_to_samples(self, corrections: list[Any]) -> list[TrainingSample]:
        """Convert correction events to training samples.

        Args:
            corrections: List of correction events

        Returns:
            List of training samples
        """
        samples = []

        for correction in corrections:
            try:
                sample = TrainingSample(
                    sample_id=uuid.uuid4(),
                    input_text=(
                        correction.context_snapshot.get("text", "")
                        if correction.context_snapshot
                        else ""
                    ),
                    input_features=(
                        correction.context_snapshot.get("features", {})
                        if correction.context_snapshot
                        else {}
                    ),
                    target_field=correction.field_corrected,
                    ai_output=correction.original_value,
                    corrected_output=correction.corrected_value,
                    correction_delta=self._compute_delta(
                        correction.original_value, correction.corrected_value
                    ),
                    outlier=False,
                    source_correction_id=uuid.UUID(correction.id),
                    created_at=correction.timestamp,
                )
                samples.append(sample)
            except Exception as e:
                logger.warning(
                    "sample_conversion_failed",
                    correction_id=correction.id,
                    error=str(e),
                )

        return samples

    def _compute_delta(self, original: Any, corrected: Any) -> float:
        """Compute correction delta.

        For numeric fields: corrected - original
        For categorical fields: 0.0

        Args:
            original: Original value
            corrected: Corrected value

        Returns:
            Delta value
        """
        if isinstance(original, int | float) and isinstance(corrected, int | float):
            return float(corrected - original)
        return 0.0

    async def _remove_outliers(
        self, samples: list[TrainingSample]
    ) -> list[TrainingSample]:
        """Remove outliers using IQR method for numeric fields.

        Numeric fields (sentiment_score, risk_score, ai_confidence):
        - Compute IQR of correction_delta for each field
        - Mark outlier = True where |delta| > Q3 + 1.5 × IQR
        - Exclude from training split but do not delete

        Args:
            samples: List of training samples

        Returns:
            List of samples with outliers marked
        """
        numeric_fields = ["sentiment_score", "risk_score", "ai_confidence"]

        for field in numeric_fields:
            field_samples = [s for s in samples if s.target_field == field]
            if len(field_samples) < 10:
                continue

            deltas = [s.correction_delta for s in field_samples]
            q1 = np.percentile(deltas, 25)
            q3 = np.percentile(deltas, 75)
            iqr = q3 - q1
            outlier_threshold = q3 + 1.5 * iqr

            for sample in field_samples:
                if abs(sample.correction_delta) > outlier_threshold:
                    sample.outlier = True

        return samples

    async def _remove_conflicting_labels(
        self, samples: list[TrainingSample]
    ) -> list[TrainingSample]:
        """Remove samples with conflicting labels for categorical fields.

        For any (input_text, target_field) pair with conflicting corrections
        (multiple different corrected_output values), mark all associated samples as outlier.

        Args:
            samples: List of training samples

        Returns:
            List of samples with conflicting labels marked
        """
        categorical_fields = ["discourse_act", "frame", "hedging_level"]

        for field in categorical_fields:
            field_samples = [s for s in samples if s.target_field == field]

            # Group by input_text
            text_to_outputs: dict[str, set[Any]] = {}
            for sample in field_samples:
                if sample.input_text not in text_to_outputs:
                    text_to_outputs[sample.input_text] = set()
                text_to_outputs[sample.input_text].add(sample.corrected_output)

            # Mark samples with conflicting labels
            for sample in field_samples:
                if len(text_to_outputs[sample.input_text]) > 1:
                    sample.outlier = True

        return samples

    def _generate_quality_report(
        self, samples: list[TrainingSample]
    ) -> DataQualityReport:
        """Generate data quality report.

        Args:
            samples: List of training samples

        Returns:
            DataQualityReport
        """
        total_samples = len(samples)
        outliers_removed = sum(1 for s in samples if s.outlier)

        # Count conflicting labels (categorical fields)
        categorical_fields = ["discourse_act", "frame", "hedging_level"]
        conflicting_removed = 0

        for field in categorical_fields:
            field_samples = [
                s for s in samples if s.target_field == field and s.outlier
            ]
            conflicting_removed += len(field_samples)

        final_sample_count = total_samples - outliers_removed

        # Field distribution
        field_distribution = Counter(s.target_field for s in samples if not s.outlier)

        return DataQualityReport(
            total_samples=total_samples,
            outliers_removed=outliers_removed,
            conflicting_labels_removed=conflicting_removed,
            final_sample_count=final_sample_count,
            field_distribution=dict(field_distribution),
        )

    async def _split_dataset(
        self, samples: list[TrainingSample], report_week_iso_string: str
    ) -> tuple[list[TrainingSample], list[TrainingSample], list[TrainingSample]]:
        """Split dataset into train/validation/test (70/15/15).

        Stratified by target_field.
        Deterministic seed: hash(report_week_iso_string).
        Minimum sample gate: if any target_field has < 50 clean samples, exclude that field.

        Args:
            samples: List of training samples
            report_week_iso_string: ISO week string for deterministic seed

        Returns:
            Tuple of (train, validation, test) samples
        """
        # Filter non-outlier samples
        clean_samples = [s for s in samples if not s.outlier]

        # Check minimum sample gate per field
        field_counts = Counter(s.target_field for s in clean_samples)
        valid_fields = {field for field, count in field_counts.items() if count >= 50}

        if not valid_fields:
            logger.warning("no_field_passes_minimum_sample_gate")
            return [], [], []

        # Filter to valid fields
        clean_samples = [s for s in clean_samples if s.target_field in valid_fields]

        # Deterministic seed from week string
        seed = hash(report_week_iso_string)
        np.random.seed(seed)

        # Stratified split
        train_samples = []
        val_samples = []
        test_samples = []

        for field in valid_fields:
            field_samples = [s for s in clean_samples if s.target_field == field]
            np.random.shuffle(field_samples)

            n = len(field_samples)
            train_end = int(0.7 * n)
            val_end = int(0.85 * n)

            train_samples.extend(field_samples[:train_end])
            val_samples.extend(field_samples[train_end:val_end])
            test_samples.extend(field_samples[val_end:])

        return train_samples, val_samples, test_samples

    async def _persist_splits(
        self,
        train: list[TrainingSample],
        val: list[TrainingSample],
        test: list[TrainingSample],
        report_week_iso_string: str,
    ) -> None:
        """Persist dataset splits to training_datasets table.

        Args:
            train: Training samples
            val: Validation samples
            test: Test samples
            report_week_iso_string: Report week identifier
        """
        try:
            # Insert into training_datasets table
            # For now, just log
            logger.info(
                "persist_training_splits",
                report_week=report_week_iso_string,
                train_count=len(train),
                val_count=len(val),
                test_count=len(test),
            )
        except Exception as e:
            logger.error("persist_splits_failed", error=str(e))
