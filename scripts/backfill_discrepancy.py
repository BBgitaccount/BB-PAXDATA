"""
scripts/backfill_discrepancy.py
TASK-DB-006 #25a — discrepancy_score backfill

AI sentiment (ai_sentence_analysis.sentiment_score, 0-1 scale) ile
rule-based diplo_compound (-1..1 scale) arasındaki tutarsızlığı hesaplar.

Formula: discrepancy_score = |ai_norm - diplo_compound| / 2.0
  where ai_norm = (ai_sentiment_score - 0.5) * 2.0  (0-1 → -1..1 normalize)
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import asyncpg


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(url)

    print("TASK-DB-006 #25a | Backfilling discrepancy_score...\n")

    # Join sentences ↔ ai_sentence_analysis
    rows = await conn.fetch(
        """
        SELECT s.sent_id,
               s.diplo_compound,
               s.vader_compound,
               a.sentiment_score AS ai_sent_score
        FROM sentences s
        LEFT JOIN ai_sentence_analysis a ON a.sent_id = s.sent_id
        ORDER BY s.sent_id
    """
    )
    total = len(rows)
    print(f"Found {total} sentences.\n")

    updates = []
    nonzero = 0
    for row in rows:
        ai_raw = row["ai_sent_score"]  # 0-1 scale from AI
        diplo = row["diplo_compound"]  # -1..1 rule-based
        vader = row["vader_compound"]  # -1..1 rule-based fallback

        # Choose best rule-based signal
        rule_based = diplo if (diplo is not None and diplo != 0.0) else (vader or 0.0)

        if ai_raw is not None and ai_raw not in {0.0, 0.5}:
            # Normalize AI score 0-1 → -1..1
            ai_norm = (ai_raw - 0.5) * 2.0
            disc = round(abs(ai_norm - rule_based) / 2.0, 4)
        else:
            # No AI data: use |diplo - vader| as proxy
            disc = round(abs((diplo or 0.0) - (vader or 0.0)) / 2.0, 4)

        if disc > 0:
            nonzero += 1
        updates.append((disc, row["sent_id"]))

    # Batch update
    batch_size = 500
    for i in range(0, len(updates), batch_size):
        batch = updates[i : i + batch_size]
        await conn.executemany(
            "UPDATE sentences SET discrepancy_score = $1 WHERE sent_id = $2",
            batch,
        )
        print(f"  Updated {min(i + batch_size, len(updates))}/{len(updates)}...")

    print("\nDone.")
    print(
        f"  discrepancy_score > 0 : {nonzero} / {total} ({100 * nonzero / total:.1f}%)"
    )

    # Distribution buckets
    buckets = await conn.fetch(
        """
        SELECT
            CASE
                WHEN discrepancy_score = 0 THEN '0.0'
                WHEN discrepancy_score < 0.1 THEN '0.01-0.09'
                WHEN discrepancy_score < 0.3 THEN '0.10-0.29'
                WHEN discrepancy_score < 0.6 THEN '0.30-0.59'
                ELSE '0.60+'
            END AS bucket,
            COUNT(*) AS cnt
        FROM sentences
        GROUP BY 1 ORDER BY 1
    """
    )
    print("\n  discrepancy_score distribution:")
    for b in buckets:
        print(f"    {b['bucket']:<12} : {b['cnt']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
