"""AI / validation persistence across multiple ORM tables → domain models only."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.metadata import Metadata
from bb_paxdata.domain.models.validation_result import ValidationResult
from bb_paxdata.infrastructure.db import models as m


class AnalysisRepository:
    """Coordinates AI sentence analysis, validation, flags, insights, demand, cache."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- AI sentence analysis (domain: Analysis) ---
    def get_sentence_analysis(self, sent_id: str) -> Analysis | None:
        stmt = select(m.AISentenceAnalysis).where(
            m.AISentenceAnalysis.sent_id == sent_id
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    def get_panel_analysis(self, panel_id: str) -> list[Analysis]:
        stmt = (
            select(m.AISentenceAnalysis)
            .where(m.AISentenceAnalysis.panel_id == panel_id)
            .order_by(m.AISentenceAnalysis.global_sent_order)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def get_failures(self, panel_id: str | None = None) -> list[Analysis]:
        fail = func.lower(m.AISentenceAnalysis.overall_logic_check) == "fail"
        stmt = select(m.AISentenceAnalysis).where(fail)
        if panel_id is not None:
            stmt = stmt.where(m.AISentenceAnalysis.panel_id == panel_id)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def save_sentence_analysis(self, analysis: Analysis) -> None:
        sent_id = analysis.sentence_id
        if not sent_id:
            raise ValueError("Analysis.sentence_id is required")
        stmt = select(m.AISentenceAnalysis).where(
            m.AISentenceAnalysis.sent_id == sent_id
        )
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing is None:
            self._session.add(
                m.AISentenceAnalysis.from_domain(analysis, sent_id=sent_id)
            )
            return
        existing.seg_id = analysis.segment_id
        existing.risk_level = analysis.risk_level.value
        existing.sentiment_score = analysis.sentiment_score
        existing.manipulation_score = analysis.manipulation_score

    def save_many_sentence_analyses(self, analyses: list[Analysis]) -> None:
        for item in analyses:
            self.save_sentence_analysis(item)

    # --- Validation log (domain: ValidationResult per row) ---
    def get_validation_log(self, sent_id: str) -> list[ValidationResult]:
        stmt = (
            select(m.AIValidationLog)
            .where(m.AIValidationLog.sent_id == sent_id)
            .order_by(m.AIValidationLog.val_id)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def save_validation_log(self, log_entry: ValidationResult) -> None:
        self._session.add(
            m.AIValidationLog.from_domain(log_entry, sent_id=log_entry.entity_id)
        )

    def save_many_validation_logs(self, logs: list[ValidationResult]) -> None:
        for log in logs:
            self.save_validation_log(log)

    # --- Contextual flags (domain: Metadata envelope) ---
    def get_anomalies(
        self,
        sent_id: str | None = None,
        severity: str | None = None,
    ) -> list[Metadata]:
        stmt = select(m.AIContextualFlag)
        if sent_id is not None:
            stmt = stmt.where(m.AIContextualFlag.sent_id == sent_id)
        if severity is not None:
            stmt = stmt.where(m.AIContextualFlag.severity == severity)
        stmt = stmt.order_by(m.AIContextualFlag.flag_id)
        rows = self._session.execute(stmt).scalars().all()
        return [r.to_domain() for r in rows]

    def save_anomaly(self, anomaly: Metadata) -> None:
        self._session.add(m.AIContextualFlag.from_domain(anomaly))

    def save_many_anomalies(self, anomalies: list[Metadata]) -> None:
        for a in anomalies:
            self.save_anomaly(a)

    # --- Segment insights (domain: Metadata envelope) ---
    def get_segment_insight(self, seg_id: str) -> Metadata | None:
        stmt = select(m.AISegmentInsight).where(m.AISegmentInsight.seg_id == seg_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    def save_segment_insight(self, insight: Metadata) -> None:
        seg_id = insight.entity_id
        existing = self._session.execute(
            select(m.AISegmentInsight).where(m.AISegmentInsight.seg_id == seg_id)
        ).scalar_one_or_none()
        if existing is not None:
            self._session.delete(existing)
            self._session.flush()
        self._session.add(m.AISegmentInsight.from_domain(insight))

    # --- Demand-side AI (domain: Metadata envelope) ---
    def get_demand_analysis(self, demand_id: int) -> Metadata | None:
        stmt = select(m.AIDemandAnalysis).where(
            m.AIDemandAnalysis.demand_id == demand_id
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    def save_demand_analysis(self, analysis: Metadata) -> None:
        cf = analysis.custom_fields or {}
        demand_id = cf.get("demand_id")
        sent_id = cf.get("sent_id")
        row = m.AIDemandAnalysis(
            demand_id=int(demand_id) if demand_id is not None else None,
            sent_id=str(sent_id) if sent_id is not None else None,
            seg_id=cf.get("seg_id"),
            panel_id=cf.get("panel_id"),
            speaker_name=cf.get("speaker_name"),
            country=cf.get("country"),
            power_level=int(cf.get("power_level") or 0),
            demand_verb=cf.get("demand_verb"),
            demand_type=cf.get("demand_type"),
            demand_category=cf.get("demand_category"),
            future_risk=cf.get("future_risk"),
            risk_severity=cf.get("risk_severity"),
            demand_subtext=cf.get("demand_subtext"),
            hidden_agenda=cf.get("hidden_agenda"),
            potential_response=cf.get("potential_response"),
            escalation_path=cf.get("escalation_path"),
            diplomatic_leverage=cf.get("diplomatic_leverage"),
            future_demands=cf.get("future_demands"),
            strategic_value=cf.get("strategic_value"),
            backend_used=cf.get("backend_used"),
            model_used=cf.get("model_used"),
            processing_ms=cf.get("processing_ms"),
        )
        self._session.add(row)

    # --- Cache (domain: Metadata envelope) ---
    def get_cache(self, hash_key: str) -> Metadata | None:
        row = self._session.get(m.AICache, hash_key)
        return row.to_domain() if row is not None else None

    def set_cache(
        self,
        hash_key: str,
        result_json: str,
        model_used: str,
        backend_used: str,
    ) -> None:
        row = self._session.get(m.AICache, hash_key)
        if row is None:
            self._session.add(
                m.AICache(
                    hash=hash_key,
                    result_json=result_json,
                    model_used=model_used,
                    backend_used=backend_used,
                    hit_count=0,
                )
            )
        else:
            row.result_json = result_json
            row.model_used = model_used
            row.backend_used = backend_used

    # --- Batch helpers ---
    def sentence_exists(self, sent_id: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(m.Sentence)
            .where(m.Sentence.sent_id == sent_id)
        )
        return int(self._session.execute(stmt).scalar_one()) > 0

    def segment_exists(self, seg_id: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(m.Segment)
            .where(m.Segment.seg_id == seg_id)
        )
        return int(self._session.execute(stmt).scalar_one()) > 0

    def get_processed_sent_ids(self, panel_id: str | None = None) -> set[str]:
        stmt = select(m.AISentenceAnalysis.sent_id)
        if panel_id is not None:
            stmt = stmt.where(m.AISentenceAnalysis.panel_id == panel_id)
        rows = self._session.execute(stmt).scalars().all()
        return {str(s) for s in rows}
