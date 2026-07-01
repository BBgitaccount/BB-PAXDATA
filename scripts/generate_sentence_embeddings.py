"""
scripts/generate_sentence_embeddings.py
TASK-DB-006 #25b — sentences.embedding backfill

sentence-transformers/all-MiniLM-L6-v2 modeli kullanarak
mevcut tüm cümleler için 384-boyutlu SBERT embedding hesaplar
ve pgvector sütununa yazar.

Özellikler:
  - Batch size: 64
  - Hata toleranslı: her batch try/except
  - Zaten embedding'i olan cümleleri atlar (--skip-existing default)
  - İlerleme gösterimi
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import asyncpg

BATCH_SIZE = 64
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_model():
    """Sentence transformer modelini yükle."""
    try:
        from sentence_transformers import SentenceTransformer

        print(f"Loading model: {MODEL_NAME}...")
        model = SentenceTransformer(MODEL_NAME)
        print(f"Model loaded. Dimension: {model.get_sentence_embedding_dimension()}")
        return model
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        print("  Run: pip install sentence-transformers")
        return None
    except Exception as e:
        print(f"ERROR loading model: {e}")
        return None


def encode_batch(model, texts: list[str]) -> list[list[float]]:
    """Metinleri vektöre çevir — sync, thread pool içinde çalışır."""
    vectors = model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2 normalize — cosine similarity için
    )
    return [v.tolist() for v in vectors]


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(url)

    print("TASK-DB-006 #25b | Generating sentence embeddings...\n")

    # pgvector extension kontrolü
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        pass  # Zaten varsa sorun değil

    # Model yükle
    model = load_model()
    if model is None:
        await conn.close()
        return

    dim = model.get_sentence_embedding_dimension()
    print(f"\nVector dimension: {dim}")

    # Embedding olmayan cümleleri al
    rows = await conn.fetch("""
        SELECT sent_id, text
        FROM sentences
        WHERE embedding IS NULL
          AND text IS NOT NULL
          AND LENGTH(text) > 5
        ORDER BY sent_id
    """)
    total = len(rows)
    print(f"Sentences without embeddings: {total}\n")

    if total == 0:
        print("All sentences already have embeddings.")
        await conn.close()
        return

    # Batch işleme
    loop = asyncio.get_event_loop()
    success = 0
    errors = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]
        sent_ids = [r["sent_id"] for r in batch]
        texts = [r["text"] for r in batch]

        try:
            # CPU-bound encoding — thread pool'da çalıştır
            vectors = await loop.run_in_executor(None, encode_batch, model, texts)

            # pgvector'e yaz: float listesini vector tipine cast et
            updates = []
            for sent_id, vec in zip(sent_ids, vectors):
                # asyncpg için vector formatı: '[0.1,0.2,...]' string
                vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                updates.append((vec_str, sent_id))

            await conn.executemany(
                "UPDATE sentences SET embedding = $1::vector WHERE sent_id = $2",
                updates,
            )
            success += len(batch)

        except Exception as e:
            errors += len(batch)
            print(f"  ERROR batch {batch_start // BATCH_SIZE + 1}: {e}")

        processed = min(batch_start + BATCH_SIZE, total)
        if processed % (BATCH_SIZE * 5) == 0 or processed == total:
            print(
                f"  [{processed}/{total}] done (success={success}, errors={errors})..."
            )

    print("\nDone.")
    print(f"  Success : {success}")
    print(f"  Errors  : {errors}")
    print(f"  Total   : {total}")

    # Doğrulama
    r = await conn.fetchrow(
        "SELECT COUNT(*) AS cnt FROM sentences WHERE embedding IS NOT NULL"
    )
    print(f"\n  embedding IS NOT NULL: {r['cnt']} / {total + success}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
