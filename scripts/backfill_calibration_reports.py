"""Backfill calibration_reports table with sample calibration data."""

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.infrastructure.db.human_review_table import CalibrationReportORM
from bb_paxdata.infrastructure.db.session import get_db_session


def main():
    """Create calibration report entries."""
    print("Backfilling calibration_reports table...")

    with get_db_session() as session:
        # Check if calibration reports exist
        existing_count = session.query(CalibrationReportORM).count()
        if existing_count > 0:
            print(f"Found {existing_count} existing calibration reports. Skipping.")
            return

        # Create sample calibration reports for different prompt versions
        prompt_versions = [
            "dki_judge_v2.1",
            "risk_analyzer_v1.5",
            "frame_detector_v1.0",
        ]

        reports_created = 0
        for prompt_version in prompt_versions:
            # Generate realistic calibration metrics
            cohens_kappa_frame = random.uniform(0.6, 0.9)
            cohens_kappa_risk = random.uniform(0.5, 0.85)
            ai_human_f1_frame = random.uniform(0.7, 0.95)
            ai_human_f1_risk = random.uniform(0.65, 0.9)
            sbi_mae = random.uniform(0.1, 0.3)

            total_reviews = random.randint(50, 200)
            total_disagreements = int(total_reviews * random.uniform(0.1, 0.3))

            # Determine if updates are needed
            requires_prompt_update = cohens_kappa_frame < 0.7 or cohens_kappa_risk < 0.7
            requires_weight_update = sbi_mae > 0.25

            alert_message = None
            if requires_prompt_update:
                alert_message = (
                    f"Low agreement for {prompt_version}. Consider prompt refinement."
                )
            elif requires_weight_update:
                alert_message = (
                    f"High SBI MAE for {prompt_version}. Consider weight adjustment."
                )

            # Evaluation period (last 30 days)
            end_date = datetime.now(timezone.utc).replace(tzinfo=None)
            start_date = end_date - timedelta(days=30)

            report = CalibrationReportORM(
                id=str(uuid.uuid4()),
                prompt_version=prompt_version,
                evaluation_period_start=start_date,
                evaluation_period_end=end_date,
                cohens_kappa_frame=cohens_kappa_frame,
                cohens_kappa_risk=cohens_kappa_risk,
                ai_human_f1_frame=ai_human_f1_frame,
                ai_human_f1_risk=ai_human_f1_risk,
                sbi_mae=sbi_mae,
                total_reviews=total_reviews,
                total_disagreements=total_disagreements,
                top_disagreement_patterns=[
                    "frame_misclassification",
                    "risk_threshold",
                    "sentiment_polarity",
                ],
                requires_prompt_update=requires_prompt_update,
                requires_weight_update=requires_weight_update,
                alert_message=alert_message,
            )
            session.add(report)
            reports_created += 1

        session.commit()
        print(f"Created {reports_created} calibration reports")

        # Verify
        total = session.query(CalibrationReportORM).count()
        print(f"\nTotal calibration_reports: {total}")


if __name__ == "__main__":
    main()
