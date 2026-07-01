"""
TASK-DB-005 | Speaker Profiles Diagnostik Script
Hataları #16-#21 için mevcut durumu tespit eder.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import asyncpg


async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)

    conn = await asyncpg.connect(db_url)
    print("=" * 70)
    print("TASK-DB-005: SPEAKER PROFILES DIAGNOSTİK RAPORU")
    print("=" * 70)

    # ── 1. Genel sayım ──────────────────────────────────────────────────────
    row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM speaker_profiles")
    print(f"\n[1] Toplam speaker_profiles satırı : {row['cnt']}")

    # ── 2. Örnek veri ───────────────────────────────────────────────────────
    rows = await conn.fetch("""
        SELECT speaker_id, risk_event_count, avg_sentiment,
               dominant_emotion, dominant_topic, pattern_diversity
        FROM speaker_profiles
        LIMIT 20
    """)
    print("\n[2] Örnek satırlar (ilk 20):")
    print(
        f"{'speaker_id':<30} {'risk_ev':>7} {'avg_sent':>9} {'dom_emo':<20} {'dom_top':<25} {'pat_div':>8}"
    )
    print("-" * 105)
    for r in rows:
        print(
            f"{r['speaker_id']!s:<30} {r['risk_event_count']!s:>7} "
            f"{r['avg_sentiment']!s:>9} {r['dominant_emotion']!s:<20} "
            f"{r['dominant_topic']!s:<25} {r['pattern_diversity']!s:>8}"
        )

    # ── 3. Ortalama değerler ─────────────────────────────────────────────────
    row = await conn.fetchrow("""
        SELECT
            AVG(risk_event_count)   AS avg_risk,
            AVG(avg_sentiment)      AS avg_sent,
            AVG(pattern_diversity)  AS avg_pdiv,
            COUNT(*) FILTER (WHERE risk_event_count = 0) AS zero_risk_cnt,
            COUNT(*) FILTER (WHERE avg_sentiment = 0)   AS zero_sent_cnt,
            COUNT(*) FILTER (WHERE dominant_emotion IS NULL) AS null_emo_cnt,
            COUNT(*) FILTER (WHERE dominant_topic IS NULL)   AS null_top_cnt,
            COUNT(*) FILTER (WHERE pattern_diversity = 0)    AS zero_pdiv_cnt
        FROM speaker_profiles
    """)
    print("\n[3] Ortalama & sıfır/null sayıları:")
    print(f"    AVG(risk_event_count)  = {row['avg_risk']}")
    print(f"    AVG(avg_sentiment)     = {row['avg_sent']}")
    print(f"    AVG(pattern_diversity) = {row['avg_pdiv']}")
    print(f"    risk_event_count = 0   → {row['zero_risk_cnt']} satır")
    print(f"    avg_sentiment = 0      → {row['zero_sent_cnt']} satır")
    print(f"    dominant_emotion NULL  → {row['null_emo_cnt']} satır")
    print(f"    dominant_topic NULL    → {row['null_top_cnt']} satır")
    print(f"    pattern_diversity = 0  → {row['zero_pdiv_cnt']} satır")

    # ── #16: risk_event_count kaynak verisini kontrol et ────────────────────
    print("\n" + "=" * 70)
    print("#16 – risk_event_count kaynağı: sentences.risk_score dağılımı")
    rows = await conn.fetch("""
        SELECT
            COUNT(*) AS total_sentences,
            COUNT(*) FILTER (WHERE risk_score IS NOT NULL) AS has_risk,
            COUNT(*) FILTER (WHERE risk_score >= 5.0)      AS risk_gte_5,
            COUNT(*) FILTER (WHERE risk_score >= 7.0)      AS risk_gte_7,
            AVG(risk_score) FILTER (WHERE risk_score IS NOT NULL) AS avg_risk
        FROM sentences
    """)
    r = rows[0]
    print(f"    Total sentences      : {r['total_sentences']}")
    print(f"    Has risk_score       : {r['has_risk']}")
    print(f"    risk_score >= 5.0    : {r['risk_gte_5']}")
    print(f"    risk_score >= 7.0    : {r['risk_gte_7']}")
    print(f"    AVG(risk_score)      : {r['avg_risk']}")

    # analyses tablosunda risk_score var mı?
    try:
        rows_a = await conn.fetch("""
            SELECT
                COUNT(*) AS total_analyses,
                COUNT(*) FILTER (WHERE risk_score IS NOT NULL) AS has_risk,
                COUNT(*) FILTER (WHERE risk_score >= 5.0)      AS risk_gte_5,
                AVG(risk_score) FILTER (WHERE risk_score IS NOT NULL) AS avg_risk
            FROM analyses
        """)
        ra = rows_a[0]
        print("\n    [analyses tablosu]")
        print(f"    Total analyses       : {ra['total_analyses']}")
        print(f"    Has risk_score       : {ra['has_risk']}")
        print(f"    risk_score >= 5.0    : {ra['risk_gte_5']}")
        print(f"    AVG(risk_score)      : {ra['avg_risk']}")
    except Exception as e:
        print(f"    [analyses tablosu erişilemedi]: {e}")

    # ── #17: avg_sentiment kaynağı ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print("#17 – avg_sentiment kaynağı: sentences.vader_compound dağılımı")
    rows = await conn.fetch("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE vader_compound IS NOT NULL)  AS has_vader,
            COUNT(*) FILTER (WHERE vader_compound = 0)          AS zero_vader,
            AVG(vader_compound) FILTER (WHERE vader_compound IS NOT NULL) AS avg_vader,
            MIN(vader_compound) AS min_vader,
            MAX(vader_compound) AS max_vader
        FROM sentences
    """)
    r = rows[0]
    print(f"    total sentences        : {r['total']}")
    print(f"    has vader_compound     : {r['has_vader']}")
    print(f"    vader_compound = 0     : {r['zero_vader']}")
    print(f"    AVG(vader_compound)    : {r['avg_vader']}")
    print(f"    MIN / MAX              : {r['min_vader']} / {r['max_vader']}")

    # ── #18: dominant_emotion kaynağı ───────────────────────────────────────
    print("\n" + "=" * 70)
    print("#18 – dominant_emotion: sentences.emotion_category dağılımı")
    rows = await conn.fetch("""
        SELECT emotion_category, COUNT(*) AS cnt
        FROM sentences
        WHERE emotion_category IS NOT NULL
        GROUP BY emotion_category
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print(f"    {'emotion_category':<30} {'count':>8}")
    print("    " + "-" * 42)
    for r in rows:
        print(f"    {r['emotion_category']!s:<30} {r['cnt']:>8}")

    # analyses.emotion_label kontrolü
    try:
        rows_ae = await conn.fetch("""
            SELECT emotion_label, COUNT(*) AS cnt
            FROM analyses
            WHERE emotion_label IS NOT NULL
            GROUP BY emotion_label
            ORDER BY cnt DESC
            LIMIT 10
        """)
        print("\n    [analyses.emotion_label dağılımı]")
        for r in rows_ae:
            print(f"    {r['emotion_label']!s:<30} {r['cnt']:>8}")
    except Exception as e:
        print(f"    [analyses.emotion_label erişilemedi]: {e}")

    # ── #19: dominant_topic mevcut değerleri ────────────────────────────────
    print("\n" + "=" * 70)
    print("#19 – dominant_topic: mevcut değerlerin dağılımı")
    rows = await conn.fetch("""
        SELECT dominant_topic, COUNT(*) AS cnt
        FROM speaker_profiles
        WHERE dominant_topic IS NOT NULL
        GROUP BY dominant_topic
        ORDER BY cnt DESC
        LIMIT 20
    """)
    print(f"    {'dominant_topic':<40} {'count':>6}")
    print("    " + "-" * 48)
    for r in rows:
        print(f"    {r['dominant_topic']!s:<40} {r['cnt']:>6}")

    # sentences.dominant_topic kaynağı
    rows2 = await conn.fetch("""
        SELECT dominant_topic, COUNT(*) AS cnt
        FROM sentences
        WHERE dominant_topic IS NOT NULL
        GROUP BY dominant_topic
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print("\n    [sentences.dominant_topic top-15]")
    for r in rows2:
        print(f"    {r['dominant_topic']!s:<40} {r['cnt']:>6}")

    # ── #20: pattern_diversity dağılımı ────────────────────────────────────
    print("\n" + "=" * 70)
    print("#20 – pattern_diversity: mevcut değer dağılımı")
    rows = await conn.fetch("""
        SELECT pattern_diversity, COUNT(*) AS cnt
        FROM speaker_profiles
        GROUP BY pattern_diversity
        ORDER BY pattern_diversity
    """)
    print(f"    {'pattern_diversity':>18} {'count':>6}")
    print("    " + "-" * 26)
    for r in rows:
        print(f"    {float(r['pattern_diversity']):>18.4f} {r['cnt']:>6}")

    # sentences.rhetoric_type dağılımı
    rows2 = await conn.fetch("""
        SELECT rhetoric_type, COUNT(*) AS cnt
        FROM sentences
        WHERE rhetoric_type IS NOT NULL
        GROUP BY rhetoric_type
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print("\n    [sentences.rhetoric_type top-15]")
    for r in rows2:
        print(f"    {r['rhetoric_type']!s:<35} {r['cnt']:>6}")

    # Unique rhetoric_type sayısı per speaker
    rows3 = await conn.fetch("""
        SELECT sent.speaker_id, COUNT(DISTINCT sent.rhetoric_type) AS unique_rt
        FROM sentences sent
        WHERE sent.rhetoric_type IS NOT NULL AND sent.speaker_id IS NOT NULL
        GROUP BY sent.speaker_id
        ORDER BY unique_rt DESC
        LIMIT 10
    """)
    print("\n    [Per speaker unique rhetoric_type (top-10)]")
    for r in rows3:
        print(f"    speaker={r['speaker_id']!s:<30} unique_rt={r['unique_rt']}")

    # ── #21: Genel audit ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("#21 – Genel audit: sütun bazında null/zero oranları")
    audit_cols = [
        ("avg_sentiment", "= 0 veya NULL"),
        ("dominant_emotion", "NULL"),
        ("dominant_topic", "NULL"),
        ("risk_event_count", "= 0"),
        ("pattern_diversity", "= 0"),
        ("avg_hedging_score", "= 0 veya NULL"),
        ("avg_politeness_ratio", "= 0 veya NULL"),
        ("lexical_diversity", "= 0"),
        ("diplo_vocab_score", "= 0"),
        ("demand_count", "= 0"),
    ]
    total_row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM speaker_profiles")
    total = total_row["cnt"]
    print(f"\n    {'Sütun':<25} {'Sorunlu':>9} {'Toplam':>8} {'Oran':>7}")
    print("    " + "-" * 55)
    for col, desc in audit_cols:
        try:
            if "NULL" in desc and "= 0" in desc:
                r = await conn.fetchrow(
                    f"SELECT COUNT(*) AS cnt FROM speaker_profiles "
                    f"WHERE {col} IS NULL OR {col} = 0"
                )
            elif "NULL" in desc:
                r = await conn.fetchrow(
                    f"SELECT COUNT(*) AS cnt FROM speaker_profiles WHERE {col} IS NULL"
                )
            else:
                r = await conn.fetchrow(
                    f"SELECT COUNT(*) AS cnt FROM speaker_profiles WHERE {col} = 0"
                )
            cnt = r["cnt"]
            pct = (cnt / total * 100) if total > 0 else 0
            print(f"    {col:<25} {cnt:>9} {total:>8} {pct:>6.1f}%")
        except Exception as e:
            print(f"    {col:<25} ERROR: {e}")

    await conn.close()
    print("\n" + "=" * 70)
    print("Diagnostik tamamlandı.")


if __name__ == "__main__":
    asyncio.run(main())
