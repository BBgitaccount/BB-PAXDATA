"""Golden dataset loader and validator for BB-PAXDATA quality assurance."""

import json
from pathlib import Path
from typing import Any, cast

import jsonschema
import structlog

logger = structlog.get_logger(__name__)


class GoldenDataset:
    """Manages the golden dataset for quality evaluation."""

    def __init__(self, dataset_path: Path | None = None):
        self.dataset_path = (
            dataset_path or Path(__file__).parent / "golden_dataset.json"
        )
        self.schema_path = Path(__file__).parent / "golden_dataset_schema.json"
        self.logger = structlog.get_logger(__name__)
        self._cache: dict[str, Any] | None = None

    def load_schema(self) -> dict[str, Any]:
        """Load the JSON schema for validation."""
        try:
            with open(self.schema_path, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Schema file not found: {self.schema_path}"
            ) from None
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema file: {e}") from e

    def validate_fixture(self, fixture: dict[str, Any]) -> bool:
        """
        Validate a single fixture against the schema.

        Args:
            fixture: Fixture dictionary to validate

        Returns:
            True if valid, raises ValueError if invalid
        """
        schema = self.load_schema()
        try:
            jsonschema.validate(instance=fixture, schema=schema)
            return True
        except jsonschema.ValidationError as e:
            raise ValueError(f"Fixture validation failed: {e.message}") from e

    def load_dataset(self, force_reload: bool = False) -> dict[str, Any]:
        """
        Load the golden dataset from file with caching.

        Args:
            force_reload: Force reload even if cached

        Returns:
            Dictionary containing the dataset
        """
        if self._cache is not None and not force_reload:
            return self._cache

        if not self.dataset_path.exists():
            # Create empty dataset if it doesn't exist
            empty_dataset = {
                "version": "1.0",
                "created_at": "2026-05-12",
                "fixtures": [],
            }
            self.save_dataset(empty_dataset)
            self._cache = empty_dataset
            return empty_dataset

        try:
            with open(self.dataset_path, encoding="utf-8") as f:
                dataset = json.load(f)

            # Validate all fixtures
            for fixture in dataset.get("fixtures", []):
                self.validate_fixture(fixture)

            self._cache = dataset
            self.logger.info(
                f"Loaded {len(dataset.get('fixtures', []))} "
                "fixtures from golden dataset"
            )
            return cast(dict[str, Any], dataset)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in dataset file: {e}") from e
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Dataset file not found: {self.dataset_path}"
            ) from None

    def save_dataset(self, dataset: dict[str, Any]) -> None:
        """
        Save the dataset to file.

        Args:
            dataset: Dataset dictionary to save
        """
        # Validate all fixtures before saving
        for fixture in dataset.get("fixtures", []):
            self.validate_fixture(fixture)

        # Ensure parent directory exists
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.dataset_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        self._cache = dataset
        self.logger.info(
            f"Saved {len(dataset.get('fixtures', []))} fixtures to golden dataset"
        )

    def add_fixture(self, fixture: dict[str, Any]) -> None:
        """
        Add a new fixture to the dataset.

        Args:
            fixture: Fixture to add
        """
        # Validate the fixture
        self.validate_fixture(fixture)

        dataset = self.load_dataset()

        # Check for duplicate fixture_id
        existing_ids = {f["fixture_id"] for f in dataset["fixtures"]}
        if fixture["fixture_id"] in existing_ids:
            raise ValueError(f"Fixture ID {fixture['fixture_id']} already exists")

        dataset["fixtures"].append(fixture)
        self.save_dataset(dataset)
        self.logger.info(f"Added fixture {fixture['fixture_id']} to golden dataset")

    def get_fixture_by_id(self, fixture_id: str) -> dict[str, Any] | None:
        """
        Get a fixture by its ID.

        Args:
            fixture_id: ID of the fixture to retrieve

        Returns:
            Fixture dictionary or None if not found
        """
        dataset = self.load_dataset()
        for fixture in dataset.get("fixtures", []):
            if fixture["fixture_id"] == fixture_id:
                return cast(dict[str, Any], fixture)
        return None

    def get_fixtures_by_criteria(self, **criteria: Any) -> list[dict[str, Any]]:
        """
        Get fixtures matching specific criteria.

        Args:
            **criteria: Key-value pairs to match against fixtures

        Returns:
            List of matching fixtures
        """
        dataset = self.load_dataset()
        matching_fixtures = []

        for fixture in dataset.get("fixtures", []):
            match = True
            for key, value in criteria.items():
                if key == "metadata":
                    # Special handling for metadata criteria
                    for meta_key, meta_value in value.items():
                        if fixture.get("metadata", {}).get(meta_key) != meta_value:
                            match = False
                            break
                elif key in fixture:
                    if fixture[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break

            if match:
                matching_fixtures.append(fixture)

        return matching_fixtures

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the golden dataset.

        Returns:
            Dictionary with dataset statistics
        """
        dataset = self.load_dataset()
        fixtures = dataset.get("fixtures", [])

        if not fixtures:
            return {
                "total_fixtures": 0,
                "version": dataset.get("version", "unknown"),
                "created_at": dataset.get("created_at", "unknown"),
            }

        # Calculate statistics
        stats = {
            "total_fixtures": len(fixtures),
            "version": dataset.get("version", "unknown"),
            "created_at": dataset.get("created_at", "unknown"),
            "risk_distribution": {},
            "sentiment_distribution": {},
            "tone_distribution": {},
            "topic_distribution": {},
            "selection_reasons": {},
        }

        for fixture in fixtures:
            ground_truth = fixture.get("ground_truth", {})
            metadata = fixture.get("metadata", {})

            # Risk distribution
            risk = ground_truth.get("AI_Potansiyel_Risk", "unknown")
            stats["risk_distribution"][risk] = (
                stats["risk_distribution"].get(risk, 0) + 1
            )

            # Sentiment distribution
            sentiment = ground_truth.get("AI_Duygu_Kategorisi", "unknown")
            stats["sentiment_distribution"][sentiment] = (
                stats["sentiment_distribution"].get(sentiment, 0) + 1
            )

            # Tone distribution
            tone = ground_truth.get("AI_Diplomatik_Ton", "unknown")
            stats["tone_distribution"][tone] = (
                stats["tone_distribution"].get(tone, 0) + 1
            )

            # Topic distribution
            topic = ground_truth.get("AI_Birincil_Konu", "unknown")
            stats["topic_distribution"][topic] = (
                stats["topic_distribution"].get(topic, 0) + 1
            )

            # Selection reasons
            reason = metadata.get("why_selected", "unknown")
            stats["selection_reasons"][reason] = (
                stats["selection_reasons"].get(reason, 0) + 1
            )

        return stats


# Global instance for easy access
golden_dataset = GoldenDataset()
