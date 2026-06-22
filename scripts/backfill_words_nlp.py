import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog
from sqlalchemy import select

from bb_paxdata.application.domain.services.hedging_service import HedgingService
from bb_paxdata.application.domain.services.language_detector import LanguageDetector
from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.db.models import Sentence, Word
from bb_paxdata.infrastructure.db.session import SessionLocal
from bb_paxdata.infrastructure.nlp.negation_detector import SpacyNegationDetector
from bb_paxdata.infrastructure.nlp.spacy_manager import SpacyModelManager

logger = structlog.get_logger(__name__)


async def backfill():
    print("Starting words table backfill...")
    settings = get_settings()
    print(f"Database URL: {settings.database_url}")

    lang_detector = LanguageDetector()
    negation_detector = SpacyNegationDetector()
    hedging_svc = HedgingService()

    async with SessionLocal() as session:
        # Find all sentences that have words
        stmt = select(Sentence.sent_id, Sentence.text, Sentence.file_id).where(
            Sentence.sent_id.in_(select(Word.sent_id))
        )
        result = await session.execute(stmt)
        sentences_to_process = result.fetchall()

        total_sentences = len(sentences_to_process)
        print(f"Found {total_sentences} sentences to backfill.")

        processed_count = 0
        batch_size = 100

        for i in range(0, total_sentences, batch_size):
            batch = sentences_to_process[i : i + batch_size]

            for sent_id, sentence_text, file_id in batch:
                try:
                    # Detect language
                    lang = lang_detector.detect(sentence_text).lower()

                    # Get spaCy model
                    nlp = SpacyModelManager.get_model(lang)
                    doc = nlp(sentence_text)
                    spacy_tokens = [t for t in doc if not t.is_space]

                    # Detect negation cues
                    neg_res = await negation_detector.detect(
                        sentence_text, sent_id, lang
                    )
                    negation_cues = neg_res.cues if neg_res else []

                    # Hedging spans
                    hedging_spans = []
                    for h_cat, h_pattern in hedging_svc._patterns.items():
                        if h_cat == "anti_hedge":
                            continue
                        for match in h_pattern.finditer(sentence_text):
                            hedging_spans.append((match.start(), match.end()))

                    # Determine lexicon and stopwords
                    if lang == "tr":
                        from bb_paxdata.application.domain.lexicon.tr_diplo_lexicon import (
                            DIPLO_LEXICON_TR as lexicon,
                        )
                    else:
                        from bb_paxdata.application.domain.services.sentiment_service import (
                            SentimentService,
                        )

                        lexicon = SentimentService.DIPLO_LEXICON

                    # Query existing words for this sentence
                    word_stmt = (
                        select(Word)
                        .where(Word.sent_id == sent_id)
                        .order_by(Word.word_position)
                    )
                    word_res = await session.execute(word_stmt)
                    db_words = word_res.scalars().all()

                    for w_idx, db_word in enumerate(db_words):
                        if w_idx < len(spacy_tokens):
                            spacy_token = spacy_tokens[w_idx]

                            # Clean and check
                            token_clean = spacy_token.text.strip(",.!?;:()\"'")
                            token_lower = token_clean.lower()

                            w_score = lexicon.get(token_lower, 0.0)
                            if w_score == 0.0:
                                if lang == "tr":
                                    from bb_paxdata.application.domain.services.sentiment_service import (
                                        SentimentService,
                                    )

                                    w_score = SentimentService.DIPLO_LEXICON.get(
                                        token_lower, 0.0
                                    )
                                else:
                                    from bb_paxdata.application.domain.lexicon.tr_diplo_lexicon import (
                                        DIPLO_LEXICON_TR,
                                    )

                                    w_score = DIPLO_LEXICON_TR.get(token_lower, 0.0)

                            # Determine negation
                            is_neg = False
                            for cue in negation_cues:
                                if spacy_token.i in getattr(
                                    cue, "scope_token_indices", []
                                ):
                                    is_neg = True
                                    break
                                if spacy_token.text in getattr(cue, "scope_tokens", []):
                                    is_neg = True
                                    break
                                if (
                                    getattr(cue, "cue_start", -1)
                                    <= spacy_token.idx
                                    < getattr(cue, "cue_end", -1)
                                ):
                                    is_neg = True
                                    break

                            # Determine hedging
                            is_hdg = any(
                                start <= spacy_token.idx < end
                                for start, end in hedging_spans
                            )

                            # Update fields
                            db_word.lemma = spacy_token.lemma_
                            db_word.pos_tag = spacy_token.pos_
                            db_word.dep_label = spacy_token.dep_
                            db_word.entity_type = spacy_token.ent_type_ or None
                            db_word.is_negated = is_neg
                            db_word.is_hedge = is_hdg
                            db_word.is_diplomatic_term = w_score != 0.0
                            db_word.char_offset_start = spacy_token.idx
                            db_word.char_offset_end = spacy_token.idx + len(
                                spacy_token.text
                            )
                            if spacy_token.ent_type_ != "":
                                db_word.is_named_entity = True
                except Exception as e:
                    print(f"Error processing sentence {sent_id}: {e}")

            await session.commit()
            processed_count += len(batch)
            print(f"Processed {processed_count}/{total_sentences} sentences.")

    print("Backfill completed successfully.")


if __name__ == "__main__":
    asyncio.run(backfill())
