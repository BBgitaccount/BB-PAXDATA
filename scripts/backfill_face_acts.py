"""
scripts/backfill_face_acts.py
TASK-DB-006 #23 — face_threat_count ve face_save_count backfill

Mevcut 3252 cümleyi genişletilmiş Brown & Levinson (1987) lexiconu ile yeniden hesaplar.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import asyncpg

# Brown & Levinson (1987) Politeness Theory — Face Save Markers
FACE_SAVE_MARKERS = {
    # English positive politeness
    "please",
    "thank",
    "appreciate",
    "acknowledge",
    "respect",
    "understand",
    "commend",
    "welcome",
    "recognize",
    "value",
    "congratulate",
    "honor",
    "grateful",
    "constructive",
    "with all due respect",
    "we appreciate",
    "we acknowledge",
    "we welcome",
    "we value",
    "we understand",
    "we commend",
    "we recognize",
    "i appreciate",
    "i acknowledge",
    "respectfully",
    # Turkish
    "lütfen",
    "teşekkür",
    "takdir",
    "saygı",
    "anlıyoruz",
    "tebrik",
    "memnuniyet",
    "değer",
    "saygıyla",
    "katkı",
}

# Face-Threatening Acts (FTA)
FACE_THREAT_MARKERS = {
    # English
    "demand",
    "insist",
    "reject",
    "refuse",
    "condemn",
    "accuse",
    "violate",
    "breach",
    "illegal",
    "unacceptable",
    "irresponsible",
    "threaten",
    "warn",
    "ultimatum",
    "sanction",
    "punish",
    "impose",
    "force",
    "criticize",
    "blame",
    "failure",
    "failed",
    "must comply",
    "must stop",
    "will not tolerate",
    "strongly urge",
    "call upon",
    "deeply concerned",
    "gross violation",
    # Turkish
    "talep",
    "reddet",
    "kına",
    "yasadışı",
    "kabul edilemez",
    "tehdit",
    "baskı",
    "zorla",
    "yaptırım",
    "suçla",
    "ihlal",
    "uygunsuz",
    "sorumlu",
    "eleştir",
}


def compute_face_acts(text: str) -> tuple[int, int]:
    """Cümle metninden face_save ve face_threat sayılarını hesaplar."""
    lower = text.lower()
    face_save = sum(1 for k in FACE_SAVE_MARKERS if k in lower)
    face_threat = sum(1 for k in FACE_THREAT_MARKERS if k in lower)
    return face_save, face_threat


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(url)

    print("TASK-DB-006 #23 | Backfilling face_threat_count / face_save_count...\n")

    rows = await conn.fetch("SELECT sent_id, text FROM sentences ORDER BY sent_id")
    total = len(rows)
    print(f"Found {total} sentences to process.\n")

    updated = 0
    nonzero_ft = 0
    nonzero_fs = 0

    # Batch update
    batch = []
    for i, row in enumerate(rows, 1):
        sent_id = row["sent_id"]
        text = row["text"] or ""
        fs, ft = compute_face_acts(text)

        if fs > 0:
            nonzero_fs += 1
        if ft > 0:
            nonzero_ft += 1

        batch.append((fs, ft, sent_id))

        if len(batch) >= 200 or i == total:
            await conn.executemany(
                "UPDATE sentences SET face_save_count = $1, face_threat_count = $2 WHERE sent_id = $3",
                batch,
            )
            updated += len(batch)
            batch = []
            print(f"  [{i}/{total}] processed...")

    print(f"\nDone. Updated {updated}/{total} sentences.")
    print(
        f"  face_save_count  > 0: {nonzero_fs} / {total} ({100 * nonzero_fs / total:.1f}%)"
    )
    print(
        f"  face_threat_count > 0: {nonzero_ft} / {total} ({100 * nonzero_ft / total:.1f}%)"
    )

    # Also update politeness_ratio
    print("\nUpdating politeness_ratio...")
    await conn.execute(
        """
        UPDATE sentences
        SET politeness_ratio = face_save_count::float / (face_save_count + face_threat_count + 1)
    """
    )
    print("politeness_ratio updated.")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
