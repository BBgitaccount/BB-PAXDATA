"""Backfill script to detect and populate demand_records from sentences."""

import json
import sys
from pathlib import Path

from tqdm import tqdm

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.application.domain.services.demand_detector import DemandDetector
from bb_paxdata.infrastructure.db.models import DemandRecord, Sentence
from bb_paxdata.infrastructure.db.session import get_db_session


def extract_entities_from_sentence(sentence: Sentence) -> list[str]:
    """Extract named entities from sentence JSON fields."""
    entities = []

    # Extract from entities_gpe (geopolitical entities)
    if sentence.entities_gpe:
        if isinstance(sentence.entities_gpe, str):
            try:
                gpe_data = json.loads(sentence.entities_gpe)
            except json.JSONDecodeError:
                gpe_data = {}
        else:
            gpe_data = sentence.entities_gpe

        if isinstance(gpe_data, dict):
            entities.extend(gpe_data.keys())
        elif isinstance(gpe_data, list):
            entities.extend(gpe_data)

    # Extract from entities_org (organizations)
    if sentence.entities_org:
        if isinstance(sentence.entities_org, str):
            try:
                org_data = json.loads(sentence.entities_org)
            except json.JSONDecodeError:
                org_data = {}
        else:
            org_data = sentence.entities_org

        if isinstance(org_data, dict):
            entities.extend(org_data.keys())
        elif isinstance(org_data, list):
            entities.extend(org_data)

    # Extract from entities_person (people)
    if sentence.entities_person:
        if isinstance(sentence.entities_person, str):
            try:
                person_data = json.loads(sentence.entities_person)
            except json.JSONDecodeError:
                person_data = {}
        else:
            person_data = sentence.entities_person

        if isinstance(person_data, dict):
            entities.extend(person_data.keys())
        elif isinstance(person_data, list):
            entities.extend(person_data)

    return entities


def calculate_demand_weight(urgency_level: str, confidence: float) -> float:
    """Calculate demand weight based on urgency and confidence."""
    urgency_weights = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.3}
    base_weight = urgency_weights.get(urgency_level, 0.5)
    return base_weight * confidence


def main():
    """Main backfill function."""
    print("Starting demand detection backfill...")
    detector = DemandDetector()

    with get_db_session() as session:
        # Get total sentence count
        total_sentences = session.query(Sentence).count()
        print(f"Total sentences to process: {total_sentences}")

        if total_sentences == 0:
            print("No sentences found in database. Exiting.")
            return

        # Process sentences in batches
        batch_size = 100
        processed = 0
        demands_created = 0

        with tqdm(total=total_sentences, desc="Processing sentences") as pbar:
            for offset in range(0, total_sentences, batch_size):
                sentences = (
                    session.query(Sentence)
                    .order_by(Sentence.sent_id)
                    .offset(offset)
                    .limit(batch_size)
                    .all()
                )

                for sentence in sentences:
                    # Extract entities
                    entities = extract_entities_from_sentence(sentence)

                    # Detect demand
                    demand_info = detector.detect_demand(
                        text=sentence.text,
                        speaker_name=sentence.speaker_name,
                        country=sentence.country,
                        entities=entities,
                    )

                    if demand_info:
                        # Calculate demand weight
                        demand_weight = calculate_demand_weight(
                            demand_info["urgency_level"],
                            demand_info["confidence_score"],
                        )

                        # Create DemandRecord
                        demand_record = DemandRecord(
                            sent_id=sentence.sent_id,
                            seg_id=sentence.seg_id,
                            speaker_name=sentence.speaker_name,
                            country=sentence.country or "UNKNOWN",
                            power_level=sentence.power_level or 0,
                            demand_verb=demand_info["demand_verb"],
                            demand_type=demand_info["demand_type"],
                            demand_weight=demand_weight,
                            demand_category=demand_info["demand_category"],
                            target_entity=demand_info["target_entity"],
                            full_sentence=sentence.text,
                            diplo_compound=sentence.diplo_compound or 0,
                            # Set default compliance status to UNKNOWN
                            compliance_status="UNKNOWN",
                            # Set default values for new fields
                            timestamp=sentence.start_time,
                            compliance_likelihood=None,
                            assertiveness_score=None,
                            politeness_score=None,
                            response_text=None,
                            response_timestamp=None,
                            related_demand_ids=None,
                            is_conditional=False,
                            conditions=None,
                            impact_score=None,
                            risk_implication=None,
                            is_active=True,
                            is_fulfilled=False,
                            fulfillment_timestamp=None,
                            notes=None,
                            tags=None,
                            extra_metadata={
                                "urgency_level": demand_info["urgency_level"],
                                "confidence_score": demand_info["confidence_score"],
                                "demand_type_enum": demand_info["demand_type_enum"],
                            },
                        )

                        session.add(demand_record)
                        demands_created += 1

                    processed += 1
                    pbar.update(1)

                # Commit batch
                session.commit()
                pbar.set_postfix({"demands": demands_created})

        print("\nBackfill complete!")
        print(f"  Processed: {processed} sentences")
        print(f"  Demands created: {demands_created}")
        print(f"  Detection rate: {demands_created / processed * 100:.2f}%")

        # Verify results
        print("\nVerifying results...")
        total_demands = session.query(DemandRecord).count()
        print(f"Total demand_records: {total_demands}")

        # Group by demand type
        from sqlalchemy import func

        type_counts = (
            session.query(DemandRecord.demand_type, func.count(DemandRecord.demand_id))
            .group_by(DemandRecord.demand_type)
            .all()
        )
        print("\nDemand type distribution:")
        for demand_type, count in type_counts:
            print(f"  {demand_type}: {count}")

        # Group by urgency (PostgreSQL compatible - iterate manually)
        urgency_counts = {}
        confidence_scores = []
        for demand in session.query(DemandRecord).all():
            if demand.extra_metadata:
                urgency = demand.extra_metadata.get("urgency_level")
                confidence = demand.extra_metadata.get("confidence_score")
                if urgency:
                    urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
                if confidence:
                    confidence_scores.append(confidence)

        print("\nUrgency level distribution:")
        for urgency, count in sorted(urgency_counts.items()):
            print(f"  {urgency}: {count}")

        # Average confidence
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        )
        print(f"\nAverage confidence score: {avg_confidence:.3f}")

        # Count null target entities
        null_targets = (
            session.query(DemandRecord)
            .filter(DemandRecord.target_entity.is_(None))
            .count()
        )
        print(f"Demands without target entity: {null_targets}")


if __name__ == "__main__":
    main()
