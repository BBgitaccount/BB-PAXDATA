"""TASK-DB-006: Mevcut durum diagnostik sorguları."""

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
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(url)

    print("=== #23: face_threat_count / face_save_count ===")
    r = await conn.fetchrow(
        """
        SELECT AVG(face_threat_count) AS avg_ft, AVG(face_save_count) AS avg_fs,
               COUNT(*) FILTER (WHERE face_threat_count > 0) AS nonzero_ft,
               COUNT(*) FILTER (WHERE face_save_count > 0) AS nonzero_fs,
               COUNT(*) AS total
        FROM sentences
    """
    )
    print(f"  AVG face_threat_count : {r['avg_ft']}")
    print(f"  AVG face_save_count   : {r['avg_fs']}")
    print(f"  face_threat_count > 0 : {r['nonzero_ft']} / {r['total']}")
    print(f"  face_save_count > 0   : {r['nonzero_fs']} / {r['total']}")

    print("\n=== #24: logic_result dağılımı ===")
    rows = await conn.fetch(
        """
        SELECT logic_result, COUNT(*) AS cnt
        FROM sentences GROUP BY logic_result ORDER BY cnt DESC
    """
    )
    for row in rows:
        print(f"  {row['logic_result']!s:<10} {row['cnt']}")

    print("\n  Sample FAIL rows (logic_result=FAIL, formula_inconsistency):")
    rows2 = await conn.fetch(
        """
        SELECT sent_id, logic_result, formula_inconsistency_score, discrepancy_score, vader_compound
        FROM sentences WHERE logic_result = 'FAIL' LIMIT 10
    """
    )
    for r in rows2:
        print(
            f"  {r['sent_id']:<35} incons={r['formula_inconsistency_score']} disc={r['discrepancy_score']} vader={r['vader_compound']}"
        )

    print("\n  formula_validation_logs count:")
    try:
        r3 = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM formula_validation_logs")
        print(f"  {r3['cnt']} rows")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n=== #25: discrepancy_score & embeddings ===")
    r4 = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE discrepancy_score IS NOT NULL AND discrepancy_score > 0) AS disc_nonzero,
            COUNT(*) FILTER (WHERE discrepancy_score IS NULL OR discrepancy_score = 0) AS disc_zero_null,
            COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS emb_not_null,
            COUNT(*) AS total
        FROM sentences
    """
    )
    print(f"  discrepancy_score > 0 : {r4['disc_nonzero']} / {r4['total']}")
    print(f"  discrepancy_score = 0/NULL : {r4['disc_zero_null']} / {r4['total']}")
    print(f"  embedding IS NOT NULL : {r4['emb_not_null']} / {r4['total']}")

    # Check embedding column type
    rows5 = await conn.fetch(
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_name='sentences' AND column_name='embedding'
    """
    )
    for r in rows5:
        print(f"\n  embedding column type: {r['data_type']} / udt: {r['udt_name']}")

    await conn.close()


asyncio.run(main())
