"""Demand network service for tracking demand relationships."""

from typing import Protocol

from ..models.demand import Demand


class DemandNetworkServiceProtocol(Protocol):
    """Protocol for demand network analysis."""

    def find_related_demands(
        self, demand: Demand, all_demands: list[Demand]
    ) -> list[str]:
        """Find related demands.

        Args:
            demand: Target demand
            all_demands: List of all demands in the conversation

        Returns:
            List of related demand IDs
        """
        ...


class DemandNetworkService:
    """Track demand relationships and network structure."""

    def find_related_demands(
        self, demand: Demand, all_demands: list[Demand]
    ) -> list[str]:
        """Find related demands.

        Args:
            demand: Target demand
            all_demands: List of all demands in the conversation

        Returns:
            List of related demand IDs
        """
        related = []

        for other in all_demands:
            if other.id == demand.id:
                continue

            # Same speaker, similar topic
            if (
                other.speaker_id == demand.speaker_id
                and other.demand_category == demand.demand_category
            ):
                related.append(other.id)

            # Response to this demand
            if other.target_speaker_id == demand.speaker_id:
                related.append(other.id)

            # This demand is a response to other
            if demand.target_speaker_id == other.speaker_id:
                related.append(other.id)

        return related
