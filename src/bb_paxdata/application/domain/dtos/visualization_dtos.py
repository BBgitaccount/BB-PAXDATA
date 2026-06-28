# src/bb_paxdata/application/domain/dtos/visualization_dtos.py

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class CountryNodeDTO(BaseModel):
    country: str = Field(..., description="Name of the country")
    iso_alpha3: str | None = Field(None, description="ISO 3166-1 alpha-3 code")
    total_interactions: int = Field(
        ..., description="Total interaction count (from + to)"
    )
    avg_sentiment: float = Field(..., description="Average sentiment score")
    dominant_emotion: str | None = Field(None, description="Dominant emotion")
    relationship_categories: dict[str, int] = Field(
        ..., description="Counts of each relationship type"
    )
    praise_count: int = Field(..., description="Count of praise references")
    accusation_count: int = Field(..., description="Count of accusation references")
    neutral_count: int = Field(..., description="Count of neutral mention references")
    power_level: float = Field(..., description="Average speaker power level")
    sessions: list[str] = Field(
        ..., description="List of sessions where this country appears"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_node(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Ensure counts are non-negative
            for field_name in [
                "total_interactions",
                "praise_count",
                "accusation_count",
                "neutral_count",
            ]:
                if field_name in data and data[field_name] is not None:
                    try:
                        data[field_name] = max(0, int(data[field_name]))
                    except (ValueError, TypeError):
                        data[field_name] = 0

            # Default missing arrays or dicts
            if (
                "relationship_categories" not in data
                or data["relationship_categories"] is None
            ):
                data["relationship_categories"] = {}
            if "sessions" not in data or data["sessions"] is None:
                data["sessions"] = []

        return data


class BilateralFlowDTO(BaseModel):
    from_country: str = Field(..., description="Speaker/Origin country")
    to_country: str = Field(..., description="Target/Destination country")
    from_iso3: str | None = Field(None, description="ISO code of origin country")
    to_iso3: str | None = Field(None, description="ISO code of target country")
    interaction_count: int = Field(
        ..., description="Total number of interactions between the pair"
    )
    avg_sentiment: float = Field(
        ..., description="Average sentiment of references from -> to"
    )
    affinity_score: float = Field(..., description="Average affinity score")
    power_weighted_score: float = Field(..., description="Average power weighted score")
    relationship_type: str = Field(..., description="Relationship classification")
    praise_ratio: float = Field(..., description="Praise count / total references")
    accusation_ratio: float = Field(
        ..., description="Accusation count / total references"
    )
    sessions: list[str] = Field(
        ..., description="Sessions in which this bilateral interaction appears"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_flow(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Clamp ratios between 0.0 and 1.0
            for key in ["praise_ratio", "accusation_ratio"]:
                if key in data and data[key] is not None:
                    try:
                        val = float(data[key])
                        data[key] = max(0.0, min(1.0, val))
                    except (ValueError, TypeError):
                        data[key] = 0.0

            if "sessions" not in data or data["sessions"] is None:
                data["sessions"] = []

        return data


class SentimentMatrixDTO(BaseModel):
    countries: list[str] = Field(
        ..., description="List of active countries sorted alphabetically"
    )
    matrix: list[list[float | None]] = Field(
        ..., description="N x N matrix of average sentiment scores"
    )
    interaction_matrix: list[list[int]] = Field(
        ..., description="N x N matrix of interaction counts"
    )
    relationship_matrix: list[list[str | None]] = Field(
        ..., description="N x N matrix of relationship types"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_matrix(cls, data: Any) -> Any:
        if isinstance(data, dict):
            countries = data.get("countries", [])
            len(countries)
            for key in ["matrix", "interaction_matrix", "relationship_matrix"]:
                val = data.get(key)
                if val is None or not isinstance(val, list):
                    data[key] = []
        return data


class SessionTimelineDTO(BaseModel):
    session_id: str = Field(..., description="Unique ID of the session (file_id)")
    session_label: str = Field(..., description="Human-readable session label")
    countries: list[str] = Field(..., description="Active countries in this session")
    avg_sentiment: float = Field(
        ..., description="Overall average sentiment of the session"
    )
    dominant_emotion: str = Field(..., description="Baskın duygu (dominant emotion)")
    top_relationships: list[dict[str, Any]] = Field(
        ..., description="Top 5 relationships by interaction count"
    )
    praise_count: int = Field(
        ..., description="Total praise references in this session"
    )
    accusation_count: int = Field(
        ..., description="Total accusation references in this session"
    )
    created_at: datetime | None = Field(None, description="Session ingestion date")

    @model_validator(mode="before")
    @classmethod
    def validate_timeline(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for count_field in ["praise_count", "accusation_count"]:
                if count_field in data and data[count_field] is not None:
                    try:
                        data[count_field] = max(0, int(data[count_field]))
                    except (ValueError, TypeError):
                        data[count_field] = 0
            if "countries" not in data or data["countries"] is None:
                data["countries"] = []
            if "top_relationships" not in data or data["top_relationships"] is None:
                data["top_relationships"] = []
        return data


class ReferenceFlowDTO(BaseModel):
    speaker_country: str = Field(..., description="Origin country making the reference")
    referenced_country: str = Field(..., description="Target country being referenced")
    context: str = Field(
        ..., description="Context type (PRAISE | ACCUSATION | NEUTRAL_MENTION)"
    )
    count: int = Field(..., description="Occurrence count of this reference flow")
    avg_sentiment: float = Field(
        ..., description="Average sentiment of this specific reference flow"
    )
    sessions: list[str] = Field(..., description="Sessions where this flow occurred")

    @model_validator(mode="before")
    @classmethod
    def validate_flow(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "count" in data and data["count"] is not None:
                try:
                    data["count"] = max(0, int(data["count"]))
                except (ValueError, TypeError):
                    data["count"] = 0
            if "sessions" not in data or data["sessions"] is None:
                data["sessions"] = []
        return data


class CountryRiskProfileDTO(BaseModel):
    country: str = Field(..., description="Name of the country")
    total_mentions: int = Field(..., description="Total mentions in the system")
    avg_sentiment: float = Field(..., description="Average overall sentiment score")
    sentiment_as_speaker: float = Field(
        ..., description="Average sentiment when this country is the speaker"
    )
    sentiment_as_target: float = Field(
        ..., description="Average sentiment when this country is referenced"
    )
    ally_count: int = Field(..., description="Number of alliance relationships")
    adversary_count: int = Field(..., description="Number of adversary relationships")
    accusation_ratio: float = Field(
        ...,
        description="Ratio of accusations targeted at this country vs total target references",
    )
    dominant_emotion: str = Field(
        ..., description="Dominant emotion associated with this country"
    )
    sessions_active: list[str] = Field(
        ..., description="List of session IDs where this country was active"
    )
    top_accusers: list[dict[str, Any]] = Field(
        ..., description="Top 5 accusers of this country"
    )
    top_praise_givers: list[dict[str, Any]] = Field(
        ..., description="Top 5 praise givers to this country"
    )
    relationship_breakdown: dict[str, int] = Field(
        ..., description="Breakdown counts of relationships"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_risk(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "accusation_ratio" in data and data["accusation_ratio"] is not None:
                try:
                    val = float(data["accusation_ratio"])
                    data["accusation_ratio"] = max(0.0, min(1.0, val))
                except (ValueError, TypeError):
                    data["accusation_ratio"] = 0.0

            for list_field in ["sessions_active", "top_accusers", "top_praise_givers"]:
                if list_field not in data or data[list_field] is None:
                    data[list_field] = []

            if (
                "relationship_breakdown" not in data
                or data["relationship_breakdown"] is None
            ):
                data["relationship_breakdown"] = {}

        return data
