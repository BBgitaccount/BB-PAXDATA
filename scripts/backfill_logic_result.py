"""
scripts/backfill_logic_result.py
TASK-DB-006 #24 — logic_result PASS/WARN/FAIL backfill

Mevcut cümleleri formula_validation_logs'taki flag bilgilerine göre
yeniden sınıflandırır.

Strateji:
  - formula_validation_logs'ta FAIL kayıtları olan sent_id'ler analiz edilir.
  - Yüksek-önem anomali içerenler → FAIL
  - Düşük-önem anomali içerenler → WARN
  - Hiç FAIL kaydı olmayanlar → PASS
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import asyncpg

# Yüksek-önem anomali prefiksleri — bunlar FAIL gerektirir
HIGH_SEVERITY_PREFIXES = (
    "HIGH_RISK_THRESHOLD",
    "EXTREME_NEGATIVE_SENTIMENT",
    "POWER_ASYMMETRY_ANOMALY",
    "PLAY_TALK_ANOMALY",
)


def classify_logic_result(formula_check_names: list[str]) -> str:
    """
    formula_validation_logs'taki FAIL check_type isimleri listesinden
    logic_result belirler.
    """
    if not formula_check_names:
        return "PASS"
    for name in formula_check_names:
        if any(name.upper().startswith(p) for p in HIGH_SEVERITY_PREFIXES):
            return "FAIL"
    return "WARN"


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(url)

    print("TASK-DB-006 #24 | Backfilling logic_result (PASS/WARN/FAIL)...\n")

    # formula_validation_logs şemasını kontrol et
    cols = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'formula_validation_logs'
        ORDER BY ordinal_position
    """
    )
    col_names = [r["column_name"] for r in cols]
    print(f"formula_validation_logs columns: {col_names}\n")

    # Tüm sentences'ı al
    all_sents = await conn.fetch("SELECT sent_id FROM sentences")
    total = len(all_sents)
    all_sent_ids = {r["sent_id"] for r in all_sents}
    print(f"Total sentences: {total}")

    # formula_validation_logs'tan FAIL satırlarını topla
    # Schema: entity_id = sent_id, entity_type = 'sentence', formula_name, status
    fail_logs = await conn.fetch(
        """
        SELECT entity_id AS sid, formula_name AS cname, status AS result
        FROM formula_validation_logs
        WHERE entity_type = 'sentence'
          AND status = 'FAIL'
    """
    )

    # sent_id → [formula_name listesi]
    from collections import defaultdict

    sid_checks: dict[str, list[str]] = defaultdict(list)
    for r in fail_logs:
        if r["sid"]:
            sid_checks[r["sid"]].append(str(r["cname"] or ""))
    print(f"Sentences with FAIL entries: {len(sid_checks)}\n")

    # Her cümle için logic_result hesapla
    updates = []
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for sent_id in all_sent_ids:
        checks = sid_checks.get(sent_id, [])
        result = classify_logic_result(checks)
        counts[result] += 1
        updates.append((result, sent_id))

    # Batch update
    batch_size = 500
    for i in range(0, len(updates), batch_size):
        batch = updates[i : i + batch_size]
        await conn.executemany(
            "UPDATE sentences SET logic_result = $1 WHERE sent_id = $2",
            batch,
        )
        print(f"  Updated {min(i + batch_size, len(updates))}/{len(updates)}...")

    print("\nDone. Results:")
    print(f"  PASS : {counts['PASS']} ({100 * counts['PASS'] / total:.1f}%)")
    print(f"  WARN : {counts['WARN']} ({100 * counts['WARN'] / total:.1f}%)")
    print(f"  FAIL : {counts['FAIL']} ({100 * counts['FAIL'] / total:.1f}%)")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
