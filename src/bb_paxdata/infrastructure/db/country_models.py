# src/bb_paxdata/infrastructure/db/country_models.py

"""
SQLAlchemy 2.0 ORM table tanımları — country/network entity'leri için.

Kurallar:
- Tüm sütunlar Mapped[T] ile tip güvenli tanımlanır.
- mapped_column() kullanılır, eski Column() yasak.
- JSON sütunlar için SQLAlchemy JSON tipi kullanılır.
- Bu modeller domain entity'lerine dönüştürücü metotlar içerir (to_domain / from_domain).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, Index, Integer, Numeric, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.bilateral_sentiment import (
        BilateralSentiment,
    )
    from bb_paxdata.application.domain.models.country_reference import CountryReference
    from bb_paxdata.application.domain.models.discourse_flow import DiscourseFlow
    from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis


class Base(DeclarativeBase):
    # Transient list to store domain events associated with this ORM instance.
    _domain_events: list[dict[str, Any]]

    def record_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        correlation_id: str | None = None,
        aggregate_id: str | None = None,
    ) -> None:
        """Record an event on this ORM instance."""
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []

        pk_val = aggregate_id
        if pk_val is None:
            from sqlalchemy import inspect

            mapper = inspect(self.__class__)
            pk_val = "unknown"
            if mapper.primary_key:
                pk_attr = mapper.primary_key[0].name
                pk_val = str(getattr(self, pk_attr, "unknown"))

        corr_id = correlation_id
        if corr_id is None:
            from bb_paxdata.application.domain.utils.context import get_correlation_id

            corr_id = get_correlation_id()

        self._domain_events.append(
            {
                "aggregate_type": self.__class__.__name__,
                "aggregate_id": pk_val,
                "event_type": event_type,
                "payload": payload,
                "actor_id": actor_id,
                "correlation_id": corr_id,
            }
        )

    def clear_events(self) -> None:
        """Clear all events registered on this instance."""
        if hasattr(self, "_domain_events") and self._domain_events:
            self._domain_events.clear()

    def get_events(self) -> list[dict[str, Any]]:
        """Get all events registered on this instance."""
        return getattr(self, "_domain_events", None) or []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # If the subclass has defined a from_domain method, wrap it to transfer events
        if "from_domain" in cls.__dict__:
            original_from_domain = cls.from_domain

            def wrapped_from_domain(cls_, model, *args, **kwargs_):
                orm_instance = original_from_domain(model, *args, **kwargs_)
                # Transfer events from domain model to ORM model
                if hasattr(model, "get_events"):
                    events = model.get_events()
                    if events:
                        if not hasattr(orm_instance, "_domain_events"):
                            orm_instance._domain_events = []
                        orm_instance._domain_events.extend(events)
                        model.clear_events()
                return orm_instance

            cls.from_domain = classmethod(wrapped_from_domain)


class CountryReferenceTable(Base):
    __tablename__ = "country_references"
    __table_args__ = (
        Index("ix_cr_panel_id", "file_id"),
        Index("ix_cr_speaker_referenced", "speaker_country", "referenced_country"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    speaker_country: Mapped[str] = mapped_column(String(100), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referenced_country: Mapped[str] = mapped_column(String(100), nullable=False)
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_context: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NEUTRAL_MENTION"
    )
    raw_sentiment_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    speaker_power_level: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def to_domain(self) -> CountryReference:
        from bb_paxdata.application.domain.enums.country_enums import (
            ReferenceContext,
        )
        from bb_paxdata.application.domain.models.country_reference import (
            CountryReference,
        )

        return CountryReference(
            id=uuid.UUID(self.id),
            panel_id=self.file_id,
            speaker_country=self.speaker_country,
            speaker_id=self.speaker_id,
            referenced_country=self.referenced_country,
            sentence_index=self.sentence_index,
            reference_context=ReferenceContext(self.reference_context),
            raw_sentiment_score=self.raw_sentiment_score,
            speaker_power_level=self.speaker_power_level,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, entity: CountryReference) -> CountryReferenceTable:
        return cls(
            id=str(entity.id),
            file_id=entity.panel_id,
            speaker_country=entity.speaker_country,
            speaker_id=entity.speaker_id,
            referenced_country=entity.referenced_country,
            sentence_index=entity.sentence_index,
            reference_context=entity.reference_context.value,
            raw_sentiment_score=entity.raw_sentiment_score,
            speaker_power_level=entity.speaker_power_level,
            created_at=entity.created_at.replace(tzinfo=None),
        )


class BilateralSentimentTable(Base):
    __tablename__ = "bilateral_sentiments"
    __table_args__ = (
        Index("ix_bs_panel_pair", "file_id", "from_country", "to_country", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_country: Mapped[str] = mapped_column(String(100), nullable=False)
    to_country: Mapped[str] = mapped_column(String(100), nullable=False)
    total_mentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationship_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NEUTRAL"
    )
    affinity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    power_weighted_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    diplomatic_distance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Trager-related parameters persisted so domain defaults don't mask real values
    power_level_a: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    power_level_b: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    demand_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    risk_severity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Faz 4 new fields (using Numeric for precision where possible)
    vote_affinity: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    alliance_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    structural_distance: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    discourse_sentiment_delta: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    # Note: diplomatic_distance and affinity_score are already present as Float,
    # but we might want to ensure they are consistent with Phase 4 expectations.
    # For now, we'll keep the existing ones and add Maoz-specific Decimal fields if needed,
    # or just use the existing ones. The prompt asks to add them as Faz 4 new fields.
    maoz_diplomatic_distance: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    maoz_affinity_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def to_domain(self) -> BilateralSentiment:
        from bb_paxdata.application.domain.enums.country_enums import (
            RelationshipType,
        )
        from bb_paxdata.application.domain.models.bilateral_sentiment import (
            BilateralSentiment,
        )

        return BilateralSentiment(
            id=uuid.UUID(self.id),
            panel_id=self.file_id,
            from_country=self.from_country,
            to_country=self.to_country,
            total_mentions=self.total_mentions,
            avg_sentiment=self.avg_sentiment,
            interaction_count=self.interaction_count,
            relationship_type=RelationshipType(self.relationship_type),
            affinity_score=self.affinity_score,
            power_weighted_score=self.power_weighted_score,
            diplomatic_distance=self.diplomatic_distance,
            last_updated=self.last_updated,
            power_level_a=float(getattr(self, "power_level_a", 1.0) or 1.0),
            power_level_b=float(getattr(self, "power_level_b", 1.0) or 1.0),
            demand_weight=float(getattr(self, "demand_weight", 1.0) or 1.0),
            risk_severity=float(getattr(self, "risk_severity", 1.0) or 1.0),
        )

    @classmethod
    def from_domain(cls, entity: BilateralSentiment) -> BilateralSentimentTable:
        return cls(
            id=str(entity.id),
            file_id=entity.panel_id,
            from_country=entity.from_country,
            to_country=entity.to_country,
            total_mentions=entity.total_mentions,
            avg_sentiment=entity.avg_sentiment,
            interaction_count=entity.interaction_count,
            relationship_type=entity.relationship_type.value,
            affinity_score=entity.affinity_score,
            power_weighted_score=entity.power_weighted_score,
            diplomatic_distance=entity.diplomatic_distance,
            power_level_a=entity.power_level_a,
            power_level_b=entity.power_level_b,
            demand_weight=entity.demand_weight,
            risk_severity=entity.risk_severity,
            last_updated=(
                entity.last_updated.replace(tzinfo=None)
                if entity.last_updated
                else datetime.now(timezone.utc).replace(tzinfo=None)
            ),
        )


class DiscourseFlowTable(Base):
    __tablename__ = "discourse_flows"
    __table_args__ = (
        Index("ix_df_panel_id", "file_id"),
        Index("ix_df_from_to", "from_country", "to_country"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_country: Mapped[str] = mapped_column(String(100), nullable=False)
    to_country: Mapped[str] = mapped_column(String(100), nullable=False)
    edge_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="diplomatic_reference"
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    sentiment_toward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confrontational_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cooperative_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narrative_layer: Mapped[str | None] = mapped_column(String(50), nullable=True)
    narrative_target_actor: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    narrative_salience: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    def to_domain(self) -> DiscourseFlow:
        from bb_paxdata.application.domain.enums.country_enums import (
            EdgeType,
            NarrativeLayer,
        )
        from bb_paxdata.application.domain.models.discourse_flow import (
            DiscourseFlow,
        )

        return DiscourseFlow(
            id=uuid.UUID(self.id),
            panel_id=self.file_id,
            from_country=self.from_country,
            to_country=self.to_country,
            edge_type=EdgeType(self.edge_type),
            weight=self.weight,
            sentiment_toward=self.sentiment_toward,
            confrontational_count=self.confrontational_count,
            cooperative_count=self.cooperative_count,
            narrative_layer=(
                NarrativeLayer(self.narrative_layer) if self.narrative_layer else None
            ),
            narrative_target_actor=self.narrative_target_actor,
            narrative_salience=self.narrative_salience,
        )

    @classmethod
    def from_domain(cls, entity: DiscourseFlow) -> DiscourseFlowTable:
        return cls(
            id=str(entity.id),
            file_id=entity.panel_id,
            from_country=entity.from_country,
            to_country=entity.to_country,
            edge_type=entity.edge_type.value,
            weight=entity.weight,
            sentiment_toward=entity.sentiment_toward,
            confrontational_count=entity.confrontational_count,
            cooperative_count=entity.cooperative_count,
            narrative_layer=(
                entity.narrative_layer.value if entity.narrative_layer else None
            ),
            narrative_target_actor=entity.narrative_target_actor,
            narrative_salience=entity.narrative_salience,
        )


class TopicMatrixTable(Base):
    __tablename__ = "topic_matrices"
    __table_args__ = (Index("ix_tm_panel_country", "file_id", "country", unique=True),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    topic_scores: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    dominant_topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    topic_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def to_domain(self) -> TopicSynthesis:
        from bb_paxdata.application.domain.models.topic_synthesis import (
            TopicSynthesis,
        )

        return TopicSynthesis(
            id=uuid.UUID(self.id),
            panel_id=self.file_id,
            country=self.country,
            topic_scores=self.topic_scores,
            topic_label=self.dominant_topic,
        )

    @classmethod
    def from_domain(cls, entity: TopicSynthesis) -> TopicMatrixTable:
        return cls(
            id=str(entity.id),
            file_id=entity.panel_id,
            country=entity.country,
            topic_scores=entity.topic_scores,
            dominant_topic=entity.topic_label,
        )
