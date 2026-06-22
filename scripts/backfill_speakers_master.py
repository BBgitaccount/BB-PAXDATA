# scripts/backfill_speakers_master.py
import asyncio
import sys
from pathlib import Path

# Add root folder to python path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select

from bb_paxdata.application.use_cases.speaker_registry_use_case import (
    normalize_speaker_name,
)
from bb_paxdata.infrastructure.db.models import Speaker, SpeakerProfile
from bb_paxdata.infrastructure.db.session import SessionLocal


async def backfill():
    print("Starting speakers master table backfill...")
    async with SessionLocal() as db:
        # Get all speaker profiles
        stmt = select(SpeakerProfile)
        result = await db.execute(stmt)
        profiles = result.scalars().all()
        print(f"Found {len(profiles)} speaker profiles in 'speaker_profiles' table.")

        # Simple country mapping dictionary
        country_map = {
            "turkey": "TUR",
            "syria": "SYR",
            "serbia": "SRB",
            "switzerland": "CHE",
            "azerbaijan": "AZE",
            "democratic republic of the congo": "COD",
            "el salvador": "SLV",
            "russia": "RUS",
            "united states": "USA",
            "china": "CHN",
            "france": "FRA",
            "germany": "DEU",
            "united kingdom": "GBR",
            "iran": "IRN",
            "iraq": "IRQ",
            "ukraine": "UKR",
            "greece": "GRC",
        }

        created_count = 0
        updated_count = 0

        for profile in profiles:
            # Check if speaker already exists
            stmt_spk = select(Speaker).where(Speaker.speaker_id == profile.speaker_id)
            res_spk = await db.execute(stmt_spk)
            spk = res_spk.scalar_one_or_none()

            canonical_name, display_name = normalize_speaker_name(profile.full_name)

            # Map power level: profile.power_level is usually 0 to 10 (int).
            # Constraint requires Float between 0.0 and 1.0.
            raw_pl = profile.power_level if profile.power_level is not None else 5
            power_level = max(0.0, min(1.0, float(raw_pl) / 10.0))

            # Map country name to 3-letter code
            country_name = profile.country.strip() if profile.country else "Unknown"
            country_code = country_map.get(country_name.lower())
            if not country_code and country_name and country_name.lower() != "unknown":
                # Use first 3 letters as fallback country code
                country_code = country_name[:3].upper()
            elif country_name.lower() == "unknown":
                country_code = None

            role = profile.role.upper() if profile.role else "SPEAKER"

            # Ensure unique canonical_name
            # If canonical_name is already in use by another speaker_id, modify it to keep constraint happy
            stmt_canon = select(Speaker).where(
                (Speaker.canonical_name == canonical_name)
                & (Speaker.speaker_id != profile.speaker_id)
            )
            res_canon = await db.execute(stmt_canon)
            canon_spk = res_canon.scalar_one_or_none()
            if canon_spk:
                print(
                    f"Warning: canonical name '{canonical_name}' already exists for speaker_id '{canon_spk.speaker_id}'. Appending speaker_id to unique name."
                )
                canonical_name = f"{canonical_name} ({profile.speaker_id})"

            if not spk:
                spk = Speaker(
                    speaker_id=profile.speaker_id,
                    canonical_name=canonical_name,
                    display_name=profile.full_name or display_name,
                    country_code=country_code,
                    country_name=country_name,
                    bloc=profile.bloc,
                    power_level=power_level,
                    role=role,
                    title=profile.title,
                    is_active=True,
                    appearance_count=profile.n_panels,
                    data_source="backfill_profiles",
                    aliases=list(
                        set([profile.full_name, canonical_name, display_name])
                    ),
                    additional_metadata={
                        "influence_tier": profile.influence_tier,
                        "first_seen_panel": profile.first_seen_panel,
                    },
                )
                db.add(spk)
                created_count += 1
            else:
                spk.canonical_name = canonical_name
                spk.display_name = profile.full_name or display_name
                spk.country_name = country_name
                spk.country_code = country_code
                spk.bloc = profile.bloc
                spk.power_level = power_level
                spk.role = role
                spk.title = profile.title
                spk.appearance_count = profile.n_panels
                updated_count += 1

        await db.commit()
        print(
            f"Successfully committed backfill: {created_count} created, {updated_count} updated."
        )


if __name__ == "__main__":
    asyncio.run(backfill())
