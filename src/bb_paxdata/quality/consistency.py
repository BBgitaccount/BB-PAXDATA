"""Consistency calculation utilities for uncertainty scoring."""

import math
from collections import Counter
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConsistencyCalculator:
    """Calculates various consistency metrics for AI outputs."""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__)

    def numeric_consistency(self, values: list[float]) -> float:
        """
        Calculate consistency for numeric values using coefficient of variation.

        Args:
            values: List of numeric values

        Returns:
            Consistency score (0.0 - 1.0)
        """
        if len(values) < 2:
            return 0.0

        try:
            # Convert to float
            numeric_values = [float(v) for v in values]

            # Calculate mean and standard deviation
            mean_val = sum(numeric_values) / len(numeric_values)

            if mean_val == 0:
                # Handle zero mean case
                variance = sum((v - mean_val) ** 2 for v in numeric_values) / len(
                    numeric_values
                )
                std_dev = math.sqrt(variance)
                if std_dev == 0:
                    return 1.0  # All values are identical
                else:
                    return 0.0  # High variation relative to mean

            # Calculate coefficient of variation
            variance = sum((v - mean_val) ** 2 for v in numeric_values) / len(
                numeric_values
            )
            std_dev = math.sqrt(variance)
            cv = std_dev / abs(mean_val)

            # Convert to consistency score (lower CV = higher consistency)
            # CV of 0 -> score 1.0, CV of 1.0 -> score 0.0
            consistency = max(0.0, 1.0 - cv)

            return consistency

        except (ValueError, TypeError) as e:
            self.logger.error(f"Error calculating numeric consistency: {e}")
            return 0.0

    def categorical_consensus(self, values: list[str]) -> float:
        """
        Calculate consensus ratio for categorical values.

        Args:
            values: List of categorical values

        Returns:
            Consensus score (0.0 - 1.0)
        """
        if not values:
            return 0.0

        try:
            # Normalize values (lowercase, strip)
            normalized_values = [
                str(v).strip().lower() for v in values if v is not None
            ]

            if not normalized_values:
                return 0.0

            # Count frequencies
            counter = Counter(normalized_values)
            most_common_count = counter.most_common(1)[0][1]
            total_count = len(normalized_values)

            # Consensus ratio
            consensus = most_common_count / total_count

            return consensus

        except Exception as e:
            self.logger.error(f"Error calculating categorical consensus: {e}")
            return 0.0

    def textual_consistency(self, values: list[str]) -> float:
        """
        Calculate consistency for textual values using Jaccard similarity.

        Args:
            values: List of textual values

        Returns:
            Consistency score (0.0 - 1.0)
        """
        if len(values) < 2:
            return 0.0

        try:
            # Normalize and tokenize values
            normalized_values = []
            for value in values:
                if value is None:
                    continue
                # Convert to lowercase and split into words
                text = str(value).lower()
                words = set(text.split())
                normalized_values.append(words)

            if len(normalized_values) < 2:
                return 0.0

            # Calculate pairwise Jaccard similarities
            similarities = []
            for i in range(len(normalized_values)):
                for j in range(i + 1, len(normalized_values)):
                    set1, set2 = normalized_values[i], normalized_values[j]

                    # Jaccard similarity
                    intersection = set1.intersection(set2)
                    union = set1.union(set2)

                    if union:
                        similarity = len(intersection) / len(union)
                        similarities.append(similarity)

            # Average similarity
            if similarities:
                avg_similarity = sum(similarities) / len(similarities)
                return avg_similarity
            else:
                return 0.0

        except Exception as e:
            self.logger.error(f"Error calculating textual consistency: {e}")
            return 0.0

    def embedding_consistency(self, values: list[str]) -> float:
        """
        Calculate consistency using embedding similarity (placeholder for future
        implementation).

        Args:
            values: List of textual values

        Returns:
            Consistency score (0.0 - 1.0)
        """
        # This would use sentence embeddings for more accurate textual similarity
        # For now, fall back to Jaccard similarity
        return self.textual_consistency(values)

    def mixed_field_consistency(
        self, values: list[Any], field_type: str = "auto"
    ) -> float:
        """
        Calculate consistency for mixed field types.

        Args:
            values: List of values of any type
            field_type: Type hint ("numeric", "categorical", "textual", "auto")

        Returns:
            Consistency score (0.0 - 1.0)
        """
        if not values:
            return 0.0

        # Auto-detect field type if not specified
        if field_type == "auto":
            field_type = self._detect_field_type(values)

        # Route to appropriate consistency calculator
        if field_type == "numeric":
            numeric_values = [float(v) for v in values if self._is_numeric(v)]
            return self.numeric_consistency(numeric_values)
        elif field_type == "categorical":
            string_values = [str(v) for v in values if v is not None]
            return self.categorical_consensus(string_values)
        elif field_type == "textual":
            string_values = [str(v) for v in values if v is not None]
            return self.textual_consistency(string_values)
        else:
            # Default to textual
            string_values = [str(v) for v in values if v is not None]
            return self.textual_consistency(string_values)

    def _detect_field_type(self, values: list[Any]) -> str:
        """Detect the type of field based on values."""
        if not values:
            return "textual"

        # Count numeric values
        numeric_count = sum(1 for v in values if self._is_numeric(v))

        # If most values are numeric, treat as numeric field
        if numeric_count / len(values) > 0.7:
            return "numeric"

        # Check for categorical (low cardinality strings)
        string_values = [str(v) for v in values if v is not None]
        unique_strings = set(string_values)

        if len(unique_strings) <= 10 and len(string_values) > 0:
            return "categorical"

        # Default to textual
        return "textual"

    def _is_numeric(self, value: Any) -> bool:
        """Check if value can be converted to numeric."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def calculate_batch_consistency(self, batch_values: list[list[Any]]) -> list[float]:
        """
        Calculate consistency for multiple fields in a batch.

        Args:
            batch_values: List of value lists, one per field

        Returns:
            List of consistency scores
        """
        consistency_scores = []

        for values in batch_values:
            score = self.mixed_field_consistency(values)
            consistency_scores.append(score)

        return consistency_scores

    def get_consensus_value(self, values: list[Any]) -> Any:
        """
        Get the consensus value from a list of values.

        Args:
            values: List of values

        Returns:
            Most common or representative value
        """
        if not values:
            return None

        # Filter out None values
        valid_values = [v for v in values if v is not None]

        if not valid_values:
            return None

        # Detect field type
        field_type = self._detect_field_type(valid_values)

        if field_type == "numeric":
            # Return median for numeric values
            numeric_values = [float(v) for v in valid_values if self._is_numeric(v)]
            if numeric_values:
                numeric_values.sort()
                n = len(numeric_values)
                if n % 2 == 0:
                    return (numeric_values[n // 2 - 1] + numeric_values[n // 2]) / 2
                else:
                    return numeric_values[n // 2]
        else:
            # Return most common for categorical/textual
            string_values = [str(v) for v in valid_values]
            counter = Counter(string_values)
            return counter.most_common(1)[0][0]

        return valid_values[0]  # Fallback
