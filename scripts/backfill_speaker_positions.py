"""Backfill speaker_positions table with sample SBI data."""

import random
import sys
import uuid
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.models import File, Speaker
from bb_paxdata.infrastructure.db.sbi_table import SpeakerPositionTable
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create speaker position entries for existing speakers."""
    print("Backfilling speaker_positions table...")

    with get_db_session() as session:
        # Get files and speakers
        files = session.query(File).all()
        speakers = session.query(Speaker).all()

        if not files:
            print("No files found. Cannot create speaker positions.")
            return

        if not speakers:
            print("No speakers found. Cannot create speaker positions.")
            return

        # Check if positions exist
        existing_count = session.query(SpeakerPositionTable).count()
        if existing_count > 0:
            print(f"Found {existing_count} existing positions. Skipping.")
            return

        # Create sample speaker positions for each speaker in each file
        positions_created = 0
        for file in files:
            for speaker in speakers:
                # Generate realistic SBI values
                wordfish_theta = random.uniform(-1.0, 1.0)
                wordscores_t = random.uniform(-1.0, 1.0)
                stance_density = random.uniform(0.0, 1.0)
                engagement_score = random.uniform(0.0, 1.0)

                # Composite SBI calculation (weighted sum)
                sbi = (
                    0.6 * wordfish_theta
                    + 0.25 * wordscores_t
                    + 0.15 * stance_density
                    + 0.05 * engagement_score
                )

                session_deviation = random.uniform(-0.5, 0.5)

                position = SpeakerPositionTable(
                    speaker_id=speaker.speaker_id,
                    session_id=file.file_id,
                    analysis_id=f"analysis_{uuid.uuid4().hex[:8]}",
                    wordfish_theta=wordfish_theta,
                    wordscores_t=wordscores_t,
                    stance_density=stance_density,
                    engagement_score=engagement_score,
                    sbi=sbi,
                    session_deviation=session_deviation,
                    alpha=0.6,
                    beta=0.25,
                    gamma=0.15,
                    delta=0.05,
                    gat_anomaly_score=(
                        random.uniform(0.0, 1.0) if random.random() > 0.8 else None
                    ),
                )
                session.add(position)
                positions_created += 1

        session.commit()
        print(f"Created {positions_created} speaker positions")

        # Verify
        total = session.query(SpeakerPositionTable).count()
        print(f"\nTotal speaker_positions: {total}")


if __name__ == "__main__":
    main()
