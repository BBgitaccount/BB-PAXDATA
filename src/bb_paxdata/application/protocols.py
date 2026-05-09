"""Application protocols for domain services.

This module defines the interfaces that all domain services must implement.
It provides a clean separation between the application layer and domain layer,
following the Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import BaseModel, Field

from ..domain.enums import (
    AnomalySeverity,
    AnomalyType,
    AppraisalAttitude,
    AudienceType,
    EvidenceType,
    FrameType,
    HedgingType,
    RiskLevel,
    SentimentCategory,
    TopicCategory,
)
from ..domain.models import Analysis, Segment, Sentence


# Result models for service outputs
class SentimentResult(BaseModel):
    """Result of sentiment analysis."""

    score: float = Field(
        ..., ge=-1.0, le=1.0, description="Sentiment score from -1 to 1"
    )
    emotion_category: SentimentCategory = Field(..., description="Emotion category")
    negation_aware_score: float = Field(
        ..., ge=-1.0, le=1.0, description="Negation-aware sentiment score"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class RiskAssessment(BaseModel):
    """Result of risk assessment."""

    sbi_score: float = Field(..., description="Söylemsel Baskı İndeksi score")
    dki_score: float = Field(..., description="Diplomatik Konum İndeksi score")
    risk_score: float = Field(..., ge=0.0, le=10.0, description="Overall risk score")
    risk_signals: list[str] = Field(
        default_factory=list, description="Detected risk signals"
    )
    severity: RiskLevel = Field(..., description="Risk severity level")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class HedgingResult(BaseModel):
    """Result of hedging analysis."""

    score: float = Field(..., ge=0.0, le=1.0, description="Hedging score from 0 to 1")
    categories: list[HedgingType] = Field(
        default_factory=list, description="Detected hedging categories"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class FrameResult(BaseModel):
    """Result of frame detection."""

    frame_type: FrameType = Field(..., description="Detected frame type")
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Evidence types used"
    )
    appraisal_attitude: AppraisalAttitude = Field(..., description="Appraisal attitude")
    audience_type: AudienceType = Field(..., description="Target audience type")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class TopicAnalysis(BaseModel):
    """Result of topic analysis."""

    topic_scores: dict[str, float] = Field(
        ..., description="Topic scores for each category"
    )
    dominant_topic: TopicCategory = Field(..., description="Dominant topic category")
    specificity: float = Field(
        ..., ge=0.0, le=1.0, description="Topic specificity score"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class AnomalyResult(BaseModel):
    """Result of anomaly detection."""

    type: AnomalyType = Field(..., description="Type of anomaly")
    severity: AnomalySeverity = Field(..., description="Severity level")
    category: str = Field(..., description="Anomaly category")
    description: str = Field(..., description="Description of the anomaly")
    ai_values: dict[str, Any] = Field(
        default_factory=dict, description="AI-derived values"
    )
    formula_values: dict[str, Any] = Field(
        default_factory=dict, description="Formula-derived values"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


# Service Protocols
class SentimentServiceProtocol(Protocol):
    """Protocol for sentiment analysis services."""

    def analyze(self, sentence: Sentence) -> SentimentResult:
        """Analyze sentiment of a sentence.

        Args:
            sentence: The sentence to analyze

        Returns:
            SentimentResult containing sentiment scores and categories
        """
        ...


class RiskServiceProtocol(Protocol):
    """Protocol for risk assessment services."""

    def assess_risk(self, segment: Segment) -> RiskAssessment:
        """Assess risk level of a segment.

        Args:
            segment: The segment to assess

        Returns:
            RiskAssessment containing risk scores and severity
        """
        ...


class HedgingServiceProtocol(Protocol):
    """Protocol for hedging analysis services."""

    def analyze_hedging(self, text: str) -> HedgingResult:
        """Analyze hedging language in text.

        Args:
            text: The text to analyze

        Returns:
            HedgingResult containing hedging score and categories
        """
        ...


class FramingServiceProtocol(Protocol):
    """Protocol for frame detection services."""

    def detect_frame(self, sentence: Sentence) -> FrameResult:
        """Detect framing in a sentence.

        Args:
            sentence: The sentence to analyze

        Returns:
            FrameResult containing frame type and related information
        """
        ...


class TopicServiceProtocol(Protocol):
    """Protocol for topic analysis services."""

    def analyze_topics(
        self, text: str, tfidf_keywords: list[str] | None = None
    ) -> TopicAnalysis:
        """Analyze topics in text.

        Args:
            text: The text to analyze
            tfidf_keywords: Optional TF-IDF keywords for enhanced analysis

        Returns:
            TopicAnalysis containing topic scores and dominant topic
        """
        ...


class CrossAnomalyServiceProtocol(Protocol):
    """Protocol for cross-anomaly detection services."""

    def detect_anomalies(self, analysis: Analysis) -> list[AnomalyResult]:
        """Detect cross-anomalies in analysis results.

        Args:
            analysis: The analysis results to check for anomalies

        Returns:
            List of detected anomalies
        """
        ...


class NERServiceProtocol(Protocol):
    """Protocol for Named Entity Recognition services."""

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract named entities from text.

        Args:
            text: The text to analyze

        Returns:
            Dictionary mapping entity types to lists of entities
        """
        ...


class TokenizerServiceProtocol(Protocol):
    """Protocol for tokenization services."""

    def tokenize_words(self, text: str) -> list[str]:
        """Tokenize text into words.

        Args:
            text: The text to tokenize

        Returns:
            List of word tokens
        """
        ...


# Abstract base classes for convenience
class BaseService(ABC):
    """Base class for all services providing common functionality."""

    def __init__(self) -> None:
        """Initialize the service."""
        self._confidence: float = 1.0

    @abstractmethod
    def analyze(self, *args: Any, **kwargs: Any) -> Any:
        """Abstract method for analysis operations."""
        pass

    @property
    def confidence(self) -> float:
        """Get the service confidence level."""
        return self._confidence

    @confidence.setter
    def confidence(self, value: float) -> None:
        """Set the service confidence level."""
        if not 0.0 <= value <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        self._confidence = value


__all__ = [
    "SentimentResult",
    "RiskAssessment",
    "HedgingResult",
    "FrameResult",
    "TopicAnalysis",
    "AnomalyResult",
    "SentimentServiceProtocol",
    "RiskServiceProtocol",
    "HedgingServiceProtocol",
    "FramingServiceProtocol",
    "TopicServiceProtocol",
    "CrossAnomalyServiceProtocol",
    "NERServiceProtocol",
    "TokenizerServiceProtocol",
    "BaseService",
]
