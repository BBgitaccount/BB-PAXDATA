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
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
    from bb_paxdata.domain.models.country_reference import CountryReference
    from bb_paxdata.domain.models.discourse_flow import DiscourseFlow
    from bb_paxdata.domain.models.topic_synthesis import TopicSynthesis


class Base(DeclarativeBase):
    pass


class CountryReferenceTable(Base):
    __tablename__ = "country_references"
    __table_args__ = (
        Index("ix_cr_panel_id", "panel_id"),
        Index("ix_cr_speaker_referenced", "speaker_country", "referenced_country"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    panel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    speaker_country: Mapped[str] = mapped_column(String(100), nullable=False)
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
        DateTime, nullable=False, default=datetime.utcnow
    )

    def to_domain(self) -> CountryReference:
        from bb_paxdata.domain.enums.country_enums import (
            ReferenceContext,
        )
        from bb_paxdata.domain.models.country_reference import (
            CountryReference,
        )

        return CountryReference(
            id=uuid.UUID(self.id),
            panel_id=self.panel_id,
            speaker_country=self.speaker_country,
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
            panel_id=entity.panel_id,
            speaker_country=entity.speaker_country,
            referenced_country=entity.referenced_country,
            sentence_index=entity.sentence_index,
            reference_context=entity.reference_context.value,
            raw_sentiment_score=entity.raw_sentiment_score,
            speaker_power_level=entity.speaker_power_level,
            created_at=entity.created_at,
        )


class BilateralSentimentTable(Base):
    __tablename__ = "bilateral_sentiments"
    __table_args__ = (
        Index(
            "ix_bs_panel_pair", "panel_id", "from_country", "to_country", unique=True
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    panel_id: Mapped[str] = mapped_column(String(255), nullable=False)
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
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def to_domain(self) -> BilateralSentiment:
        from bb_paxdata.domain.enums.country_enums import (
            RelationshipType,
        )
        from bb_paxdata.domain.models.bilateral_sentiment import (
            BilateralSentiment,
        )

        return BilateralSentiment(
            id=uuid.UUID(self.id),
            panel_id=self.panel_id,
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
        )

    @classmethod
    def from_domain(cls, entity: BilateralSentiment) -> BilateralSentimentTable:
        return cls(
            id=str(entity.id),
            panel_id=entity.panel_id,
            from_country=entity.from_country,
            to_country=entity.to_country,
            total_mentions=entity.total_mentions,
            avg_sentiment=entity.avg_sentiment,
            interaction_count=entity.interaction_count,
            relationship_type=entity.relationship_type.value,
            affinity_score=entity.affinity_score,
            power_weighted_score=entity.power_weighted_score,
            diplomatic_distance=entity.diplomatic_distance,
            last_updated=entity.last_updated,
        )


class DiscourseFlowTable(Base):
    __tablename__ = "discourse_flows"
    __table_args__ = (
        Index("ix_df_panel_id", "panel_id"),
        Index("ix_df_from_to", "from_country", "to_country"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    panel_id: Mapped[str] = mapped_column(String(255), nullable=False)
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

    def to_domain(self) -> DiscourseFlow:
        from bb_paxdata.domain.enums.country_enums import EdgeType
        from bb_paxdata.domain.models.discourse_flow import (
            DiscourseFlow,
        )

        return DiscourseFlow(
            id=uuid.UUID(self.id),
            panel_id=self.panel_id,
            from_country=self.from_country,
            to_country=self.to_country,
            edge_type=EdgeType(self.edge_type),
            weight=self.weight,
            sentiment_toward=self.sentiment_toward,
            confrontational_count=self.confrontational_count,
            cooperative_count=self.cooperative_count,
        )

    @classmethod
    def from_domain(cls, entity: DiscourseFlow) -> DiscourseFlowTable:
        return cls(
            id=str(entity.id),
            panel_id=entity.panel_id,
            from_country=entity.from_country,
            to_country=entity.to_country,
            edge_type=entity.edge_type.value,
            weight=entity.weight,
            sentiment_toward=entity.sentiment_toward,
            confrontational_count=entity.confrontational_count,
            cooperative_count=entity.cooperative_count,
        )


class TopicMatrixTable(Base):
    __tablename__ = "topic_matrices"
    __table_args__ = (Index("ix_tm_panel_country", "panel_id", "country", unique=True),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    panel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    topic_scores: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    dominant_topic: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def to_domain(self) -> TopicSynthesis:
        from bb_paxdata.domain.models.topic_synthesis import (
            TopicSynthesis,
        )

        return TopicSynthesis(
            id=uuid.UUID(self.id),
            panel_id=self.panel_id,
            country=self.country,
            topic_scores=self.topic_scores,
            dominant_topic=self.dominant_topic,
        )

    @classmethod
    def from_domain(cls, entity: TopicSynthesis) -> TopicMatrixTable:
        return cls(
            id=str(entity.id),
            panel_id=entity.panel_id,
            country=entity.country,
            topic_scores=entity.topic_scores,
            dominant_topic=entity.dominant_topic,
        )
