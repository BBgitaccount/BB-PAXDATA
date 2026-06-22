"""
scripts/recalculate_speaker_profiles.py
TASK-DB-005 | Hata #16-#21 düzeltmeleri

Mevcut speaker_profiles satırlarını doğru kaynak verilerle yeniden hesaplar.

Düzeltme Stratejileri (Diagnostik Bulgularına Göre):
  #16 risk_event_count  → ai_sentence_analysis.risk_score (max=2, eşik=1; ya da
                          sentences.risk_level = 'HIGH'/'CRITICAL')
  #17 avg_sentiment     → ai_sentence_analysis.sentiment_score (non-NULL, non-zero);
                          fallback: sentences.vader_compound (non-zero olanlar)
  #18 dominant_emotion  → sentences.emotion_category (non-NULL); fallback:
                          ai_sentence_analysis.diplomatic_tone kategorize et
  #19 dominant_topic    → topic_assignments.topic_label (non-NULL, non '-1');
                          fallback: "uncategorized"
  #20 pattern_diversity → Shannon entropy normalize (rhetoric_type dağılımı)
  #21 hedging/polite    → sentences.hedging_score / politeness_ratio (mevcut en iyi)
"""

from __future__ import annotations

import asyncio
import math
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import asyncpg


# ── Yardımcı: Shannon entropy (normalize) ──────────────────────────────────────
def shannon_entropy_normalized(counts: dict[str, int]) -> float:
    """
    Verilen kategorilerin count dict'i için normalize Shannon entropy hesaplar.
    Sonuç: 0.0 (tek tip) – 1.0 (eşit dağılım, max çeşitlilik).
    """
    total = sum(counts.values())
    if total == 0 or len(counts) < 2:
        return 0.0
    probs = [c / total for c in counts.values() if c > 0]
    entropy = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(len(probs))
    return entropy / max_entropy if max_entropy > 0 else 0.0


# ── Yardımcı: risk_level string → yüksek risk mi? ─────────────────────────────
_HIGH_RISK_LEVELS = {"high", "critical", "CRITICAL", "HIGH"}


async def fetch_speaker_data(conn: asyncpg.Connection, speaker_id: str) -> dict:
    """Bir konuşmacı için tüm kaynak verileri toplar."""
    data: dict = {"speaker_id": speaker_id}

    # ── sentences ──────────────────────────────────────────────────────────────
    sentences = await conn.fetch(
        """
        SELECT sent_id, vader_compound, emotion_category,
               risk_score, rhetoric_type, dominant_topic,
               hedging_score, politeness_ratio, dominant_frame,
               audience_type, demand_type, word_count
        FROM sentences
        WHERE speaker_id = $1
        """,
        speaker_id,
    )
    data["sentences"] = sentences

    # ── ai_sentence_analysis ───────────────────────────────────────────────────
    sent_ids = [r["sent_id"] for r in sentences]
    if sent_ids:
        ai_rows = await conn.fetch(
            """
            SELECT a.sent_id, a.risk_score, a.risk_level,
                   a.sentiment_score, a.ai_emotion, a.diplomatic_tone,
                   a.ai_hedging_score, a.ai_politeness_score,
                   a.sentiment_category
            FROM ai_sentence_analysis a
            WHERE a.sent_id = ANY($1::text[])
            """,
            sent_ids,
        )
        data["ai_rows"] = {r["sent_id"]: r for r in ai_rows}
    else:
        data["ai_rows"] = {}

    # ── topic_assignments ──────────────────────────────────────────────────────
    if sent_ids:
        topic_rows = await conn.fetch(
            """
            SELECT analysis_id, topic_label, topic_scores
            FROM topic_assignments
            WHERE analysis_id = ANY($1::text[])
              AND topic_label IS NOT NULL
              AND topic_label != '-1'
            """,
            sent_ids,
        )
        data["topic_labels"] = [r["topic_label"] for r in topic_rows]
    else:
        data["topic_labels"] = []

    return data


def compute_profile_updates(data: dict) -> dict:
    """Kaynak verilerden speaker_profiles güncellemelerini hesaplar."""
    sentences = data["sentences"]
    ai_map = data["ai_rows"]
    topic_labels = data["topic_labels"]
    updates: dict = {}

    if not sentences:
        return updates

    # ── #16: risk_event_count ──────────────────────────────────────────────────
    # Strateji:
    #   1. ai_sentence_analysis.risk_score >= 5 (AI skoru 1-10 beklenen)
    #   2. Fallback: ai_sentence_analysis.risk_level IN ('HIGH','CRITICAL')
    #   3. Fallback2: ai_sentence_analysis.risk_score >= 1 (en gevşek)
    risk_count = 0
    for s in sentences:
        sid = s["sent_id"]
        ai = ai_map.get(sid)
        if ai and ai["risk_score"] is not None and ai["risk_score"] >= 5:
            risk_count += 1
        elif (
            ai
            and ai["risk_level"] is not None
            and str(ai["risk_level"]).upper() in _HIGH_RISK_LEVELS
        ):
            risk_count += 1
    # Fallback: risk_score >= 1 (anlamlı risk sinyali)
    if risk_count == 0:
        for s in sentences:
            sid = s["sent_id"]
            ai = ai_map.get(sid)
            if ai and ai["risk_score"] is not None and ai["risk_score"] >= 1:
                risk_count += 1
    updates["risk_event_count"] = risk_count

    # ── #17: avg_sentiment ──────────────────────────────────────────────────
    # Strateji:
    #   1. vader_compound (non-NULL, non-zero) — en güvenilir kısa vadeli ölçek
    #   2. Fallback: AI sentiment_score (non-NULL, non-zero, 0-1 scale → -1..1)
    vader_vals = [
        s["vader_compound"]
        for s in sentences
        if s["vader_compound"] is not None and s["vader_compound"] != 0.0
    ]
    if vader_vals:
        avg_sent = sum(vader_vals) / len(vader_vals)
        sent_source = "vader"
    else:
        # AI sentiment_score: 0-1 ölçeğinde; 0 veya 0.5 = neutral/eksik, filtrele
        ai_sentiments = [
            ai["sentiment_score"]
            for s in sentences
            if (ai := ai_map.get(s["sent_id"]))
            and ai["sentiment_score"] is not None
            and ai["sentiment_score"] != 0.0
            and ai["sentiment_score"] != 0.5
        ]
        if ai_sentiments:
            # 0-1 → -1..1 dönüşümü
            normalized = [(v - 0.5) * 2.0 for v in ai_sentiments]
            avg_sent = sum(normalized) / len(normalized)
            sent_source = "ai"
        else:
            avg_sent = 0.0
            sent_source = "none"
    updates["avg_sentiment"] = avg_sent

    # ── #18: dominant_emotion ──────────────────────────────────────────────────
    # Kaynak 1: sentences.emotion_category (NOT NULL)
    emotions = [s["emotion_category"] for s in sentences if s["emotion_category"]]
    # Kaynak 2: AI diplomatic_tone → emotion mapping
    if not emotions:
        tone_emotion_map = {
            "cooperative": "cooperative",
            "constructive": "constructive",
            "neutral": "neutral_cautious",
            "cautious": "neutral_cautious",
            "concerned": "concerned",
            "confrontational": "confrontational",
            "aggressive": "confrontational",
        }
        for s in sentences:
            ai = ai_map.get(s["sent_id"])
            if ai and ai["diplomatic_tone"]:
                tone = ai["diplomatic_tone"].lower().strip()
                mapped = tone_emotion_map.get(tone)
                if mapped:
                    emotions.append(mapped)

    updates["dominant_emotion"] = (
        Counter(emotions).most_common(1)[0][0] if emotions else None
    )

    # Behavioral percentages (sentences.emotion_category)
    total_sents = len(sentences)
    emo_counter = Counter(
        s["emotion_category"] for s in sentences if s["emotion_category"]
    )
    updates["cooperative_pct"] = emo_counter.get("cooperative", 0) / total_sents
    updates["constructive_pct"] = emo_counter.get("constructive", 0) / total_sents
    updates["neutral_pct"] = emo_counter.get("neutral_cautious", 0) / total_sents
    updates["concerned_pct"] = emo_counter.get("concerned", 0) / total_sents
    updates["confrontational_pct"] = emo_counter.get("confrontational", 0) / total_sents

    # ── #19: dominant_topic ────────────────────────────────────────────────────
    # Kaynak 1: topic_assignments.topic_label (non-NULL, non '-1')
    if topic_labels:
        clean_labels = [
            lbl for lbl in topic_labels if lbl and lbl.strip() != "-1" and len(lbl) > 3
        ]
        if clean_labels:
            topic_counter = Counter(clean_labels)
            updates["dominant_topic"] = topic_counter.most_common(1)[0][0]
            top3 = [t for t, _ in topic_counter.most_common(3)]
            updates["top_topics"] = ", ".join(top3)
        else:
            updates["dominant_topic"] = "uncategorized"
            updates["top_topics"] = None
    else:
        # Fallback: sentences.dominant_topic (non-NULL, non '-1', non stop-word list)
        raw_topics = [
            s["dominant_topic"]
            for s in sentences
            if s["dominant_topic"]
            and s["dominant_topic"].strip() not in {"-1", ""}
            and not _is_stop_word_list(s["dominant_topic"])
        ]
        if raw_topics:
            topic_counter = Counter(raw_topics)
            updates["dominant_topic"] = topic_counter.most_common(1)[0][0]
            top3 = [t for t, _ in topic_counter.most_common(3)]
            updates["top_topics"] = ", ".join(top3)
        else:
            updates["dominant_topic"] = "uncategorized"
            updates["top_topics"] = None

    # ── #20: pattern_diversity (Shannon entropy) ───────────────────────────────
    rhetoric_counts = Counter(
        s["rhetoric_type"] for s in sentences if s["rhetoric_type"]
    )
    updates["pattern_diversity"] = shannon_entropy_normalized(dict(rhetoric_counts))

    # ── #21: hedging, politeness (best available source) ─────────────────────
    # ai_sentence_analysis.ai_hedging_score (AI-produced 0-1 scale)
    ai_hedging = [
        ai["ai_hedging_score"]
        for s in sentences
        if (ai := ai_map.get(s["sent_id"])) and ai["ai_hedging_score"] is not None
    ]
    if ai_hedging:
        updates["avg_hedging_score"] = sum(ai_hedging) / len(ai_hedging)
    else:
        sent_hedging = [
            s["hedging_score"] for s in sentences if s["hedging_score"] is not None
        ]
        updates["avg_hedging_score"] = (
            sum(sent_hedging) / len(sent_hedging) if sent_hedging else 0.0
        )

    # ai_sentence_analysis.ai_politeness_score
    ai_politeness = [
        ai["ai_politeness_score"]
        for s in sentences
        if (ai := ai_map.get(s["sent_id"])) and ai["ai_politeness_score"] is not None
    ]
    if ai_politeness:
        updates["avg_politeness_ratio"] = sum(ai_politeness) / len(ai_politeness)
    else:
        sent_polite = [
            s["politeness_ratio"]
            for s in sentences
            if s["politeness_ratio"] is not None
        ]
        updates["avg_politeness_ratio"] = (
            sum(sent_polite) / len(sent_polite) if sent_polite else 0.0
        )

    # dominant_frame, dominant_audience
    frames = [s["dominant_frame"] for s in sentences if s["dominant_frame"]]
    updates["dominant_frame"] = Counter(frames).most_common(1)[0][0] if frames else None

    audiences = [s["audience_type"] for s in sentences if s["audience_type"]]
    updates["dominant_audience"] = (
        Counter(audiences).most_common(1)[0][0] if audiences else None
    )

    # avg_sentiment quality flag (informational)
    updates["_sentiment_source"] = sent_source
    updates["_risk_source"] = "ai_level" if risk_count > 0 else "none"

    return updates


def _is_stop_word_list(text: str) -> bool:
    """BERTopic'in ürettiği kelime listesi formatını tespit eder: 'the, is, and' gibi."""
    if not text:
        return False
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return False
    # Çoğunlukla 1-3 karakter kelimeler, stop word'ler
    _STOP = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "at",
        "for",
        "that",
        "this",
        "it",
        "he",
        "she",
        "we",
        "they",
        "you",
        "i",
        "with",
        "from",
        "as",
    }
    stop_count = sum(1 for p in parts if p.lower() in _STOP)
    return stop_count >= max(1, len(parts) // 2)


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]

    conn = await asyncpg.connect(url)
    print("TASK-DB-005 | Recalculating speaker_profiles...\n")

    # Tüm speaker_id listesini al
    speaker_rows = await conn.fetch(
        "SELECT speaker_id FROM speaker_profiles ORDER BY speaker_id"
    )
    total = len(speaker_rows)
    print(f"Found {total} speaker profiles to recalculate.\n")

    updated = 0
    stats = {
        "risk_nonzero": 0,
        "sentiment_ai": 0,
        "sentiment_vader": 0,
        "emotion_found": 0,
        "topic_from_assignments": 0,
        "topic_fallback": 0,
        "topic_uncategorized": 0,
        "pattern_div_gt0": 0,
    }

    for i, row in enumerate(speaker_rows, 1):
        speaker_id = row["speaker_id"]

        data = await fetch_speaker_data(conn, speaker_id)
        updates = compute_profile_updates(data)

        if not updates:
            continue

        # Stats
        if updates.get("risk_event_count", 0) > 0:
            stats["risk_nonzero"] += 1
        if updates.get("_sentiment_source") == "ai":
            stats["sentiment_ai"] += 1
        else:
            stats["sentiment_vader"] += 1
        if updates.get("dominant_emotion"):
            stats["emotion_found"] += 1
        if updates.get("dominant_topic") == "uncategorized":
            stats["topic_uncategorized"] += 1
        elif data["topic_labels"]:
            stats["topic_from_assignments"] += 1
        else:
            stats["topic_fallback"] += 1
        if updates.get("pattern_diversity", 0) > 0:
            stats["pattern_div_gt0"] += 1

        # Remove internal tracking keys before SQL
        updates.pop("_sentiment_source", None)
        updates.pop("_risk_source", None)

        # Build UPDATE query
        set_clauses = ", ".join(
            f"{col} = ${j + 2}" for j, col in enumerate(updates.keys())
        )
        values = [speaker_id, *list(updates.values())]

        await conn.execute(
            f"UPDATE speaker_profiles SET {set_clauses} WHERE speaker_id = $1",
            *values,
        )
        updated += 1

        if i % 10 == 0 or i == total:
            print(f"  [{i}/{total}] processed...")

    print(f"\nDone. Updated {updated}/{total} profiles.\n")
    print("=== Statistics ===")
    print(f"  risk_event_count > 0      : {stats['risk_nonzero']} / {total}")
    print(f"  avg_sentiment (AI source) : {stats['sentiment_ai']}")
    print(f"  avg_sentiment (vader)     : {stats['sentiment_vader']}")
    print(f"  dominant_emotion found    : {stats['emotion_found']} / {total}")
    print(f"  dominant_topic (topic_assignments) : {stats['topic_from_assignments']}")
    print(f"  dominant_topic (sentences fallback): {stats['topic_fallback']}")
    print(f"  dominant_topic uncategorized       : {stats['topic_uncategorized']}")
    print(f"  pattern_diversity > 0     : {stats['pattern_div_gt0']} / {total}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
