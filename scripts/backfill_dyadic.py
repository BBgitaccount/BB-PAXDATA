# scripts/backfill_dyadic.py
"""
TASK-DB-009 — bilateral_sentiments backfill script.
Calculates power_level_b, demand_weight, risk_severity, structural_distance,
alliance_score, and discourse_sentiment_delta dynamically for all existing records.
"""

import asyncio
import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select

from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
    COUNTRY_BLOC_MAP,
    normalize_country,
)
from bb_paxdata.application.pipeline.stages.assemble_network import (
    calculate_alliance_score,
)
from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.db.country_models import BilateralSentimentTable
from bb_paxdata.infrastructure.db.models import (
    DemandRecord,
    Sentence,
    Speaker,
    TopicMatrix,
)
from bb_paxdata.infrastructure.db.session import SessionLocal


async def main():
    print(
        "Starting TASK-DB-009 backfill script for bilateral sentiments calculations..."
    )
    settings = get_settings()
    print(f"Database URL: {settings.database_url}")

    async with SessionLocal() as session:
        # Fetch all bilateral sentiments
        res = await session.execute(select(BilateralSentimentTable))
        records = res.scalars().all()
        total = len(records)
        print(f"Found {total} bilateral sentiment records to process.")

        updated_count = 0

        # Build a map of records to easily lookup reverse directions
        # Key: (file_id, from_country.lower(), to_country.lower()) -> avg_sentiment
        sentiment_map = {
            (r.file_id, r.from_country.lower(), r.to_country.lower()): r.avg_sentiment
            for r in records
        }

        for r in records:
            from_c = r.from_country
            to_c = r.to_country
            panel_id = r.file_id

            iso_a, _, _ = normalize_country(from_c)
            iso_b, _, _ = normalize_country(to_c)

            # 1. Resolve power_level_a
            power_a = r.power_level_a
            # Try to resolve more specific power level from speakers if it is default
            if power_a in (1.0, 0.5, 0.0):
                stmt = (
                    select(Speaker.power_level)
                    .where(
                        or_(
                            Speaker.speaker_id == from_c,
                            func.lower(Speaker.country_code) == from_c.lower(),
                            func.lower(Speaker.canonical_name) == from_c.lower(),
                            func.lower(Speaker.country_name) == from_c.lower(),
                        )
                    )
                    .where(Speaker.power_level.isnot(None))
                )
                res_p = await session.execute(stmt)
                p_val = res_p.scalars().first()
                if p_val is not None:
                    power_a = p_val
                else:
                    info_a = COUNTRY_BLOC_MAP.get(iso_a)
                    if info_a:
                        power_a = info_a["power_level"]

            # 2. Resolve power_level_b
            power_b = 1.0
            stmt = (
                select(Speaker.power_level)
                .where(
                    or_(
                        Speaker.speaker_id == to_c,
                        func.lower(Speaker.country_code) == to_c.lower(),
                        func.lower(Speaker.canonical_name) == to_c.lower(),
                        func.lower(Speaker.country_name) == to_c.lower(),
                    )
                )
                .where(Speaker.power_level.isnot(None))
            )
            res_p = await session.execute(stmt)
            p_val = res_p.scalars().first()
            if p_val is not None:
                power_b = p_val
            else:
                info_b = COUNTRY_BLOC_MAP.get(iso_b)
                if info_b:
                    power_b = info_b["power_level"]

            # 3. Resolve demand_weight and risk_severity
            stmt_demands = select(
                DemandRecord.demand_topic,
                DemandRecord.demand_type,
                DemandRecord.sent_id,
            ).where(
                DemandRecord.file_id == panel_id,
                or_(
                    func.lower(DemandRecord.country) == from_c.lower(),
                    func.lower(DemandRecord.country) == iso_a.lower(),
                ),
                or_(
                    func.lower(DemandRecord.target_entity) == to_c.lower(),
                    func.lower(DemandRecord.target_entity) == iso_b.lower(),
                ),
            )
            res_demands = await session.execute(stmt_demands)
            demands = res_demands.all()

            demand_weights = []
            risk_severities = []

            for d_topic, d_type, d_sent_id in demands:
                topic_score = 0.5
                if d_topic:
                    stmt_topic = select(TopicMatrix.score).where(
                        TopicMatrix.file_id == panel_id,
                        or_(
                            func.lower(TopicMatrix.country) == from_c.lower(),
                            func.lower(TopicMatrix.country) == iso_a.lower(),
                        ),
                        func.lower(TopicMatrix.topic) == d_topic.lower(),
                    )
                    res_topic = await session.execute(stmt_topic)
                    t_val = res_topic.scalars().first()
                    if t_val is not None:
                        topic_score = t_val

                d_weight = power_a * topic_score
                demand_weights.append(d_weight)

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

                r_score = 0.0
                if d_sent_id:
                    stmt_sent = select(Sentence.risk_score).where(
                        Sentence.sent_id == d_sent_id
                    )
                    res_sent = await session.execute(stmt_sent)
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
            opp_avg = sentiment_map.get((panel_id, to_c.lower(), from_c.lower()), 0.0)
            discourse_sentiment_delta = Decimal(str(r.avg_sentiment - opp_avg))

            # Update row values
            r.power_level_a = power_a
            r.power_level_b = power_b
            r.demand_weight = final_demand_weight
            r.risk_severity = final_risk_severity
            r.structural_distance = structural_distance
            r.alliance_score = alliance_score
            r.discourse_sentiment_delta = discourse_sentiment_delta
            r.vote_affinity = (
                None  # TODO: UN Genel Kurul oy uyumu harici dataset gerektirir.
            )
            r.maoz_diplomatic_distance = None
            r.maoz_affinity_score = None
            r.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)

            updated_count += 1
            if updated_count % 50 == 0:
                print(f"Processed {updated_count}/{total} records...")

        await session.commit()
        print(f"Successfully backfilled {updated_count} bilateral sentiment records!")


if __name__ == "__main__":
    asyncio.run(main())
