# src/bb_paxdata/application/domain/ports/i_visualization_repository.py

from typing import Any, Protocol


class IVisualizationRepository(Protocol):
    """
    Interface for querying database records required by visualization endpoints.
    Concrete implementation utilizes SQLAlchemy 2.0 async queries.
    """

    async def get_country_reference_aggregates(
        self, session_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves aggregated stats (total count, avg power, and contexts counts)
        from CountryReferenceTable, grouped by speaker_country.
        """
        ...

    async def get_country_stats(
        self, session_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves CountryStat records filtered by session_ids (if provided).
        """
        ...

    async def get_bilateral_sentiment_aggregates(
        self,
        session_ids: list[str] | None = None,
        relationship_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieves BilateralSentimentTable records filtered by session_ids and relationship_types.
        """
        ...

    async def get_global_pair_sentiments(self) -> list[dict[str, Any]]:
        """
        Retrieves all global relationship records from CountryPairSentiment.
        """
        ...

    async def get_sessions_list(self) -> list[dict[str, Any]]:
        """
        Retrieves all processed files/sessions ordered by import time.
        """
        ...

    async def get_all_reference_counts(self) -> list[dict[str, Any]]:
        """
        Retrieves praise and accusation counts aggregated per session (file_id).
        """
        ...

    async def get_reference_flows(
        self, session_id: str | None = None, context_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves reference flow groups from CountryReferenceTable,
        grouped by speaker_country, referenced_country, reference_context, and file_id.
        """
        ...

    async def get_pair_sentiments_for_country(
        self, country: str
    ) -> list[dict[str, Any]]:
        """
        Retrieves global relationship records where the country is either from or to.
        """
        ...

    async def get_country_stats_for_country(self, country: str) -> list[dict[str, Any]]:
        """
        Retrieves session-specific statistics for the specified country.
        """
        ...

    async def get_speaker_references_summary(self, country: str) -> dict[str, Any]:
        """
        Retrieves general sentiment and count for references made by the country as speaker.
        """
        ...

    async def get_target_references_summary(self, country: str) -> list[dict[str, Any]]:
        """
        Retrieves detailed count and average sentiment of references targeting this country,
        grouped by the speaker country and reference context.
        """
        ...
