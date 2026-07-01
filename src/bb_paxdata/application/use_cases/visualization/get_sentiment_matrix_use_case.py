# src/bb_paxdata/application/use_cases/visualization/get_sentiment_matrix_use_case.py


from bb_paxdata.application.domain.dtos.visualization_dtos import SentimentMatrixDTO
from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)
from bb_paxdata.infrastructure.mappings.country_iso_map import is_unknown_country


class GetSentimentMatrixUseCase:
    def __init__(self, repository: IVisualizationRepository) -> None:
        self.repository = repository

    async def execute(self) -> SentimentMatrixDTO:
        # 1. Fetch all global pair sentiments from repository
        pairs = await self.repository.get_global_pair_sentiments()

        # 2. Extract unique countries and sort alphabetically
        country_set = set()
        for p in pairs:
            if not is_unknown_country(p["from_country"]):
                country_set.add(p["from_country"])
            if not is_unknown_country(p["to_country"]):
                country_set.add(p["to_country"])

        countries = sorted(list(country_set))
        n = len(countries)

        # 3. Create index map for fast lookup
        idx_map = {c: i for i, c in enumerate(countries)}

        # 4. Initialize matrices
        matrix = [[None] * n for _ in range(n)]
        interaction_matrix = [[0] * n for _ in range(n)]
        relationship_matrix = [[None] * n for _ in range(n)]

        # 5. Populate matrices
        for p in pairs:
            if is_unknown_country(p["from_country"]) or is_unknown_country(
                p["to_country"]
            ):
                continue
            i = idx_map[p["from_country"]]
            j = idx_map[p["to_country"]]

            # Simple average sentiment (null if no data)
            matrix[i][j] = p["avg_sentiment"]
            interaction_matrix[i][j] = p["interaction_count"]
            relationship_matrix[i][j] = p["relationship_type"]

        return SentimentMatrixDTO(
            countries=countries,
            matrix=matrix,
            interaction_matrix=interaction_matrix,
            relationship_matrix=relationship_matrix,
        )
