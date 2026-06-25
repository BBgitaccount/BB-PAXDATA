"""Backfill audit_entries table with sample audit data."""

import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.model_evaluation import AuditEntry
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create audit entry records for recent operations."""
    print("Backfilling audit_entries table...")

    with get_db_session() as session:
        # Check if audit entries exist
        existing_count = session.query(AuditEntry).count()
        if existing_count > 0:
            print(f"Found {existing_count} existing audit entries. Skipping.")
            return

        # Create sample audit entries for various operations
        action_types = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "BULK_IMPORT",
            "CALIBRATION_RUN",
            "MODEL_TRAIN",
        ]

        entity_types = [
            "File",
            "Segment",
            "Sentence",
            "Speaker",
            "DemandRecord",
            "SpeakerPosition",
            "DKIResult",
            "CalibrationReport",
        ]

        entries_created = 0
        # Create 50 sample audit entries
        for _ in range(50):
            action_type = random.choice(action_types)
            entity_type = random.choice(entity_types)

            # Generate random timestamp within last 7 days
            timestamp = datetime.now(UTC).replace(tzinfo=None) - timedelta(
                days=random.randint(0, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            # Create details based on action type
            if action_type == "INSERT":
                details = {
                    "record_id": str(uuid.uuid4()),
                    "fields_affected": ["id", "created_at", "data"],
                    "source": "pipeline",
                }
            elif action_type == "UPDATE":
                details = {
                    "record_id": str(uuid.uuid4()),
                    "fields_changed": ["updated_at", "status"],
                    "old_values": {"status": "pending"},
                    "new_values": {"status": "completed"},
                }
            elif action_type == "DELETE":
                details = {
                    "record_id": str(uuid.uuid4()),
                    "reason": "duplicate",
                    "deleted_at": timestamp.isoformat(),
                }
            elif action_type == "BULK_IMPORT":
                details = {
                    "batch_id": str(uuid.uuid4()),
                    "records_processed": random.randint(10, 1000),
                    "source_file": f"import_{random.randint(1000, 9999)}.json",
                }
            elif action_type == "CALIBRATION_RUN":
                details = {
                    "prompt_version": f"v{random.randint(1, 3)}.{random.randint(0, 9)}",
                    "total_reviews": random.randint(50, 200),
                    "accuracy": round(random.uniform(0.7, 0.95), 3),
                }
            else:  # MODEL_TRAIN
                details = {
                    "model_type": "BERTopic",
                    "training_docs": random.randint(1000, 10000),
                    "n_topics": random.randint(10, 20),
                    "coherence_score": round(random.uniform(0.3, 0.7), 3),
                }

            # Manually set the performed_at timestamp
            audit_entry = AuditEntry(
                action_type=action_type,
                entity_type=entity_type,
                details=details,
            )
            # Set timestamp manually (bypassing server_default)
            session.add(audit_entry)
            # Flush to get the ID, then update timestamp
            session.flush()
            audit_entry.performed_at = timestamp
            entries_created += 1

        session.commit()
        print(f"Created {entries_created} audit entries")

        # Verify
        total = session.query(AuditEntry).count()
        print(f"\nTotal audit_entries: {total}")


if __name__ == "__main__":
    main()
