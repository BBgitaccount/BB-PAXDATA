"""Backfill aggregation_lineage table with sample lineage data."""

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.models import AggregationLineage, File
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create aggregation lineage entries for speaker profiles."""
    print("Backfilling aggregation_lineage table...")

    with get_db_session() as session:
        # Get files
        files = session.query(File).all()

        if not files:
            print("No files found. Cannot create aggregation lineage.")
            return

        # Check if aggregation lineage exists
        existing_count = session.query(AggregationLineage).count()
        if existing_count > 0:
            print(
                f"Found {existing_count} existing aggregation lineage entries. Skipping."
            )
            return

        # Create sample aggregation lineage for speaker profile aggregations
        # Each file's speaker profile aggregation would have lineage from its segments
        lineage_created = 0
        for file in files:
            # Create a few lineage entries per file
            for _ in range(random.randint(3, 10)):
                projection_id = str(uuid.uuid4())
                event_id = str(uuid.uuid4())

                # Random weight contribution (0.0 to 1.0)
                weight_contribution = random.uniform(0.01, 0.3)

                # Random timestamp within last 30 days
                contribution_timestamp = datetime.now(timezone.utc).replace(
                    tzinfo=None
                ) - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )

                lineage = AggregationLineage(
                    id=str(uuid.uuid4()),
                    projection_id=projection_id,
                    event_id=event_id,
                    weight_contribution=weight_contribution,
                    contribution_timestamp=contribution_timestamp,
                )
                session.add(lineage)
                lineage_created += 1

        session.commit()
        print(f"Created {lineage_created} aggregation lineage entries")

        # Verify
        total = session.query(AggregationLineage).count()
        print(f"\nTotal aggregation_lineage: {total}")


if __name__ == "__main__":
    main()
