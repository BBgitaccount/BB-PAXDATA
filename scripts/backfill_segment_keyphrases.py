import asyncio
import json
import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.db.models import Segment
from bb_paxdata.infrastructure.db.session import SessionLocal


async def main():
    print("Starting TASK-DB-007 backfill script for segment keyphrases and TF-IDF...")

    settings = get_settings()
    print(f"Database URL: {settings.database_url}")

    # 1. Load KeyBERT model
    print("Loading KeyBERT model...")
    from keybert import KeyBERT

    kw_model = KeyBERT()

    async with SessionLocal() as session:
        # Fetch all segments
        print("Fetching all segments from database...")
        stmt = select(Segment)
        res = await session.execute(stmt)
        segments = res.scalars().all()
        print(f"Found {len(segments)} segments to process.")

        # 2. Extract KeyBERT keywords for each segment
        print("Extracting KeyBERT keywords...")
        for i, segment in enumerate(segments, 1):
            if not segment.text:
                continue
            try:
                # Extract keywords with KeyBERT
                keywords = kw_model.extract_keywords(
                    segment.text, keyphrase_ngram_range=(1, 3), top_n=10
                )
                key_phrases = [kw[0] for kw in keywords]
                segment.key_phrases = json.dumps(key_phrases, ensure_ascii=False)
            except Exception as e:
                print(
                    f"  Error extracting KeyBERT keywords for segment {segment.seg_id}: {e}"
                )

            if i % 50 == 0 or i == len(segments):
                print(f"  [{i}/{len(segments)}] KeyBERT extraction completed...")

        # 3. Fit TF-IDF Vectorizer on all segment texts
        print("Computing TF-IDF scores on segment corpus...")
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(max_features=50, stop_words="english")
        corpus = [seg.text for seg in segments if seg.text]

        if corpus:
            tfidf_matrix = vectorizer.fit_transform(corpus)
            feature_names = vectorizer.get_feature_names_out()

            corpus_idx = 0
            for i, segment in enumerate(segments, 1):
                if not segment.text:
                    continue
                try:
                    row = tfidf_matrix.getrow(corpus_idx)
                    words_scores = {}
                    for col_idx, score in zip(row.indices, row.data):
                        words_scores[feature_names[col_idx]] = round(float(score), 4)
                    # Sort by score descending
                    sorted_words_scores = dict(
                        sorted(words_scores.items(), key=lambda x: x[1], reverse=True)
                    )
                    segment.tfidf_keywords = json.dumps(
                        sorted_words_scores, ensure_ascii=False
                    )
                    corpus_idx += 1
                except Exception as e:
                    print(
                        f"  Error extracting TF-IDF for segment {segment.seg_id}: {e}"
                    )

                if i % 50 == 0 or i == len(segments):
                    print(f"  [{i}/{len(segments)}] TF-IDF extraction completed...")

        # Commit all updates to DB
        print("Saving updates to database...")
        await session.commit()
        print("Backfill for segment keyphrases and TF-IDF completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
