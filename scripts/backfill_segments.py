import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.config.settings import get_settings
from bb_paxdata.domain.services.framing_service import FramingService
from bb_paxdata.domain.services.ner_service import SpacyNERService
from bb_paxdata.infrastructure.db.models import Segment, Sentence
from bb_paxdata.infrastructure.db.segment_enrichment_gateway import (
    SegmentEnrichmentGateway,
)
from bb_paxdata.infrastructure.db.session import SessionLocal


async def backfill():
    print("Backfill scripti baslatiliyor...")

    settings = get_settings()
    print(f"Veritabani URL: {settings.database_url}")

    ner_service = SpacyNERService()
    framing_service = FramingService()
    gateway = SegmentEnrichmentGateway()

    async with SessionLocal() as session:
        # Prevent expiring instances on commit to avoid MissingGreenlet errors
        session.expire_on_commit = False

        # 1. Cümlelerin entities_org ve dominant_frame alanlarını doldur
        print("Cumlelerin (Sentence) eksik alanlari taraniyor...")
        stmt = select(Sentence.sent_id).where(
            (Sentence.entities_org.is_(None)) | (Sentence.dominant_frame.is_(None))
        )
        result = await session.execute(stmt)
        sent_ids = result.scalars().all()
        print(f"Guncellenecek {len(sent_ids)} adet cumle bulundu.")

        batch_size = 100
        for i in range(0, len(sent_ids), batch_size):
            chunk_ids = sent_ids[i : i + batch_size]
            stmt = select(Sentence).where(Sentence.sent_id.in_(chunk_ids))
            result = await session.execute(stmt)
            chunk = result.scalars().all()

            for s in chunk:
                # entities_org backfill
                if s.entities_org is None:
                    try:
                        ner_res = await ner_service.extract(s.text)
                        orgs = []
                        for ent in ner_res.get("entities", []):
                            label = ent.get("label", "").upper()
                            if label in ("ORG", "ORGANIZATION"):
                                orgs.append(ent.get("text"))
                        s.entities_org = orgs if orgs else None
                    except Exception as e:
                        print(f"Cumle {s.sent_id} icin NER hatasi: {e}")

                # dominant_frame backfill
                if s.dominant_frame is None:
                    try:
                        from bb_paxdata.domain.models.sentence import (
                            Sentence as SentenceDomainModel,
                        )

                        _framing_sentence = SentenceDomainModel(
                            id=s.sent_id, text=s.text
                        )
                        _frame_result = framing_service.detect_frame(_framing_sentence)
                        if _frame_result and _frame_result.frame_type:
                            s.dominant_frame = _frame_result.frame_type.value
                    except Exception as e:
                        print(f"Cumle {s.sent_id} icin Framing hatasi: {e}")

            await session.commit()
            print(f"Cumleler guncellendi: {i + len(chunk)}/{len(sent_ids)}")

        # 2. Segment alanlarını aggregate edip güncelle
        print("Segment (Segment) alanlari guncelleniyor...")
        stmt = select(Segment.seg_id)
        result = await session.execute(stmt)
        seg_ids = result.scalars().all()
        print(f"Toplam {len(seg_ids)} adet segment islenecek.")

        segment_batch_size = 100
        for i in range(0, len(seg_ids), segment_batch_size):
            chunk_ids = seg_ids[i : i + segment_batch_size]
            stmt = (
                select(Segment)
                .where(Segment.seg_id.in_(chunk_ids))
                .options(joinedload(Segment.speaker), joinedload(Segment.sentences))
            )
            res = await session.execute(stmt)
            segments = res.scalars().unique().all()

            for segment in segments:
                enriched = gateway.enrich(
                    db_segment=segment,
                    db_sentences=segment.sentences,
                    pipeline_res=None,
                    topic_result=None,
                )

                segment.bloc = enriched.bloc
                segment.role = enriched.role
                segment.key_phrases = enriched.key_phrases
                segment.tfidf_keywords = enriched.tfidf_keywords
                segment.entities_gpe = enriched.entities_gpe
                segment.entities_org = enriched.entities_org
                segment.entities_person = enriched.entities_person
                segment.risk_signals = enriched.risk_signals
                segment.demand_concentration = enriched.demand_concentration
                segment.inconsistency_score = enriched.inconsistency_score
                segment.dominant_frame = enriched.dominant_frame

            await session.commit()
            print(f"Segmentler guncellendi: {i + len(segments)}/{len(seg_ids)}")

    print("Backfill islemi basariyla tamamlandi!")


if __name__ == "__main__":
    asyncio.run(backfill())
