"""Backfill topic_mappings table with topic information."""

import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.models import TopicMapping, TopicModelVersion
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create topic mapping entries for current topics."""
    print("Backfilling topic_mappings table...")

    with get_db_session() as session:
        # Get the topic model version
        version = session.query(TopicModelVersion).first()
        if not version:
            print(
                "No topic model version found. Run backfill_topic_model_versions.py first."
            )
            return

        # Check if mappings exist
        existing_count = session.query(TopicMapping).count()
        if existing_count > 0:
            print(f"Found {existing_count} existing mappings. Skipping.")
            return

        # Create sample topic mappings
        # In a real implementation, this would come from BERTopic topic info
        sample_topics = [
            {
                "topic_from": "topic_0",
                "top_words": ["war", "conflict", "military", "troops", "attack"],
                "human_label": "Military Conflict",
            },
            {
                "topic_from": "topic_1",
                "top_words": ["diplomacy", "negotiation", "peace", "talk", "agreement"],
                "human_label": "Diplomatic Negotiation",
            },
            {
                "topic_from": "topic_2",
                "top_words": ["sanction", "economic", "trade", "penalty", "embargo"],
                "human_label": "Economic Sanctions",
            },
            {
                "topic_from": "topic_3",
                "top_words": ["humanitarian", "aid", "refugee", "relief", "crisis"],
                "human_label": "Humanitarian Issues",
            },
            {
                "topic_from": "topic_4",
                "top_words": ["security", "council", "resolution", "un", "vote"],
                "human_label": "UN Security Council",
            },
        ]

        for topic in sample_topics:
            mapping = TopicMapping(
                version_from=version.version_id,
                topic_from=topic["topic_from"],
                version_to=version.version_id,
                topic_to=topic["topic_from"],
                wasserstein_distance=0.0,  # Same version, no distance
                mapping_confidence=1.0,  # Perfect confidence for same version
            )
            session.add(mapping)

        session.commit()
        print(f"Created {len(sample_topics)} topic mappings")

        # Verify
        total = session.query(TopicMapping).count()
        print(f"\nTotal topic_mappings: {total}")


if __name__ == "__main__":
    main()
