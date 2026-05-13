#!/usr/bin/env python3
"""
Manual annotation tool for golden dataset labeling.

This CLI tool allows users to annotate golden dataset candidates
with ground truth values for quality evaluation.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from bb_paxdata.tests.fixtures.golden_dataset import GoldenDataset  # type: ignore

logger = structlog.get_logger(__name__)


class GoldenAnnotator:
    """Interactive annotation tool for golden dataset."""

    def __init__(self, candidates_path: str, dataset: GoldenDataset | None = None):
        self.candidates_path = Path(candidates_path)
        self.dataset = dataset or GoldenDataset()
        self.logger = structlog.get_logger(__name__)
        self.candidates: list[dict[str, Any]] = []
        self.current_index = 0

    def load_candidates(self) -> None:
        """Load candidates from CSV file."""
        try:
            with open(self.candidates_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.candidates = list(reader)
            self.logger.info(
                f"Loaded {len(self.candidates)} candidates from {self.candidates_path}"
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Candidates file not found: {self.candidates_path}"
            ) from None
        except Exception as e:
            raise ValueError(f"Error loading candidates: {e}") from e

    def get_next_fixture_id(self) -> str:
        """Get next available fixture ID."""
        dataset = self.dataset.load_dataset()
        existing_ids = {f["fixture_id"] for f in dataset.get("fixtures", [])}

        # Find next available ID
        i = 1
        while f"gd_{i:03d}" in existing_ids:
            i += 1
        return f"gd_{i:03d}"

    def display_candidate(self, candidate: dict[str, Any]) -> None:
        """Display candidate information."""
        print("\n" + "=" * 80)
        print(f"CANDIDATE #{self.current_index + 1}/{len(self.candidates)}")
        print("=" * 80)
        print(f"Sentence ID: {candidate.get('sent_id', 'N/A')}")
        print(
            f"Speaker: {candidate.get('speaker_name', 'N/A')} "
            f"({candidate.get('country', 'N/A')})"
        )
        print(f"Panel: {candidate.get('panel_id', 'N/A')}")
        print(f"\nTEXT:\n{candidate.get('text', 'N/A')}")
        print("\n" + "-" * 40)
        print("CURRENT AI ANALYSIS (for reference):")
        print(f"Sentiment Score: {candidate.get('AI_Duyju_Skoru', 'N/A')}")
        print(f"Risk Score: {candidate.get('AI_Risk_Skoru', 'N/A')}")
        print(f"Potential Risk: {candidate.get('AI_Potansiyel_Risk', 'N/A')}")
        print(f"Diplomatic Tone: {candidate.get('AI_Diplomatik_Ton', 'N/A')}")
        print(f"Demand Present: {candidate.get('AI_Talep_Var', 'N/A')}")
        print(f"Primary Topic: {candidate.get('AI_Birincil_Konu', 'N/A')}")
        print(f"Framing: {candidate.get('AI_Cerceveleme', 'N/A')}")
        print("-" * 40)

    def get_user_input(
        self, prompt: str, options: list[str] | None = None, required: bool = True
    ) -> str:
        """Get user input with optional options."""
        while True:
            if options:
                print(f"\n{prompt}")
                for i, option in enumerate(options, 1):
                    print(f"  {i}. {option}")
                choice = input("Enter choice number (or skip with 's'): ").strip()

                if choice.lower() == "s" and not required:
                    return ""

                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(options):
                        return options[choice_idx]
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
            else:
                value = input(f"{prompt}: ").strip()
                if value or not required:
                    return value
                print("This field is required. Please enter a value.")

    def get_numeric_input(
        self, prompt: str, min_val: float, max_val: float, required: bool = True
    ) -> float | None:
        """Get numeric input with validation."""
        while True:
            value = input(f"{prompt} ({min_val}-{max_val}): ").strip()

            if value.lower() == "s" and not required:
                return None

            try:
                num_val = float(value)
                if min_val <= num_val <= max_val:
                    return num_val
                else:
                    print(
                        f"Value must be between {min_val} and {max_val}. "
                        "Please try again."
                    )
            except ValueError:
                print("Please enter a valid number.")

    def annotate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        """Annotate a single candidate."""
        self.display_candidate(candidate)

        print("\n" + "=" * 40)
        print("GROUND TRUTH ANNOTATION")
        print("=" * 40)

        # Get annotation inputs
        ground_truth: dict[str, Any] = {}

        # Sentiment score (-1 to 1)
        sentiment_score = self.get_numeric_input("AI_Duygu_Skoru", -1.0, 1.0)
        if sentiment_score is not None:
            ground_truth["AI_Duygu_Skoru"] = sentiment_score

        # Sentiment category
        sentiment_options = [
            "positive",
            "negative",
            "neutral",
            "concerned",
            "hopeful",
            "angry",
            "fearful",
        ]
        ground_truth["AI_Duyju_Kategorisi"] = self.get_user_input(
            "AI_Duygu_Kategorisi", sentiment_options
        )

        # Risk score (0-10)
        risk_score = self.get_numeric_input("AI_Risk_Skoru", 0, 10, required=False)
        if risk_score is not None:
            ground_truth["AI_Risk_Skoru"] = int(risk_score)

        # Potential risk level
        risk_options = ["none", "low", "medium", "high", "critical"]
        ground_truth["AI_Potansiyel_Risk"] = self.get_user_input(
            "AI_Potansiyel_Risk", risk_options
        )

        # Demand present
        demand_choice = self.get_user_input("AI_Talep_Var (0=no, 1=yes)", ["0", "1"])
        ground_truth["AI_Talep_Var"] = int(demand_choice)

        # Diplomatic tone
        tone_options = [
            "assertive",
            "conciliatory",
            "evasive",
            "confrontational",
            "neutral",
            "persuasive",
            "defensive",
        ]
        ground_truth["AI_Diplomatik_Ton"] = self.get_user_input(
            "AI_Diplomatik_Ton", tone_options
        )

        # Manipulation score (0-1)
        manip_score = self.get_numeric_input(
            "AI_Manipulasyon_Skoru", 0.0, 1.0, required=False
        )
        if manip_score is not None:
            ground_truth["AI_Manipulasyon_Skor"] = manip_score

        # Framing (optional)
        framing = self.get_user_input("AI_Cerceveleme", required=False)
        if framing:
            ground_truth["AI_Cerceveleme"] = framing

        # Primary topic (optional)
        topic = self.get_user_input("AI_Birincil_Konu", required=False)
        if topic:
            ground_truth["AI_Birincil_Konu"] = topic

        # Selection reason
        reason_options = [
            "negation_trap",
            "high_risk",
            "topic_shift",
            "sentiment_drift",
            "demand_sentence",
            "diplomatic_tone",
            "manipulation_suspect",
            "framing_interest",
            "representative_sample",
            "edge_case",
        ]
        why_selected = self.get_user_input(
            "Why was this sentence selected?", reason_options
        )

        # Create fixture
        fixture = {
            "fixture_id": self.get_next_fixture_id(),
            "sent_id": candidate.get("sent_id", ""),
            "source_text": candidate.get("text", ""),
            "ground_truth": ground_truth,
            "metadata": {
                "why_selected": why_selected,
                "annotator": input("Your name: ").strip() or "anonymous",
                "annotated_at": datetime.now().strftime("%Y-%m-%d"),
                "version": "1.0",
            },
        }

        return fixture

    def save_fixture(self, fixture: dict[str, Any]) -> None:
        """Save fixture to golden dataset."""
        try:
            self.dataset.add_fixture(fixture)
            print(f"\n✅ Successfully saved fixture {fixture['fixture_id']}")
        except Exception as e:
            print(f"\n❌ Error saving fixture: {e}")

    def run_interactive(self) -> None:
        """Run interactive annotation session."""
        self.load_candidates()

        if not self.candidates:
            print("No candidates found to annotate.")
            return

        print("\n🏗️  Golden Dataset Annotation Tool")
        print(f"📊 {len(self.candidates)} candidates loaded")
        print(
            f"📝 Current dataset has "
            f"{len(self.dataset.load_dataset().get('fixtures', []))} fixtures"
        )

        while self.current_index < len(self.candidates):
            candidate = self.candidates[self.current_index]

            try:
                fixture = self.annotate_candidate(candidate)
                if fixture:
                    # Confirm before saving
                    confirm = (
                        input(f"\nSave fixture {fixture['fixture_id']}? (y/n/skip): ")
                        .strip()
                        .lower()
                    )
                    if confirm == "y":
                        self.save_fixture(fixture)
                    elif confirm == "skip":
                        print("⏭️  Skipped this candidate")
                    else:
                        print("❌ Not saved")

                # Move to next
                self.current_index += 1

                if self.current_index < len(self.candidates):
                    continue_choice = (
                        input("\nContinue to next candidate? (y/n): ").strip().lower()
                    )
                    if continue_choice != "y":
                        break

            except KeyboardInterrupt:
                print("\n\n⏹️  Annotation session interrupted")
                break
            except Exception as e:
                self.logger.error(f"Error annotating candidate: {e}")
                print(f"\n❌ Error: {e}")
                continue_choice = (
                    input("Continue to next candidate? (y/n): ").strip().lower()
                )
                if continue_choice != "y":
                    break
                self.current_index += 1

        print("\n📊 Session completed!")
        print(
            f"📝 Dataset now has "
            f"{len(self.dataset.load_dataset().get('fixtures', []))} fixtures"
        )

    def run_batch(self, output_file: str) -> None:
        """Run batch annotation (export candidates for external annotation)."""
        self.load_candidates()

        batch_data = []
        for candidate in self.candidates:
            batch_data.append(
                {
                    "sent_id": candidate.get("sent_id", ""),
                    "text": candidate.get("text", ""),
                    "speaker_name": candidate.get("speaker_name", ""),
                    "panel_id": candidate.get("panel_id", ""),
                    "current_ai_analysis": {
                        "AI_Duyju_Skoru": candidate.get("AI_Duyju_Skoru", ""),
                        "AI_Risk_Skoru": candidate.get("AI_Risk_Skoru", ""),
                        "AI_Potansiyel_Risk": candidate.get("AI_Potansiyel_Risk", ""),
                        "AI_Diplomatik_Ton": candidate.get("AI_Diplomatik_Ton", ""),
                        "AI_Talep_Var": candidate.get("AI_Talep_Var", ""),
                        "AI_Birincil_Konu": candidate.get("AI_Birincil_Konu", ""),
                        "AI_Cerceveleme": candidate.get("AI_Cerceveleme", ""),
                    },
                    "ground_truth": {
                        "AI_Duyju_Skoru": None,
                        "AI_Duyju_Kategorisi": None,
                        "AI_Risk_Skoru": None,
                        "AI_Potansiyel_Risk": None,
                        "AI_Talep_Var": None,
                        "AI_Diplomatik_Ton": None,
                        "AI_Manipulasyon_Skor": None,
                        "AI_Cerceveleme": None,
                        "AI_Birincil_Konu": None,
                    },
                    "metadata": {
                        "why_selected": None,
                        "annotator": None,
                        "annotated_at": None,
                        "version": "1.0",
                    },
                }
            )

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(batch_data, f, indent=2, ensure_ascii=False)

        print(f"📄 Exported {len(batch_data)} candidates to {output_file}")


def main() -> None:
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Golden dataset annotation tool")
    parser.add_argument("candidates", help="Path to candidates CSV file")
    parser.add_argument("--batch", help="Export for batch annotation to this JSON file")
    parser.add_argument("--dataset", help="Path to golden dataset JSON file")

    args = parser.parse_args()

    # Initialize dataset
    dataset = GoldenDataset(Path(args.dataset)) if args.dataset else None

    annotator = GoldenAnnotator(args.candidates, dataset)

    if args.batch:
        annotator.run_batch(args.batch)
    else:
        annotator.run_interactive()


if __name__ == "__main__":
    main()
