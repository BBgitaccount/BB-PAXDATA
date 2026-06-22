"""Application protocols for domain services.

This module defines the interfaces that all domain services must implement.
It provides a clean separation between the application layer and domain layer,
following the Dependency Inversion Principle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

from .domain.ports.speech_act_port import SpeechActClassifierProtocol

if TYPE_CHECKING:
    from .domain.models.appraisal_vector import AppraisalVector
    from .domain.models.segment import Segment
    from .domain.models.sentence import Sentence
    from .domain.models.srl import SRLFrame


from typing import runtime_checkable

from .domain.models.service_results import (
    AnomalyResult,
    FrameResult,
    HedgingResult,
    RiskAssessment,
    SentimentResult,
    TopicAnalysis,
)


@runtime_checkable
class AppraisalServiceProtocol(Protocol):
    """Protocol for appraisal theory vector services."""

    def analyze(
        self,
        text: str,
        segment_id: str | None = None,
        srl_frame: SRLFrame | None = None,
        hedging_detected_markers: list[str] | None = None,
    ) -> AppraisalVector:
        """Analyze appraisal theory vectors in text.

        Args:
            text: The text to analyze
            segment_id: Optional segment ID
            srl_frame: Optional SRL frame from semantic role labeling
            hedging_detected_markers: Optional list of detected hedging markers

        Returns:
            AppraisalVector containing affect, judgment, appreciation, graduation, and engagement
        """
        ...


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

    def assess_risk(
        self, segment: Segment, sentences: list[Sentence] | None = None
    ) -> RiskAssessment:
        """Assess risk level of a segment.

        Args:
            segment: The segment to assess
            sentences: Optional list of sentences

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


class LLMServiceProtocol(Protocol):
    """Protocol for LLM services, e.g. for generating narratives."""

    @property
    def model_name(self) -> str:
        """The name of the underlying model used by the service."""
        ...

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text completion from a prompt asynchronously."""
        ...


__all__ = [
    "AnomalyResult",
    "AppraisalServiceProtocol",
    "BaseService",
    "FrameResult",
    "FramingServiceProtocol",
    "HedgingResult",
    "HedgingServiceProtocol",
    "LLMServiceProtocol",
    "NERServiceProtocol",
    "RiskAssessment",
    "RiskServiceProtocol",
    "SentimentResult",
    "SentimentServiceProtocol",
    "SpeechActClassifierProtocol",
    "TokenizerServiceProtocol",
    "TopicAnalysis",
    "TopicServiceProtocol",
]
