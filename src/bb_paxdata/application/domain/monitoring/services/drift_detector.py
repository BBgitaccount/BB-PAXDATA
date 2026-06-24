"""Drift Detector Service - Detects data, concept, and prediction drift.

Runs as an AsyncIO background task registered at FastAPI startup.
Execution interval: every 6 hours.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel
from sklearn.decomposition import PCA

from bb_paxdata.application.domain.monitoring.services.drift_metrics_service import (
    DriftScore,
    compute_ks,
    compute_psi,
    compute_wasserstein,
)
from bb_paxdata.config.drift_config import DriftConfig
from bb_paxdata.config.settings import get_settings

logger = structlog.get_logger(__name__)


class DataDriftAlert(BaseModel):
    """Alert for data drift detection."""

    alert_type: str = "data_drift"
    field: str = "embedding_vector"
    detected_at: datetime
    baseline_window_start: datetime
    baseline_window_end: datetime
    current_window_start: datetime
    current_window_end: datetime
    ks_x_score: float
    ks_x_severity: str
    ks_y_score: float
    ks_y_severity: str
    wasserstein_x_score: float
    wasserstein_x_severity: str
    wasserstein_y_score: float
    wasserstein_y_severity: str


class ConceptDriftAlert(BaseModel):
    """Alert for concept drift detection."""

    alert_type: str = "concept_drift"
    field: str
    detected_at: datetime
    correction_rate_current: float
    correction_rate_baseline: float
    psi_score: float
    severity: str


class PredictionDriftAlert(BaseModel):
    """Alert for prediction drift detection."""

    alert_type: str = "prediction_drift"
    field: str
    detected_at: datetime
    metrics: list[DriftScore]
    warning_count: int
    critical_count: str


class DriftDetectorService:
    """Service for detecting data, concept, and prediction drift.

    Runs as a background task every 6 hours.
    """

    def __init__(self, session_factory, config: DriftConfig | None = None):
        """Initialize drift detector service.

        Args:
            session_factory: SQLAlchemy async session factory
            config: Drift configuration (uses defaults if None)
        """
        self.session_factory = session_factory
        self.config = config or DriftConfig()
        self.settings = get_settings()

    async def run_detection_cycle(self) -> list[Any]:
        """Run full drift detection cycle.

        Returns:
            List of all alerts generated during this cycle
        """
        alerts = []

        try:
            # Data drift detection
            data_drift_alerts = await self.detect_data_drift()
            alerts.extend(data_drift_alerts)

            # Concept drift detection
            concept_drift_alerts = await self.detect_concept_drift()
            alerts.extend(concept_drift_alerts)

            # Prediction drift detection
            prediction_drift_alerts = await self.detect_prediction_drift()
            alerts.extend(prediction_drift_alerts)

            logger.info(
                "drift_detection_cycle_completed",
                total_alerts=len(alerts),
                data_drift=len(data_drift_alerts),
                concept_drift=len(concept_drift_alerts),
                prediction_drift=len(prediction_drift_alerts),
            )

        except Exception as e:
            logger.error("drift_detection_cycle_failed", error=str(e))

        return alerts

    async def detect_data_drift(self) -> list[DataDriftAlert]:
        """Detect data drift in embedding distribution.

        Data source: Sentence.embedding_vector column.
        Baseline window = embeddings from last 30 days.
        Current window = embeddings from last 7 days.
        Reduce to 2D via PCA(n_components=2).
        Run KS and Wasserstein on both PCA dimensions.
        Produce DataDriftAlert only if drift is detected in BOTH dimensions.

        Returns:
            List of data drift alerts
        """
        alerts = []

        try:
            async with self.session_factory() as session:
                # Query baseline embeddings (last 30 days)
                baseline_end = datetime.now(timezone.utc)
                baseline_start = baseline_end - timedelta(
                    days=self.config.baseline_window_days
                )

                # Query current embeddings (last 7 days)
                current_end = baseline_end
                current_start = baseline_end - timedelta(
                    days=self.config.concept_drift_window_days
                )

                # Get embeddings from database
                baseline_embeddings = await self._get_embeddings(
                    session, baseline_start, baseline_end
                )
                current_embeddings = await self._get_embeddings(
                    session, current_start, current_end
                )

                if len(baseline_embeddings) < 100 or len(current_embeddings) < 100:
                    logger.warning(
                        "insufficient_embeddings_for_drift_detection",
                        baseline_count=len(baseline_embeddings),
                        current_count=len(current_embeddings),
                    )
                    return alerts

                # Convert to numpy arrays
                baseline_arr = np.array(baseline_embeddings)
                current_arr = np.array(current_embeddings)

                # Reduce to 2D via PCA
                pca = PCA(n_components=2)

                # Fit on baseline and transform both
                baseline_2d = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: pca.fit_transform(baseline_arr)
                )
                current_2d = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: pca.transform(current_arr)
                )

                # Extract x and y dimensions
                baseline_x = baseline_2d[:, 0]
                baseline_y = baseline_2d[:, 1]
                current_x = current_2d[:, 0]
                current_y = current_2d[:, 1]

                # Run KS and Wasserstein on both dimensions
                ks_x = compute_ks(
                    baseline_x,
                    current_x,
                    "embedding_pca_x",
                    baseline_start,
                    baseline_end,
                    current_start,
                    current_end,
                )
                ks_y = compute_ks(
                    baseline_y,
                    current_y,
                    "embedding_pca_y",
                    baseline_start,
                    baseline_end,
                    current_start,
                    current_end,
                )
                wasserstein_x = compute_wasserstein(
                    baseline_x,
                    current_x,
                    "embedding_pca_x",
                    baseline_start,
                    baseline_end,
                    current_start,
                    current_end,
                )
                wasserstein_y = compute_wasserstein(
                    baseline_y,
                    current_y,
                    "embedding_pca_y",
                    baseline_start,
                    baseline_end,
                    current_start,
                    current_end,
                )

                # Check if drift detected in BOTH dimensions
                drift_detected = (
                    ks_x.severity != "stable" or wasserstein_x.severity != "stable"
                ) and (ks_y.severity != "stable" or wasserstein_y.severity != "stable")

                if drift_detected:
                    alert = DataDriftAlert(
                        field="embedding_vector",
                        detected_at=datetime.now(timezone.utc),
                        baseline_window_start=baseline_start,
                        baseline_window_end=baseline_end,
                        current_window_start=current_start,
                        current_window_end=current_end,
                        ks_x_score=ks_x.value,
                        ks_x_severity=ks_x.severity,
                        ks_y_score=ks_y.value,
                        ks_y_severity=ks_y.severity,
                        wasserstein_x_score=wasserstein_x.value,
                        wasserstein_x_severity=wasserstein_x.severity,
                        wasserstein_y_score=wasserstein_y.value,
                        wasserstein_y_severity=wasserstein_y.severity,
                    )
                    alerts.append(alert)
                    logger.warning("data_drift_detected", alert=alert.model_dump())

        except Exception as e:
            logger.error("data_drift_detection_failed", error=str(e))

        return alerts

    async def detect_concept_drift(self) -> list[ConceptDriftAlert]:
        """Detect concept drift via prediction/correction mismatch rate.

        Data source: correction_events table (learning BC).
        For each field in {sentiment_score, risk_score, discourse_act, frame, hedging_level}:
        - Compute correction_rate_current = corrections / total_analyses for last 7 days
        - Compute correction_rate_baseline = 8-week rolling rate
        - Run PSI comparing the two rates
        - If PSI > 0.2 for a field → emit ConceptDriftAlert

        Returns:
            List of concept drift alerts
        """
        alerts = []

        try:
            async with self.session_factory() as session:
                fields = [
                    "sentiment_score",
                    "risk_score",
                    "discourse_act",
                    "frame",
                    "hedging_level",
                ]

                current_end = datetime.now(timezone.utc)
                current_start = current_end - timedelta(
                    days=self.config.concept_drift_window_days
                )
                baseline_start = current_end - timedelta(days=56)  # 8 weeks

                for field in fields:
                    # Get correction rates
                    correction_rate_current = await self._get_correction_rate(
                        session, field, current_start, current_end
                    )
                    correction_rate_baseline = await self._get_correction_rate(
                        session, field, baseline_start, current_end
                    )

                    if (
                        correction_rate_current is None
                        or correction_rate_baseline is None
                    ):
                        continue

                    # Compute PSI on the two rates
                    baseline_arr = np.array([correction_rate_baseline])
                    current_arr = np.array([correction_rate_current])

                    psi_score = compute_psi(
                        baseline_arr,
                        current_arr,
                        field,
                        baseline_start,
                        current_end,
                        current_start,
                        current_end,
                    )

                    # Check if PSI > critical threshold
                    if psi_score.value > self.config.psi_critical_threshold:
                        alert = ConceptDriftAlert(
                            field=field,
                            detected_at=datetime.now(timezone.utc),
                            correction_rate_current=correction_rate_current,
                            correction_rate_baseline=correction_rate_baseline,
                            psi_score=psi_score.value,
                            severity=psi_score.severity,
                        )
                        alerts.append(alert)
                        logger.warning(
                            "concept_drift_detected", alert=alert.model_dump()
                        )

        except Exception as e:
            logger.error("concept_drift_detection_failed", error=str(e))

        return alerts

    async def detect_prediction_drift(self) -> list[PredictionDriftAlert]:
        """Detect prediction drift in model output distribution.

        Data source: analysis results table.
        Columns: sentiment_score, risk_score, ai_confidence, detected_at.
        Baseline = last 30 days of output values.
        Current = last 7 days.
        Run all four metrics (PSI, KL, KS, Wasserstein) per numerical field.
        If at least 2 metrics reach warning severity → emit PredictionDriftAlert.
        Persist all DriftScore results to drift_measurements table.

        Returns:
            List of prediction drift alerts
        """
        alerts = []

        try:
            async with self.session_factory() as session:
                fields = ["sentiment_score", "risk_score", "ai_confidence"]

                baseline_end = datetime.now(timezone.utc)
                baseline_start = baseline_end - timedelta(
                    days=self.config.baseline_window_days
                )
                current_end = baseline_end
                current_start = baseline_end - timedelta(
                    days=self.config.concept_drift_window_days
                )

                for field in fields:
                    # Get baseline and current values
                    baseline_values = await self._get_field_values(
                        session, field, baseline_start, baseline_end
                    )
                    current_values = await self._get_field_values(
                        session, field, current_start, current_end
                    )

                    if len(baseline_values) < 50 or len(current_values) < 50:
                        logger.warning(
                            "insufficient_values_for_prediction_drift",
                            field=field,
                            baseline_count=len(baseline_values),
                            current_count=len(current_values),
                        )
                        continue

                    baseline_arr = np.array(baseline_values)
                    current_arr = np.array(current_values)

                    # Run all four metrics
                    from bb_paxdata.application.domain.monitoring.services.drift_metrics_service import (
                        compute_kl,
                    )

                    psi = compute_psi(
                        baseline_arr,
                        current_arr,
                        field,
                        baseline_start,
                        baseline_end,
                        current_start,
                        current_end,
                    )
                    kl = compute_kl(
                        baseline_arr,
                        current_arr,
                        field,
                        baseline_start,
                        baseline_end,
                        current_start,
                        current_end,
                    )
                    ks = compute_ks(
                        baseline_arr,
                        current_arr,
                        field,
                        baseline_start,
                        baseline_end,
                        current_start,
                        current_end,
                    )
                    wasserstein = compute_wasserstein(
                        baseline_arr,
                        current_arr,
                        field,
                        baseline_start,
                        baseline_end,
                        current_start,
                        current_end,
                    )

                    # Persist all drift scores
                    await self._persist_drift_scores(
                        session, [psi, kl, ks, wasserstein]
                    )

                    # Check if at least 2 metrics reach warning severity
                    warning_count = sum(
                        1
                        for score in [psi, kl, ks, wasserstein]
                        if score.severity in ("warning", "critical")
                    )
                    critical_count = sum(
                        1
                        for score in [psi, kl, ks, wasserstein]
                        if score.severity == "critical"
                    )

                    if warning_count >= 2:
                        alert = PredictionDriftAlert(
                            field=field,
                            detected_at=datetime.now(timezone.utc),
                            metrics=[psi, kl, ks, wasserstein],
                            warning_count=warning_count,
                            critical_count=critical_count,
                        )
                        alerts.append(alert)
                        logger.warning(
                            "prediction_drift_detected", alert=alert.model_dump()
                        )

        except Exception as e:
            logger.error("prediction_drift_detection_failed", error=str(e))

        return alerts

    async def _get_embeddings(
        self, session, start: datetime, end: datetime
    ) -> list[list[float]]:
        """Get embedding vectors from database for given time window.

        Args:
            session: Database session
            start: Start of time window
            end: End of time window

        Returns:
            List of embedding vectors
        """
        try:
            from bb_paxdata.infrastructure.db.models import Sentence

            query = (
                session.query(Sentence.embedding)
                .filter(
                    Sentence.embedding.isnot(None),
                    # Add timestamp filter if available in Sentence model
                )
                .limit(10000)
            )

            results = await asyncio.get_event_loop().run_in_executor(None, query.all)

            embeddings = []
            for row in results:
                if row.embedding is not None:
                    embeddings.append(row.embedding)

            return embeddings

        except Exception as e:
            logger.error("get_embeddings_failed", error=str(e))
            return []

    async def _get_correction_rate(
        self, session, field: str, start: datetime, end: datetime
    ) -> float | None:
        """Get correction rate for a field in given time window.

        Args:
            session: Database session
            field: Field name
            start: Start of time window
            end: End of time window

        Returns:
            Correction rate (corrections / total_analyses) or None
        """
        try:
            from bb_paxdata.infrastructure.db.correction_event_table import (
                CorrectionEventORM,
            )

            # Count corrections for this field
            corrections_query = session.query(CorrectionEventORM).filter(
                CorrectionEventORM.field_corrected == field,
                CorrectionEventORM.timestamp >= start,
                CorrectionEventORM.timestamp <= end,
            )

            corrections_count = await asyncio.get_event_loop().run_in_executor(
                None, corrections_query.count
            )

            # Get total analyses (this would need to be implemented based on your schema)
            # For now, return a placeholder
            total_analyses = 1000  # Placeholder

            if total_analyses == 0:
                return None

            return corrections_count / total_analyses

        except Exception as e:
            logger.error("get_correction_rate_failed", error=str(e))
            return None

    async def _get_field_values(
        self, session, field: str, start: datetime, end: datetime
    ) -> list[float]:
        """Get field values from analysis results for given time window.

        Args:
            session: Database session
            field: Field name
            start: Start of time window
            end: End of time window

        Returns:
            List of field values
        """
        try:
            # This would query the analysis_results table
            # For now, return placeholder data
            return [0.5, 0.6, 0.7, 0.4, 0.8]  # Placeholder

        except Exception as e:
            logger.error("get_field_values_failed", error=str(e))
            return []

    async def _persist_drift_scores(self, session, scores: list[DriftScore]) -> None:
        """Persist drift scores to drift_measurements table.

        Args:
            session: Database session
            scores: List of drift scores to persist
        """
        try:
            # This would insert into drift_measurements table
            # For now, just log
            logger.info("persist_drift_scores", count=len(scores))

        except Exception as e:
            logger.error("persist_drift_scores_failed", error=str(e))
