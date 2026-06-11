"""Fulfillment tracking service for demand analysis."""

from datetime import datetime, timezone
from typing import Protocol

from ..models.demand import Demand


class FulfillmentTrackerProtocol(Protocol):
    """Protocol for fulfillment tracking."""

    def check_fulfillment(self, demand: Demand, responses: list[str]) -> bool:
        """Check if demand has been fulfilled.

        Args:
            demand: Demand to check
            responses: List of response texts

        Returns:
            True if demand is fulfilled, False otherwise
        """
        ...

    def get_fulfillment_timestamp(
        self, demand: Demand, responses: list[tuple[str, float]]
    ) -> datetime | None:
        """Get timestamp when demand was fulfilled.

        Args:
            demand: Demand to check
            responses: List of (response_text, timestamp) tuples

        Returns:
            Fulfillment timestamp or None if not fulfilled
        """
        ...

    def get_compliance_status(self, demand: Demand) -> str:
        """Get compliance status of demand.

        Args:
            demand: Demand to check

        Returns:
            Compliance status string
        """
        ...


class FulfillmentTracker:
    """Track demand fulfillment and compliance."""

    def check_fulfillment(self, demand: Demand, responses: list[str]) -> bool:
        """Check if demand has been fulfilled.

        Args:
            demand: Demand to check
            responses: List of response texts

        Returns:
            True if demand is fulfilled, False otherwise
        """
        if not responses:
            return False

        # Simple keyword matching
        demand_keywords = set(demand.demand_text.lower().split())

        for response in responses:
            response_keywords = set(response.lower().split())

            # High overlap = likely fulfilled
            overlap = len(demand_keywords & response_keywords)
            if overlap >= len(demand_keywords) * 0.5:
                return True

        return False

    def get_fulfillment_timestamp(
        self, demand: Demand, responses: list[tuple[str, float]]
    ) -> datetime | None:
        """Get timestamp when demand was fulfilled.

        Args:
            demand: Demand to check
            responses: List of (response_text, timestamp) tuples

        Returns:
            Fulfillment timestamp or None if not fulfilled
        """
        if not demand.is_fulfilled or not responses:
            return None

        # Return first response timestamp
        return datetime.fromtimestamp(responses[0][1], timezone.utc)

    def get_compliance_status(self, demand: Demand) -> str:
        """Get compliance status of demand.

        Args:
            demand: Demand to check

        Returns:
            Compliance status string
        """
        if demand.is_fulfilled:
            if demand.deadline and demand.fulfillment_timestamp:
                deadline_ts = datetime.fromtimestamp(demand.deadline, timezone.utc)
                if demand.fulfillment_timestamp <= deadline_ts:
                    return "accepted_on_time"
                else:
                    return "accepted_late"
            return "accepted"
        elif demand.deadline and demand.timestamp:
            # Check if deadline passed
            current_time = datetime.now(timezone.utc).timestamp()
            if current_time > demand.deadline:
                return "rejected_expired"
            return "pending"
        return "unknown"
