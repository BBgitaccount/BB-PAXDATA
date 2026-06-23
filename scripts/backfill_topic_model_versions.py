"""Backfill topic_model_versions table with current BERTopic model info."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.models import TopicModelVersion
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create a topic model version entry for the current model."""
    print("Backfilling topic_model_versions table...")

    with get_db_session() as session:
        # Check if any versions exist
        existing_count = session.query(TopicModelVersion).count()
        if existing_count > 0:
            print(f"Found {existing_count} existing versions. Skipping.")
            return

        # Create a default version entry for the current model
        # This would normally come from the actual BERTopic model metadata
        version_id = f"bertopic_v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Default hyperparameters (these should match your actual BERTopic config)
        hyperparameters = {
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "nr_topics": 15,
            "min_topic_size": 10,
            "verbose": True,
            "calculate_probabilities": False,
        }

        # Corpus checksum (placeholder - should be hash of training corpus)
        corpus_checksum = "placeholder_checksum_" + version_id

        topic_version = TopicModelVersion(
            version_id=version_id,
            trained_at=datetime.now(timezone.utc).replace(tzinfo=None),
            hyperparameters=hyperparameters,
            corpus_checksum=corpus_checksum,
        )

        session.add(topic_version)
        session.commit()

        print(f"Created topic model version: {version_id}")
        print(f"Hyperparameters: {json.dumps(hyperparameters, indent=2)}")

        # Verify
        total = session.query(TopicModelVersion).count()
        print(f"\nTotal topic_model_versions: {total}")


if __name__ == "__main__":
    main()
