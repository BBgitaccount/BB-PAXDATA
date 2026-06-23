"""Backfill dki_results table with sample DKI data."""

import random
import sys
import uuid
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.dki_table import DKIResultModel
from bb_paxdata.infrastructure.db.models import File, Speaker
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create DKI result entries for existing speakers."""
    print("Backfilling dki_results table...")

    with get_db_session() as session:
        # Get files and speakers
        files = session.query(File).all()
        speakers = session.query(Speaker).all()

        if not files:
            print("No files found. Cannot create DKI results.")
            return

        if not speakers:
            print("No speakers found. Cannot create DKI results.")
            return

        # Check if DKI results exist
        existing_count = session.query(DKIResultModel).count()
        if existing_count > 0:
            print(f"Found {existing_count} existing DKI results. Skipping.")
            return

        # Create sample DKI results for each speaker in each file
        dki_created = 0
        for file in files:
            for speaker in speakers:
                # Generate realistic DKI component scores
                velocity = random.uniform(0.0, 1.0)
                semantic_shift = random.uniform(0.0, 1.0)
                debate_loading = random.uniform(0.0, 1.0)

                # Composite DKI score
                dki_score = (velocity + semantic_shift + debate_loading) / 3.0

                # Anomaly flag (10% chance of being anomalous)
                anomaly_flag = random.random() < 0.1

                dki_result = DKIResultModel(
                    analysis_id=f"analysis_{uuid.uuid4().hex[:8]}",
                    speaker_id=speaker.speaker_id,
                    session_id=file.file_id,
                    dki_score=dki_score,
                    velocity=velocity,
                    semantic_shift=semantic_shift,
                    debate_loading=debate_loading,
                    anomaly_flag=anomaly_flag,
                    calculation_method="dki_v1.0",
                )
                session.add(dki_result)
                dki_created += 1

        session.commit()
        print(f"Created {dki_created} DKI results")

        # Verify
        total = session.query(DKIResultModel).count()
        print(f"\nTotal dki_results: {total}")


if __name__ == "__main__":
    main()
