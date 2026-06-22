# scripts/fix_topic_matrix.py
import asyncio

from sqlalchemy import delete, func, select

from bb_paxdata.infrastructure.db.models import DemandRecord, Sentence, TopicMatrix
from bb_paxdata.infrastructure.db.topic_models import TopicAssignmentORM
from bb_paxdata.interfaces.cli.dependencies import get_session


async def run_backfill():
    print("Starting Topic Matrix Backfill...")
    async with get_session() as session:
        # 1. Truncate existing topic_matrix table
        print("Clearing existing topic_matrix table...")
        await session.execute(delete(TopicMatrix))
        await session.commit()

        # 2. Fetch all sentences, topic assignments and demand records
        print("Fetching data from DB...")
        sentences_res = await session.execute(select(Sentence))
        sentences = sentences_res.scalars().all()
        sent_map = {s.sent_id: s for s in sentences}

        ta_res = await session.execute(select(TopicAssignmentORM))
        assignments = ta_res.scalars().all()

        dr_res = await session.execute(select(DemandRecord))
        demands = dr_res.scalars().all()
        demand_sent_ids = {d.sent_id for d in demands if d.sent_id}

        print(
            f"Loaded {len(sentences)} sentences, {len(assignments)} topic assignments, and {len(demands)} demand records."
        )

        # Build topic ID -> human-readable label mapping
        topic_mapping = {}
        for ta in assignments:
            if ta.primary_topic:
                topic_mapping[ta.primary_topic] = ta.topic_label or ta.primary_topic

        # Group assignments by (file_id, country, topic_label)
        from collections import defaultdict

        grouped = defaultdict(list)

        for ta in assignments:
            sent = sent_map.get(ta.analysis_id)
            if not sent or not sent.country or sent.country.lower() == "unknown":
                continue

            p_topic = ta.primary_topic
            score = ta.topic_scores.get(p_topic, 0.0) if ta.topic_scores else 0.0

            # Filter by confidence score > 0.5
            if score > 0.5:
                label = topic_mapping.get(p_topic)
                if p_topic == "-1" or not label:
                    label = "uncategorized"

                grouped[(sent.file_id, sent.country, label)].append((sent, score))

        print(f"Aggregating into {len(grouped)} country-topic combinations...")

        # Add TopicMatrix records
        for (file_id, country, label), items in grouped.items():
            scores = [score for _, score in items]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            mention_count = len(items)

            sentiments = [
                sent.vader_compound
                for sent, _ in items
                if sent.vader_compound is not None
            ]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

            risks = [
                sent.risk_score for sent, _ in items if sent.risk_score is not None
            ]
            avg_risk = sum(risks) / len(risks) if risks else 0.0

            demand_count = sum(
                1 for sent, _ in items if sent.sent_id in demand_sent_ids
            )

            emotions = [
                sent.emotion_category for sent, _ in items if sent.emotion_category
            ]
            dominant_emotion = (
                max(set(emotions), key=emotions.count) if emotions else None
            )

            frames = [sent.dominant_frame for sent, _ in items if sent.dominant_frame]
            dominant_frame = max(set(frames), key=frames.count) if frames else None

            tm = TopicMatrix(
                file_id=file_id,
                country=country,
                topic=label,
                score=avg_score,
                mention_count=mention_count,
                avg_sentiment=avg_sentiment,
                risk_score=avg_risk,
                demand_count=demand_count,
                dominant_emotion=dominant_emotion,
                dominant_frame=dominant_frame,
            )
            session.add(tm)

        await session.commit()
        print("Backfill data successfully committed to database!")

        # 3. Validation and Report
        print("\nVerification Report:")
        total_res = await session.execute(select(func.count(TopicMatrix.topic)))
        total_count = total_res.scalar()
        print(f"  * Total topic_matrix rows: {total_count}")

        # Metrics check
        res = await session.execute(
            select(
                func.count(TopicMatrix.mention_count),
                func.count(TopicMatrix.avg_sentiment),
                func.count(TopicMatrix.risk_score),
                func.count(TopicMatrix.demand_count),
            )
        )
        row = res.fetchone()
        print(f"  * Non-null mention_count: {row[0]}")
        print(f"  * Non-null avg_sentiment: {row[1]}")
        print(f"  * Non-null risk_score: {row[2]}")
        print(f"  * Non-null demand_count: {row[3]}")

        # Value ranges check
        res = await session.execute(
            select(
                func.min(TopicMatrix.avg_sentiment),
                func.max(TopicMatrix.avg_sentiment),
                func.min(TopicMatrix.risk_score),
                func.max(TopicMatrix.risk_score),
                func.min(TopicMatrix.mention_count),
                func.max(TopicMatrix.mention_count),
            )
        )
        row = res.fetchone()
        print(f"  * Sentiment Range: [{row[0]}, {row[1]}] (expected: [-1.0, 1.0])")
        print(f"  * Risk Score Range: [{row[2]}, {row[3]}] (expected: [0, 10])")
        print(
            f"  * Mention Count Range: [{row[4]}, {row[5]}] (expected: positive integer)"
        )

        # Unique topic names check
        res = await session.execute(select(TopicMatrix.topic).distinct().limit(20))
        topics = [r[0] for r in res.all()]
        # Filter topics list to only ascii characters to prevent any print crash on Windows console
        safe_topics = []
        for t in topics:
            if t:
                # Convert non-ascii to ascii representation or remove
                safe_t = t.encode("ascii", errors="replace").decode("ascii")
                safe_topics.append(safe_t)
        print(f"  * Unique Topic Names sample: {safe_topics}")


if __name__ == "__main__":
    asyncio.run(run_backfill())
