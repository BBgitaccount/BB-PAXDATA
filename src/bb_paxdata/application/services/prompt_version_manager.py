"""
Prompt Version Manager Service.

Manages prompt version lifecycle, triggers, and A/B testing.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.prompt_version import (
    ABTest,
    ABTestStatus,
    FewShotExample,
    PromptVersion,
    PromptVersionStatus,
)
from bb_paxdata.application.services.few_shot_pool_manager import FewShotPoolManager

logger = structlog.get_logger(__name__)


class PromptVersionManager:
    """
    Manages prompt version lifecycle and A/B testing.

    Features:
    - Automatic version triggering based on correction rate
    - Explicit rule addition for systematic errors
    - Counter-example management
    - Semantic versioning (v2.1 -> v2.2)
    - A/B testing infrastructure
    """

    def __init__(
        self,
        db: AsyncSession,
        pool_manager: FewShotPoolManager,
        correction_rate_threshold: float = 0.3,
    ) -> None:
        self._db = db
        self._pool_manager = pool_manager
        self._correction_rate_threshold = correction_rate_threshold
        # In-memory storage (in production, use database)
        self._versions: dict[str, PromptVersion] = {}
        self._ab_tests: dict[str, ABTest] = {}

    def create_new_version(
        self,
        base_version_id: str | None = None,
        reason: str = "Manual creation",
    ) -> PromptVersion:
        """
        Create a new prompt version.

        Args:
            base_version_id: ID of version to base on (None for fresh start)
            reason: Reason for creating this version

        Returns:
            New PromptVersion
        """
        if base_version_id:
            base = self._versions.get(base_version_id)
            if not base:
                raise ValueError(f"Base version not found: {base_version_id}")
            new_version_str = base.increment_version()
            template = base.base_template
        else:
            new_version_str = "v1.0"
            template = "Default prompt template"

        version = PromptVersion(
            id=str(uuid.uuid4()),
            version=new_version_str,
            status=PromptVersionStatus.DRAFT,
            base_template=template,
            created_at=datetime.utcnow(),
            metadata={"reason": reason},
        )

        self._versions[version.id] = version
        logger.info(
            "prompt_version_created",
            version_id=version.id,
            version=new_version_str,
            reason=reason,
        )

        return version

    def trigger_version_update(
        self,
        field: str,
        correction_rate: float,
        systematic_error: str | None = None,
    ) -> PromptVersion | None:
        """
        Trigger a new version based on correction rate threshold.

        Args:
            field: Field with high correction rate
            correction_rate: Current correction rate
            systematic_error: Description of systematic error (optional)

        Returns:
            New PromptVersion if triggered, None otherwise
        """
        if correction_rate < self._correction_rate_threshold:
            logger.debug(
                "correction_rate_below_threshold",
                field=field,
                rate=correction_rate,
                threshold=self._correction_rate_threshold,
            )
            return None

        # Find active version for this field
        active_version = self._find_active_version()
        if not active_version:
            logger.warning("no_active_version_found")
            return None

        # Create new version
        new_version = self.create_new_version(
            base_version_id=active_version.id,
            reason=f"High correction rate ({correction_rate:.2f}) for {field}",
        )

        # Add few-shot examples from pool
        examples = self._pool_manager.get_examples_for_field(field, limit=5)
        new_version.few_shot_examples = list(examples)

        # Add systematic error as explicit rule if provided
        if systematic_error:
            new_version.explicit_rules.append(
                f"Systematic error detected: {systematic_error}"
            )

        logger.info(
            "version_update_triggered",
            field=field,
            correction_rate=correction_rate,
            new_version_id=new_version.id,
            new_version=new_version.version,
        )

        return new_version

    def _find_active_version(self) -> PromptVersion | None:
        """Find the currently active prompt version."""
        for version in self._versions.values():
            if version.status == PromptVersionStatus.ACTIVE:
                return version
        return None

    def add_counter_example(
        self, version_id: str, example: FewShotExample
    ) -> PromptVersion | None:
        """
        Add a counter-example to a prompt version.

        Counter-examples are cases the model should avoid.
        """
        version = self._versions.get(version_id)
        if not version:
            logger.warning("version_not_found", version_id=version_id)
            return None

        version.counter_examples.append(example)
        logger.info(
            "counter_example_added",
            version_id=version_id,
            example_id=example.id,
        )
        return version

    def add_explicit_rule(self, version_id: str, rule: str) -> PromptVersion | None:
        """
        Add an explicit rule to a prompt version.

        Used for systematic errors that need specific handling.
        """
        version = self._versions.get(version_id)
        if not version:
            logger.warning("version_not_found", version_id=version_id)
            return None

        version.explicit_rules.append(rule)
        logger.info(
            "explicit_rule_added",
            version_id=version_id,
            rule=rule,
        )
        return version

    def activate_version(self, version_id: str) -> PromptVersion | None:
        """
        Activate a prompt version.

        Deactivates any currently active version.
        """
        version = self._versions.get(version_id)
        if not version:
            logger.warning("version_not_found", version_id=version_id)
            return None

        # Deactivate current active version
        current_active = self._find_active_version()
        if current_active:
            current_active.status = PromptVersionStatus.DEPRECATED
            current_active.deprecated_at = datetime.utcnow()

        # Activate new version
        version.status = PromptVersionStatus.ACTIVE
        version.activated_at = datetime.utcnow()

        logger.info(
            "version_activated",
            version_id=version_id,
            version=version.version,
        )

        return version

    # A/B Testing Methods
    def start_ab_test(
        self,
        version_a_id: str,
        version_b_id: str,
        duration_days: int = 3,
    ) -> ABTest:
        """
        Start an A/B test between two prompt versions.

        Args:
            version_a_id: First version to test
            version_b_id: Second version to test
            duration_days: Test duration in days

        Returns:
            Created ABTest
        """
        version_a = self._versions.get(version_a_id)
        version_b = self._versions.get(version_b_id)

        if not version_a or not version_b:
            raise ValueError("One or both versions not found")

        # Set versions to testing status
        version_a.status = PromptVersionStatus.TESTING
        version_b.status = PromptVersionStatus.TESTING

        test = ABTest(
            id=str(uuid.uuid4()),
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            status=ABTestStatus.RUNNING,
            started_at=datetime.utcnow(),
            duration_days=duration_days,
        )

        self._ab_tests[test.id] = test

        logger.info(
            "ab_test_started",
            test_id=test.id,
            version_a=version_a.version,
            version_b=version_b.version,
            duration_days=duration_days,
        )

        return test

    def record_correction(
        self, test_id: str, version_id: str, is_correction: bool
    ) -> None:
        """
        Record a correction event for an A/B test.

        Args:
            test_id: ID of the A/B test
            version_id: ID of the version that produced the result
            is_correction: Whether this was a correction
        """
        test = self._ab_tests.get(test_id)
        if not test:
            logger.warning("ab_test_not_found", test_id=test_id)
            return

        if version_id == test.version_a_id:
            test.total_analyzed_a += 1
            if is_correction:
                test.correction_count_a += 1
        elif version_id == test.version_b_id:
            test.total_analyzed_b += 1
            if is_correction:
                test.correction_count_b += 1

    def complete_ab_test(self, test_id: str) -> ABTest | None:
        """
        Complete an A/B test and determine winner.

        Automatically selects winner based on correction rates.
        Deactivates loser version.
        """
        test = self._ab_tests.get(test_id)
        if not test:
            logger.warning("ab_test_not_found", test_id=test_id)
            return None

        test.status = ABTestStatus.COMPLETED
        test.ended_at = datetime.utcnow()

        # Determine winner
        winner_id = test.determine_winner()
        if winner_id:
            test.winner_version_id = winner_id

            # Activate winner, deactivate loser
            loser_id = (
                test.version_b_id
                if winner_id == test.version_a_id
                else test.version_a_id
            )

            self.activate_version(winner_id)

            loser = self._versions.get(loser_id)
            if loser:
                loser.status = PromptVersionStatus.DEPRECATED
                loser.deprecated_at = datetime.utcnow()

            logger.info(
                "ab_test_completed",
                test_id=test_id,
                winner_id=winner_id,
                loser_id=loser_id,
                rate_a=test.get_correction_rate_a(),
                rate_b=test.get_correction_rate_b(),
            )
        else:
            logger.info(
                "ab_test_completed_no_winner",
                test_id=test_id,
                rate_a=test.get_correction_rate_a(),
                rate_b=test.get_correction_rate_b(),
            )

        return test

    def check_ab_test_completion(self) -> list[ABTest]:
        """
        Check for A/B tests that should be completed.

        Returns list of completed tests.
        """
        completed = []
        now = datetime.utcnow()

        for test_id, test in self._ab_tests.items():
            if test.status == ABTestStatus.RUNNING:
                end_time = test.started_at + timedelta(days=test.duration_days)
                if now >= end_time:
                    completed_test = self.complete_ab_test(test_id)
                    if completed_test:
                        completed.append(completed_test)

        return completed

    def get_version(self, version_id: str) -> PromptVersion | None:
        """Get a prompt version by ID."""
        return self._versions.get(version_id)

    def list_versions(
        self, status: PromptVersionStatus | None = None
    ) -> Sequence[PromptVersion]:
        """List prompt versions, optionally filtered by status."""
        if status:
            return [v for v in self._versions.values() if v.status == status]
        return list(self._versions.values())

    def list_ab_tests(self, status: ABTestStatus | None = None) -> Sequence[ABTest]:
        """List A/B tests, optionally filtered by status."""
        if status:
            return [t for t in self._ab_tests.values() if t.status == status]
        return list(self._ab_tests.values())
