# src/bb_paxdata/quality/topic_validator.py
import pandas as pd
import pandera as pa

from bb_paxdata.domain.models.topic import TopicResult


class TopicDistributionSchema(pa.DataFrameModel):
    segment_id: str = pa.Field(nullable=False)
    topic_id: str = pa.Field(nullable=False)
    probability: float = pa.Field(ge=0.0, le=1.0)

    @pa.check("probability", groupby="segment_id")
    def probabilities_sum_to_one(cls, grouped: pd.Series) -> bool:
        return bool(grouped.sum().between(0.999999, 1.000001))


class TopicResultValidator:
    """Validates the output of TopicModelingService."""

    @staticmethod
    def validate_distributions(topic_result: TopicResult) -> bool:
        """Validates that topic probabilities for each segment sum to ~1.0."""
        data = []
        for assignment in topic_result.assignments:
            # -1 (outlier) topic'i genellikle 1.0'dır ama doğrulanmalı
            for topic_id, prob in assignment.topic_scores.items():
                data.append(
                    {
                        "segment_id": assignment.segment_id,
                        "topic_id": topic_id,
                        "probability": prob,
                    }
                )

        if not data:
            return True

        df = pd.DataFrame(data)
        try:
            TopicDistributionSchema.validate(df)
            return True
        except pa.errors.SchemaError:
            return False
