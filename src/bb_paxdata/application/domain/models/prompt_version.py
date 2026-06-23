"""
Prompt Version Management Domain Models.

Defines models for few-shot example pools, prompt versions, and A/B testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExampleQuality(str, Enum):
    """Quality rating for few-shot examples."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PromptVersionStatus(str, Enum):
    """Status of prompt versions."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    TESTING = "testing"


class ABTestStatus(str, Enum):
    """Status of A/B tests."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class FewShotExample:
    """
    A few-shot example for prompt engineering.

    High-quality corrections can be added to the pool to improve future prompts.
    """

    id: str
    field: str  # e.g., "sentiment", "frame", "discourse_act"
    original_text: str
    corrected_value: Any
    original_ai_value: Any
    confidence: float  # AI confidence when this was corrected
    correction_rate: float  # Historical correction rate for similar cases
    quality: ExampleQuality
    source_correction_id: str | None = None  # Reference to CorrectionEvent
    added_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_reliable(self) -> bool:
        """
        Determine if this example is reliable for few-shot learning.

        Reliable examples have:
        - Low AI confidence (< 0.5)
        - High correction rate (> threshold)
        - High quality rating
        """
        return (
            self.confidence < 0.5
            and self.correction_rate > 0.3
            and self.quality == ExampleQuality.HIGH
        )


@dataclass
class FewShotPool:
    """
    A pool of few-shot examples for a specific field.

    Each field (sentiment, frame, discourse_act) has its own pool.
    """

    id: str
    field: str
    examples: list[FewShotExample] = field(default_factory=list)
    max_size: int = 100
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_example(self, example: FewShotExample) -> bool:
        """
        Add an example to the pool.

        Returns True if added, False if pool is full.
        Automatically removes oldest example if at capacity.
        """
        if len(self.examples) >= self.max_size:
            # Remove oldest example
            self.examples.pop(0)

        self.examples.append(example)
        self.updated_at = datetime.utcnow()
        return True

    def get_examples(self, limit: int = 10) -> list[FewShotExample]:
        """Get the most recent reliable examples."""
        reliable = [e for e in self.examples if e.is_reliable()]
        return reliable[-limit:]

    def cleanup_old_examples(self, max_age_days: int = 30) -> int:
        """
        Remove examples older than max_age_days.

        Returns number of examples removed.
        """
        cutoff = datetime.utcnow().timestamp() - (max_age_days * 86400)
        original_count = len(self.examples)
        self.examples = [e for e in self.examples if e.added_at.timestamp() > cutoff]
        removed = original_count - len(self.examples)
        if removed > 0:
            self.updated_at = datetime.utcnow()
        return removed


@dataclass
class PromptVersion:
    """
    A version of a prompt with its configuration.

    Uses semantic versioning (v2.1, v2.2, etc.).
    """

    id: str
    version: str  # e.g., "v2.1"
    status: PromptVersionStatus
    base_template: str
    few_shot_examples: list[FewShotExample] = field(default_factory=list)
    counter_examples: list[FewShotExample] = field(default_factory=list)
    explicit_rules: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: datetime | None = None
    deprecated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def increment_version(self) -> str:
        """Increment the version (e.g., v2.1 -> v2.2)."""
        # Parse version
        parts = self.version.replace("v", "").split(".")
        if len(parts) >= 2:
            major, minor = int(parts[0]), int(parts[1])
            minor += 1
            return f"v{major}.{minor}"
        return f"v{int(parts[0]) + 1}.0"


@dataclass
class ABTest:
    """
    An A/B test comparing two prompt versions.

    Runs for 2-3 days, then automatically selects winner.
    """

    id: str
    version_a_id: str
    version_b_id: str
    status: ABTestStatus
    started_at: datetime
    ended_at: datetime | None = None
    winner_version_id: str | None = None
    correction_count_a: int = 0
    correction_count_b: int = 0
    total_analyzed_a: int = 0
    total_analyzed_b: int = 0
    duration_days: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_correction_rate_a(self) -> float:
        """Get correction rate for version A."""
        if self.total_analyzed_a == 0:
            return 0.0
        return self.correction_count_a / self.total_analyzed_a

    def get_correction_rate_b(self) -> float:
        """Get correction rate for version B."""
        if self.total_analyzed_b == 0:
            return 0.0
        return self.correction_count_b / self.total_analyzed_b

    def determine_winner(self) -> str | None:
        """
        Determine the winner based on correction rates.

        Returns version ID of winner, or None if no clear winner.
        """
        rate_a = self.get_correction_rate_a()
        rate_b = self.get_correction_rate_b()

        # Winner is the version with lower correction rate
        if rate_a < rate_b and (rate_b - rate_a) > 0.05:  # >5% difference
            return self.version_a_id
        elif rate_b < rate_a and (rate_a - rate_b) > 0.05:
            return self.version_b_id

        return None  # No clear winner
