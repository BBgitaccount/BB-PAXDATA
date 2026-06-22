from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
    COUNTRY_BLOC_MAP,
    normalize_country,
)
from bb_paxdata.application.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.application.domain.models.country_reference import CountryReference
from bb_paxdata.application.domain.models.discourse_flow import (
    DiscourseFlow,
    DyadicMetrics,
)
from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.application.domain.services.compare_sessions_protocols import (
    IDiscourseFlowRepository,
)
from bb_paxdata.application.pipeline.stages.assemble_network import (
    calculate_alliance_score,
)
from bb_paxdata.infrastructure.db.country_models import (
    BilateralSentimentTable,
    CountryReferenceTable,
    DiscourseFlowTable,
)
from bb_paxdata.infrastructure.db.models import (
    DemandRecord as DemandRecordTable,
    Sentence as SentenceTable,
    Speaker as SpeakerTable,
    TopicMatrix as TopicMatrixTable,
)


class CountryReferenceRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "Database session is not set on CountryReferenceRepository"
            )
        return self._session

    async def save(self, reference: CountryReference) -> None:
        row = CountryReferenceTable.from_domain(reference)
        self.session.add(row)
        await self.session.flush()

    async def save_batch(self, references: Sequence[CountryReference]) -> None:
        rows = [CountryReferenceTable.from_domain(r) for r in references]
        self.session.add_all(rows)
        await self.session.flush()

    async def get_by_panel(self, panel_id: str) -> list[CountryReference]:
        result = await self.session.execute(
            select(CountryReferenceTable).where(
                CountryReferenceTable.file_id == panel_id
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def get_by_pair(
        self, speaker: str, referenced: str, panel_id: str
    ) -> list[CountryReference]:
        result = await self.session.execute(
            select(CountryReferenceTable).where(
                CountryReferenceTable.file_id == panel_id,
                CountryReferenceTable.speaker_country == speaker,
                CountryReferenceTable.referenced_country == referenced,
            )
        )
        return [row.to_domain() for row in result.scalars().all()]


class BilateralSentimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _calculate_dynamic_metrics(
        self,
        panel_id: str,
        from_c: str,
        to_c: str,
        avg_sentiment: float,
        existing_power_a: float,
    ) -> tuple[float, float, float, float, Decimal, Decimal, Decimal]:
        iso_a, _, _ = normalize_country(from_c)
        iso_b, _, _ = normalize_country(to_c)

        # 1. Resolve power_level_a
        power_a = existing_power_a
        if power_a in (1.0, 0.5, 0.0):
            stmt = (
                select(SpeakerTable.power_level)
                .where(
                    or_(
                        SpeakerTable.speaker_id == from_c,
                        func.lower(SpeakerTable.country_code) == from_c.lower(),
                        func.lower(SpeakerTable.canonical_name) == from_c.lower(),
                        func.lower(SpeakerTable.country_name) == from_c.lower(),
                    )
                )
                .where(SpeakerTable.power_level.isnot(None))
            )
            res = await self._session.execute(stmt)
            p_val = res.scalars().first()
            if p_val is not None:
                power_a = p_val
            else:
                info_a = COUNTRY_BLOC_MAP.get(iso_a)
                if info_a:
                    power_a = info_a["power_level"]

        # 2. Resolve power_level_b
        power_b = 1.0
        stmt = (
            select(SpeakerTable.power_level)
            .where(
                or_(
                    SpeakerTable.speaker_id == to_c,
                    func.lower(SpeakerTable.country_code) == to_c.lower(),
                    func.lower(SpeakerTable.canonical_name) == to_c.lower(),
                    func.lower(SpeakerTable.country_name) == to_c.lower(),
                )
            )
            .where(SpeakerTable.power_level.isnot(None))
        )
        res = await self._session.execute(stmt)
        p_val = res.scalars().first()
        if p_val is not None:
            power_b = p_val
        else:
            info_b = COUNTRY_BLOC_MAP.get(iso_b)
            if info_b:
                power_b = info_b["power_level"]

        # 3. Resolve demand_weight
        stmt_demands = select(
            DemandRecordTable.demand_topic,
            DemandRecordTable.demand_type,
            DemandRecordTable.sent_id,
        ).where(
            DemandRecordTable.file_id == panel_id,
            or_(
                func.lower(DemandRecordTable.country) == from_c.lower(),
                func.lower(DemandRecordTable.country) == iso_a.lower(),
            ),
            or_(
                func.lower(DemandRecordTable.target_entity) == to_c.lower(),
                func.lower(DemandRecordTable.target_entity) == iso_b.lower(),
            ),
        )
        res_demands = await self._session.execute(stmt_demands)
        demands = res_demands.all()

        demand_weights = []
        risk_severities = []

        for d_topic, d_type, d_sent_id in demands:
            topic_score = 0.5
            if d_topic:
                stmt_topic = select(TopicMatrixTable.score).where(
                    TopicMatrixTable.file_id == panel_id,
                    or_(
                        func.lower(TopicMatrixTable.country) == from_c.lower(),
                        func.lower(TopicMatrixTable.country) == iso_a.lower(),
                    ),
                    func.lower(TopicMatrixTable.topic) == d_topic.lower(),
                )
                res_topic = await self._session.execute(stmt_topic)
                t_val = res_topic.scalars().first()
                if t_val is not None:
                    topic_score = t_val

            d_weight = power_a * topic_score
            demand_weights.append(d_weight)

            # base weight based on demand_type
            d_type_clean = str(d_type).lower() if d_type else ""
            if (
                "ultimatum" in d_type_clean
                or "obligatory" in d_type_clean
                or "must" in d_type_clean
            ):
                base_w = 0.9
            elif (
                "recommendation" in d_type_clean
                or "intention" in d_type_clean
                or "suggest" in d_type_clean
            ):
                base_w = 0.1
            else:
                base_w = 0.3

            # risk score context modifier
            r_score = 0.0
            if d_sent_id:
                stmt_sent = select(SentenceTable.risk_score).where(
                    SentenceTable.sent_id == d_sent_id
                )
                res_sent = await self._session.execute(stmt_sent)
                rs_val = res_sent.scalars().first()
                if rs_val is not None:
                    r_score = float(rs_val)

            modifier = (r_score / 10.0) * 0.1 + abs(power_a - power_b) * 0.1
            risk_sev = min(1.0, max(0.0, base_w + modifier))
            risk_severities.append(risk_sev)

        final_demand_weight = (
            sum(demand_weights) / len(demand_weights) if demand_weights else 1.0
        )
        final_risk_severity = (
            sum(risk_severities) / len(risk_severities) if risk_severities else 1.0
        )

        # 4. structural_distance
        structural_distance = Decimal(str(abs(power_a - power_b)))

        # 5. alliance_score
        alliance_score = calculate_alliance_score(from_c, to_c)

        # 6. discourse_sentiment_delta
        stmt_opp = select(BilateralSentimentTable.avg_sentiment).where(
            BilateralSentimentTable.file_id == panel_id,
            BilateralSentimentTable.from_country == to_c,
            BilateralSentimentTable.to_country == from_c,
        )
        res_opp = await self._session.execute(stmt_opp)
        opp_avg = res_opp.scalars().first()
        if opp_avg is None:
            opp_avg = 0.0

        discourse_sentiment_delta = Decimal(str(avg_sentiment - opp_avg))

        return (
            power_a,
            power_b,
            final_demand_weight,
            final_risk_severity,
            structural_distance,
            alliance_score,
            discourse_sentiment_delta,
        )

    async def upsert(self, sentiment: BilateralSentiment) -> BilateralSentiment:
        existing = await self.get_by_pair(
            sentiment.from_country, sentiment.to_country, sentiment.panel_id
        )

        power_a, power_b, demand_w, risk_sev, struct_dist, alliance, delta = (
            await self._calculate_dynamic_metrics(
                sentiment.panel_id,
                sentiment.from_country,
                sentiment.to_country,
                sentiment.avg_sentiment,
                sentiment.power_level_a,
            )
        )

        if existing is not None:
            result = await self._session.execute(
                select(BilateralSentimentTable).where(
                    BilateralSentimentTable.file_id == sentiment.panel_id,
                    BilateralSentimentTable.from_country == sentiment.from_country,
                    BilateralSentimentTable.to_country == sentiment.to_country,
                )
            )
            row = result.scalar_one()
            row.total_mentions = sentiment.total_mentions
            row.avg_sentiment = sentiment.avg_sentiment
            row.interaction_count = sentiment.interaction_count
            row.relationship_type = sentiment.relationship_type.value
            row.affinity_score = sentiment.affinity_score
            row.power_weighted_score = sentiment.power_weighted_score
            row.diplomatic_distance = sentiment.diplomatic_distance
            row.power_level_a = power_a
            row.power_level_b = power_b
            row.demand_weight = demand_w
            row.risk_severity = risk_sev
            row.last_updated = (
                sentiment.last_updated.replace(tzinfo=None)
                if sentiment.last_updated
                else datetime.now(timezone.utc).replace(tzinfo=None)
            )
            # Phase 4 columns
            row.vote_affinity = (
                None  # TODO: UN Genel Kurul oy uyumu harici dataset gerektirir.
            )
            row.alliance_score = alliance
            row.structural_distance = struct_dist
            row.discourse_sentiment_delta = delta
            row.maoz_diplomatic_distance = None
            row.maoz_affinity_score = None
        else:
            row = BilateralSentimentTable(
                id=str(sentiment.id),
                file_id=sentiment.panel_id,
                from_country=sentiment.from_country,
                to_country=sentiment.to_country,
                total_mentions=sentiment.total_mentions,
                avg_sentiment=sentiment.avg_sentiment,
                interaction_count=sentiment.interaction_count,
                relationship_type=sentiment.relationship_type.value,
                affinity_score=sentiment.affinity_score,
                power_weighted_score=sentiment.power_weighted_score,
                diplomatic_distance=sentiment.diplomatic_distance,
                power_level_a=power_a,
                power_level_b=power_b,
                demand_weight=demand_w,
                risk_severity=risk_sev,
                # Phase 4 columns
                vote_affinity=None,
                alliance_score=alliance,
                structural_distance=struct_dist,
                discourse_sentiment_delta=delta,
                maoz_diplomatic_distance=None,
                maoz_affinity_score=None,
                last_updated=(
                    sentiment.last_updated.replace(tzinfo=None)
                    if sentiment.last_updated
                    else datetime.now(timezone.utc).replace(tzinfo=None)
                ),
            )
            self._session.add(row)
        await self._session.flush()

        # Update opposite direction delta if it exists
        stmt_opp_row = select(BilateralSentimentTable).where(
            BilateralSentimentTable.file_id == sentiment.panel_id,
            BilateralSentimentTable.from_country == sentiment.to_country,
            BilateralSentimentTable.to_country == sentiment.from_country,
        )
        res_opp_row = await self._session.execute(stmt_opp_row)
        opp_row = res_opp_row.scalars().first()
        if opp_row:
            opp_row.discourse_sentiment_delta = Decimal(
                str(opp_row.avg_sentiment - sentiment.avg_sentiment)
            )
            await self._session.flush()

        return row.to_domain()

    async def save_dyadic(self, session: AsyncSession, metrics: DyadicMetrics) -> None:
        stmt = select(BilateralSentimentTable).where(
            BilateralSentimentTable.file_id == metrics.session_id,
            or_(
                and_(
                    BilateralSentimentTable.from_country == metrics.actor_a_id,
                    BilateralSentimentTable.to_country == metrics.actor_b_id,
                ),
                and_(
                    BilateralSentimentTable.from_country == metrics.actor_b_id,
                    BilateralSentimentTable.to_country == metrics.actor_a_id,
                ),
            ),
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.vote_affinity = metrics.vote_affinity
            row.alliance_score = metrics.alliance_score
            row.structural_distance = metrics.structural_distance
            row.discourse_sentiment_delta = metrics.discourse_sentiment_delta
            row.diplomatic_distance = float(metrics.diplomatic_distance or 0.0)
            row.maoz_diplomatic_distance = metrics.diplomatic_distance
            row.maoz_affinity_score = metrics.affinity_score
            await session.flush()
        else:
            pass

    async def get_by_pair(
        self, from_country: str, to_country: str, panel_id: str
    ) -> BilateralSentiment | None:
        result = await self._session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.file_id == panel_id,
                BilateralSentimentTable.from_country == from_country,
                BilateralSentimentTable.to_country == to_country,
            )
        )
        row = result.scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def get_all_for_panel(self, panel_id: str) -> list[BilateralSentiment]:
        result = await self._session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.file_id == panel_id
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def rebuild_global_country_pair_sentiments(self) -> None:
        from sqlalchemy import delete

        from bb_paxdata.application.domain.enums.country_enums import RelationshipType
        from bb_paxdata.infrastructure.db.models import CountryPairSentiment

        await self._session.execute(delete(CountryPairSentiment))
        stmt = select(
            BilateralSentimentTable.from_country,
            BilateralSentimentTable.to_country,
            func.sum(BilateralSentimentTable.total_mentions).label("total_mentions"),
            func.avg(BilateralSentimentTable.avg_sentiment).label("avg_sentiment"),
            func.sum(BilateralSentimentTable.interaction_count).label(
                "interaction_count"
            ),
            func.avg(BilateralSentimentTable.affinity_score).label("affinity_score"),
            func.avg(BilateralSentimentTable.power_weighted_score).label(
                "power_weighted_score"
            ),
            func.avg(BilateralSentimentTable.diplomatic_distance).label(
                "diplomatic_distance"
            ),
        ).group_by(
            BilateralSentimentTable.from_country, BilateralSentimentTable.to_country
        )
        res = await self._session.execute(stmt)
        rows = res.all()
        for r in rows:
            aff = r.affinity_score or 0.0
            if aff > 0.5:
                rel_type = RelationshipType.ALLY
            elif aff > 0.2:
                rel_type = RelationshipType.PARTNER
            elif aff < -0.5:
                rel_type = RelationshipType.ADVERSARY
            elif aff < -0.2:
                rel_type = RelationshipType.CAUTIOUS
            else:
                rel_type = RelationshipType.NEUTRAL
            cp = CountryPairSentiment(
                from_country=r.from_country,
                to_country=r.to_country,
                total_mentions=int(r.total_mentions or 0),
                avg_sentiment=(
                    float(r.avg_sentiment) if r.avg_sentiment is not None else None
                ),
                interaction_count=int(r.interaction_count or 0),
                relationship_type=rel_type,
                affinity_score=float(aff),
                power_weighted_score=float(r.power_weighted_score or 0.0),
                diplomatic_distance=float(r.diplomatic_distance or 0.0),
            )
            self._session.add(cp)
        await self._session.flush()


class DiscourseFlowRepository(IDiscourseFlowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_session(self, session_id: str) -> list[DiscourseFlow]:
        result = await self._session.execute(
            select(DiscourseFlowTable).where(DiscourseFlowTable.file_id == session_id)
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def save(self, flow: DiscourseFlow) -> None:
        row = DiscourseFlowTable.from_domain(flow)
        self._session.add(row)
        await self._session.flush()

    async def save_batch(self, flows: Sequence[DiscourseFlow]) -> None:
        rows = [DiscourseFlowTable.from_domain(f) for f in flows]
        self._session.add_all(rows)
        await self._session.flush()

    async def get_edges_for_panel(self, panel_id: str) -> list[DiscourseFlow]:
        result = await self._session.execute(
            select(DiscourseFlowTable).where(DiscourseFlowTable.file_id == panel_id)
        )
        return [row.to_domain() for row in result.scalars().all()]


class TopicSynthesisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, synthesis: TopicSynthesis) -> TopicSynthesis:
        from bb_paxdata.infrastructure.db.models import TopicMatrix

        # 1. Fetch existing topic matrix rows for this country in this file
        result = await self._session.execute(
            select(TopicMatrix).where(
                TopicMatrix.file_id == synthesis.panel_id,
                TopicMatrix.country == synthesis.country,
            )
        )
        existing_rows = result.scalars().all()
        existing_by_topic = {row.topic: row for row in existing_rows}

        new_scores = synthesis.topic_scores or {}

        # 2. Iterate through new topic scores
        for topic, score in new_scores.items():
            if topic in existing_by_topic:
                # Update score of existing row, preserving other columns
                existing_by_topic[topic].score = score
            else:
                # Insert new row
                new_row = TopicMatrix(
                    file_id=synthesis.panel_id,
                    country=synthesis.country,
                    topic=topic,
                    score=score,
                )
                self._session.add(new_row)

        # 3. Delete rows that are no longer present in new_scores
        for topic, row in existing_by_topic.items():
            if topic not in new_scores:
                await self._session.delete(row)

        await self._session.flush()
        return synthesis

    async def get_by_country(
        self, panel_id: str, country: str
    ) -> TopicSynthesis | None:
        from bb_paxdata.infrastructure.db.models import TopicMatrix

        result = await self._session.execute(
            select(TopicMatrix).where(
                TopicMatrix.file_id == panel_id,
                TopicMatrix.country == country,
            )
        )
        rows = result.scalars().all()
        if not rows:
            return None

        topic_scores = {row.topic: row.score for row in rows}
        dominant_topic = (
            max(topic_scores, key=lambda k: topic_scores[k]) if topic_scores else None
        )

        return TopicSynthesis(
            panel_id=panel_id,
            country=country,
            topic_scores=topic_scores,
            topic_label=dominant_topic,
        )

    async def get_all_for_panel(self, panel_id: str) -> list[TopicSynthesis]:
        from bb_paxdata.infrastructure.db.models import TopicMatrix

        result = await self._session.execute(
            select(TopicMatrix).where(TopicMatrix.file_id == panel_id)
        )
        rows = result.scalars().all()

        # Group by country
        from collections import defaultdict

        by_country = defaultdict(list)
        for row in rows:
            by_country[row.country].append(row)

        syntheses = []
        for country, c_rows in by_country.items():
            topic_scores = {row.topic: row.score for row in c_rows}
            dominant_topic = (
                max(topic_scores, key=lambda k: topic_scores[k])
                if topic_scores
                else None
            )
            syntheses.append(
                TopicSynthesis(
                    panel_id=panel_id,
                    country=country,
                    topic_scores=topic_scores,
                    topic_label=dominant_topic,
                )
            )
        return syntheses
