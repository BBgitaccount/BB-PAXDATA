import asyncio
import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select, text

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.db.models import (
    Segment,
    Sentence,
    Speaker,
    SpeakerProfile,
    Word,
)
from bb_paxdata.infrastructure.db.session import SessionLocal
from bb_paxdata.infrastructure.text.normalizer import normalize_person_name


async def main():
    print("Starting TASK-DB-007 backfill script for entries and speaker names...")

    settings = get_settings()
    print(f"Database URL: {settings.database_url}")

    async with SessionLocal() as session:
        # 1. Create entries table physically in PostgreSQL if not exists
        print("Ensuring 'entries' table exists in database...")
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS entries (
                person VARCHAR(255) PRIMARY KEY
            );
        """))
        await session.commit()

        # 2. Fetch all speakers and speaker profiles
        print("Fetching speakers and profiles from database...")
        speakers_res = await session.execute(select(Speaker))
        speakers = speakers_res.scalars().all()

        profiles_res = await session.execute(select(SpeakerProfile))
        profiles = profiles_res.scalars().all()

        print(f"Found {len(speakers)} speakers and {len(profiles)} profiles.")

        # Track all unique clean names to populate entries table
        clean_people_names = set()

        # 3. Clean and update speakers
        print("Cleaning 'speakers' table...")
        seen_canon = set()
        for spk in speakers:
            old_canon = spk.canonical_name
            old_display = spk.display_name

            clean_canon = normalize_person_name(old_canon) if old_canon else ""
            # If canonical name had commas (e.g. LIZZY, Porter), keep the structure but clean names
            if old_canon and "," in old_canon:
                parts = old_canon.split(",", 1)
                last_clean = normalize_person_name(parts[0]).upper()
                first_clean = normalize_person_name(parts[1])
                clean_canon = f"{last_clean}, {first_clean}"
            elif old_canon:
                clean_canon = clean_canon.upper()

            clean_display = normalize_person_name(old_display) if old_display else ""

            # Ensure unique canonical name to satisfy unique constraint
            if clean_canon:
                base_canon = clean_canon
                while clean_canon in seen_canon or any(
                    s.canonical_name == clean_canon and s.speaker_id != spk.speaker_id
                    for s in speakers
                ):
                    clean_canon = f"{base_canon} ({spk.speaker_id})"
                seen_canon.add(clean_canon)

            if clean_canon != old_canon or clean_display != old_display:
                print(f"  Updating Speaker ID: {spk.speaker_id}")
                print(
                    f"    Canonical: {old_canon!r} -> {clean_canon!r}".encode(
                        "ascii", errors="replace"
                    ).decode("ascii")
                )
                print(
                    f"    Display:   {old_display!r} -> {clean_display!r}".encode(
                        "ascii", errors="replace"
                    ).decode("ascii")
                )
                spk.canonical_name = clean_canon
                spk.display_name = clean_display

            if clean_canon:
                clean_people_names.add(clean_canon)
            if clean_display:
                clean_people_names.add(clean_display)

            # Also clean aliases list if present
            if spk.aliases:
                clean_aliases = []
                for alias in spk.aliases:
                    clean_a = normalize_person_name(alias)
                    if clean_a:
                        clean_aliases.append(clean_a)
                        clean_people_names.add(clean_a)
                spk.aliases = list(set(clean_aliases))

        # 4. Clean and update speaker profiles
        print("Cleaning 'speaker_profiles' table...")
        for prof in profiles:
            old_full = prof.full_name
            clean_full = normalize_person_name(old_full) if old_full else ""

            if clean_full != old_full:
                print(f"  Updating SpeakerProfile ID: {prof.speaker_id}")
                print(
                    f"    Full Name: {old_full!r} -> {clean_full!r}".encode(
                        "ascii", errors="replace"
                    ).decode("ascii")
                )
                prof.full_name = clean_full

            if clean_full:
                clean_people_names.add(clean_full)

        # 5. Clean references in segment, sentence, and word tables to keep DB consistent
        print("Cleaning speaker name references in other tables...")

        # Gather all mappings of speaker_id to display_name/full_name
        speaker_name_map = {}
        for spk in speakers:
            if spk.display_name:
                speaker_name_map[spk.speaker_id] = spk.display_name
        for prof in profiles:
            if prof.full_name:
                speaker_name_map[prof.speaker_id] = prof.full_name

        # Clean segment speaker_name
        segments_res = await session.execute(select(Segment))
        segments = segments_res.scalars().all()
        for seg in segments:
            old_name = seg.speaker_name
            # Fallback to map if needed or just clean directly
            clean_name = normalize_person_name(old_name)
            if not clean_name and seg.speaker_id in speaker_name_map:
                clean_name = speaker_name_map[seg.speaker_id]

            if clean_name != old_name:
                seg.speaker_name = clean_name

        # Clean sentence speaker_name
        sentences_res = await session.execute(select(Sentence))
        sentences = sentences_res.scalars().all()
        for sent in sentences:
            old_name = sent.speaker_name
            clean_name = normalize_person_name(old_name)
            if not clean_name and sent.speaker_id in speaker_name_map:
                clean_name = speaker_name_map[sent.speaker_id]

            if clean_name != old_name:
                sent.speaker_name = clean_name

        # Clean word speaker_name
        words_res = await session.execute(
            select(Word).limit(10000)
        )  # Clean up to 10000 sample words if any
        words = words_res.scalars().all()
        for word in words:
            old_name = word.speaker_name
            clean_name = normalize_person_name(old_name)
            if not clean_name and word.speaker_id in speaker_name_map:
                clean_name = speaker_name_map[word.speaker_id]

            if clean_name != old_name:
                word.speaker_name = clean_name

        # 6. Populate physical entries table
        print(
            f"Populating 'entries' table with {len(clean_people_names)} unique names..."
        )
        for name in sorted(list(clean_people_names)):
            if not name or name.upper() in ("UNKNOWN",):
                continue
            await session.execute(
                text(
                    "INSERT INTO entries (person) VALUES (:person) ON CONFLICT (person) DO NOTHING;"
                ),
                {"person": name},
            )
        await session.commit()

        # Verification check
        verify_res = await session.execute(
            text("SELECT COUNT(*), COUNT(person) FROM entries;")
        )
        count_info = verify_res.fetchone()
        print(
            f"Verification: 'entries' table has {count_info[0]} rows (non-null: {count_info[1]})."
        )

        corrupt_res = await session.execute(
            text(
                "SELECT COUNT(*) FROM entries WHERE person LIKE '%?%' OR person LIKE '%â%';"
            )
        )
        corrupt_count = corrupt_res.scalar()
        print(
            f"Verification: found {corrupt_count} entries with corrupt characters (?, â)."
        )

    print("Backfill for entries and speaker names completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
