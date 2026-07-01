"""Quick DB check for ai_sentence_analysis columns."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import asyncpg


async def main():
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]
    conn = await asyncpg.connect(url)

    # ai_sentence_analysis: row count + key columns
    r = await conn.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(risk_score) FILTER (WHERE risk_score IS NOT NULL) AS has_risk,
            COUNT(*) FILTER (WHERE risk_score >= 5) AS risk_gte5,
            COUNT(*) FILTER (WHERE risk_score >= 7) AS risk_gte7,
            COUNT(ai_emotion) FILTER (WHERE ai_emotion IS NOT NULL) AS has_ai_emotion,
            COUNT(sentiment_score) FILTER (WHERE sentiment_score IS NOT NULL) AS has_sent,
            COUNT(ai_topic) FILTER (WHERE ai_topic IS NOT NULL) AS has_ai_topic,
            COUNT(ai_hedging_score) FILTER (WHERE ai_hedging_score IS NOT NULL) AS has_hedging
        FROM ai_sentence_analysis
    """)
    print("=== ai_sentence_analysis ===")
    for k, v in r.items():
        print(f"  {k:30} {v}")

    # speaker_id linkage: ai_sentence_analysis -> sentences
    r2 = await conn.fetchrow("""
        SELECT COUNT(DISTINCT s.speaker_id) AS speakers_with_ai
        FROM ai_sentence_analysis a
        JOIN sentences s ON a.sent_id = s.sent_id
        WHERE s.speaker_id IS NOT NULL
    """)
    print(f"\n  speakers_with_ai_data       {r2['speakers_with_ai']}")

    # Sample risk_score values
    rows = await conn.fetch("""
        SELECT risk_score, COUNT(*) AS cnt
        FROM ai_sentence_analysis
        WHERE risk_score IS NOT NULL
        GROUP BY risk_score
        ORDER BY risk_score DESC
        LIMIT 15
    """)
    print("\n  risk_score distribution (ai_sentence_analysis):")
    for row in rows:
        print(f"    risk_score={row['risk_score']:>4}  count={row['cnt']}")

    # Sample ai_emotion distribution
    rows2 = await conn.fetch("""
        SELECT ai_emotion, COUNT(*) AS cnt
        FROM ai_sentence_analysis
        WHERE ai_emotion IS NOT NULL
        GROUP BY ai_emotion
        ORDER BY cnt DESC
        LIMIT 10
    """)
    print("\n  ai_emotion distribution:")
    for row in rows2:
        print(f"    {row['ai_emotion']!s:<30} {row['cnt']}")

    # topic_assignments count
    try:
        r3 = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM topic_assignments")
        print(f"\n=== topic_assignments: {r3['cnt']} rows ===")
        rows3 = await conn.fetch("""
            SELECT topic_label, COUNT(*) AS cnt
            FROM topic_assignments
            WHERE topic_label IS NOT NULL
            GROUP BY topic_label
            ORDER BY cnt DESC
            LIMIT 15
        """)
        for row in rows3:
            print(f"  {row['topic_label']!s:<40} {row['cnt']}")
    except Exception as e:
        print(f"\ntopic_assignments: {e}")

    await conn.close()


asyncio.run(main())
