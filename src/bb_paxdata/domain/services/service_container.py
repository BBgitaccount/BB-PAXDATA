"""Service container for dependency injection.

This module provides a centralized container for managing domain services
and their dependencies. It implements the Service Locator pattern for
clean dependency injection and service lifecycle management.
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ..models.analysis import Analysis
    from ..models.segment import Segment
    from ..models.sentence import Sentence
else:
    Sentence = None
    Segment = None
    Analysis = None

from ...application.protocols import (
    FramingServiceProtocol,
    HedgingServiceProtocol,
    NERServiceProtocol,
    RiskServiceProtocol,
    SentimentServiceProtocol,
    TokenizerServiceProtocol,
    TopicServiceProtocol,
)
from .cross_anomaly_service import CrossAnomalyService
from .framing_service import FramingService
from .hedging_service import HedgingService
from .protocols import AnomalyResult, AnomalyServiceProtocol
from .risk_service import RiskService
from .segment_service import SegmentService
from .sentiment_service import SentimentService
from .topic_service import TopicService


class NERStub(NERServiceProtocol):
    """Stub implementation of NER service for testing and development."""

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract basic entities using simple patterns.

        Args:
            text: Text to analyze

        Returns:
            Dictionary of entity types to entity lists
        """
        # Simple regex-based entity extraction for development
        import re

        entities: dict[str, list[str]] = {
            "GPE": [],  # Geopolitical entities
            "ORG": [],  # Organizations
            "PERSON": [],  # People
        }

        # Basic country patterns
        countries = [
            "turkey",
            "türkiye",
            "ukraine",
            "russia",
            "syria",
            "iran",
            "israel",
            "palestine",
            "gaza",
            "usa",
            "united states",
            "china",
            "france",
            "germany",
            "uk",
            "britain",
            "nato",
            "eu",
            "un",
        ]

        for country in countries:
            if country in text.lower():
                entities["GPE"].append(country.title())

        # Basic organization patterns
        orgs = ["un", "nato", "eu", "security council", "general assembly"]
        for org in orgs:
            if org in text.lower():
                entities["ORG"].append(org.upper())

        # Basic person patterns (very simplified)
        person_patterns = [
            r"\b(President|Prime Minister|Minister|Ambassador)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(said|stated|declared|announced)",
        ]

        for pattern in person_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    name = " ".join(
                        [
                            part
                            for part in match
                            if part
                            and part.lower()
                            not in [
                                "president",
                                "prime",
                                "minister",
                                "ambassador",
                                "said",
                                "stated",
                                "declared",
                                "announced",
                            ]
                        ]
                    )
                    if name:
                        entities["PERSON"].append(name)

        return entities


class TokenizerStub(TokenizerServiceProtocol):
    """Stub implementation of tokenizer service."""

    def tokenize_words(self, text: str) -> list[str]:
        """Simple word tokenization.

        Args:
            text: Text to tokenize

        Returns:
            List of word tokens
        """
        import re

        return re.findall(r"\b\w+\b", text.lower())


class ServiceContainer:
    """Container for managing domain services and dependencies."""

    def __init__(
        self,
        ner_service: NERServiceProtocol | None = None,
        tokenizer_service: TokenizerServiceProtocol | None = None,
    ):
        """Initialize the service container.

        Args:
            ner_service: Optional NER service implementation
            tokenizer_service: Optional tokenizer service implementation
        """
        self._ner_service = ner_service or NERStub()
        self._tokenizer_service = tokenizer_service or TokenizerStub()

        # Initialize services
        self._sentiment_service: SentimentServiceProtocol | None = None
        self._risk_service: RiskServiceProtocol | None = None
        self._hedging_service: HedgingServiceProtocol | None = None
        self._framing_service: FramingServiceProtocol | None = None
        self._topic_service: TopicServiceProtocol | None = None
        self._anomaly_service: AnomalyServiceProtocol | None = None
        self._segment_service: SegmentService | None = None

        # Service configuration
        self._service_config: dict[str, Any] = {}

    @property
    def sentiment(self) -> SentimentServiceProtocol:
        """Get the sentiment analysis service."""
        if self._sentiment_service is None:
            self._sentiment_service = SentimentService()
        return self._sentiment_service

    @property
    def risk(self) -> RiskServiceProtocol:
        """Get the risk assessment service."""
        if self._risk_service is None:
            self._risk_service = RiskService(ner_service=self._ner_service)
        return self._risk_service

    @property
    def hedging(self) -> HedgingServiceProtocol:
        """Get the hedging analysis service."""
        if self._hedging_service is None:
            self._hedging_service = HedgingService()
        return self._hedging_service

    @property
    def framing(self) -> FramingServiceProtocol:
        """Get the framing analysis service."""
        if self._framing_service is None:
            self._framing_service = FramingService(ner_service=self._ner_service)
        return self._framing_service

    @property
    def topic(self) -> TopicServiceProtocol:
        """Get the topic analysis service."""
        if self._topic_service is None:
            self._topic_service = TopicService()
        return self._topic_service

    @property
    def segment(self) -> SegmentService:
        """Get the segment analysis service."""
        if self._segment_service is None:
            self._segment_service = SegmentService(risk_service=self.risk)
        return self._segment_service

    @property
    def anomaly(self) -> AnomalyServiceProtocol:
        """Get the cross-anomaly detection service."""
        if self._anomaly_service is None:
            self._anomaly_service = CrossAnomalyService()
        assert self._anomaly_service is not None
        return self._anomaly_service

    @property
    def ner(self) -> NERServiceProtocol:
        """Get the NER service."""
        return self._ner_service

    @property
    def tokenizer(self) -> TokenizerServiceProtocol:
        """Get the tokenizer service."""
        return self._tokenizer_service

    def configure_service(self, service_name: str, **kwargs: Any) -> None:
        """Configure a service with custom parameters.

        Args:
            service_name: Name of the service to configure
            **kwargs: Configuration parameters
        """
        self._service_config[service_name] = kwargs

        # Reset the service to apply new configuration
        if hasattr(self, f"_{service_name}_service"):
            setattr(self, f"_{service_name}_service", None)

    def get_service_config(self, service_name: str) -> dict[str, Any]:
        """Get configuration for a service.

        Args:
            service_name: Name of the service

        Returns:
            Service configuration dictionary
        """
        return cast(dict[str, Any], self._service_config.get(service_name, {}))

    def reset_service(self, service_name: str) -> None:
        """Reset a service, forcing reinitialization.

        Args:
            service_name: Name of the service to reset
        """
        service_attr = f"_{service_name}_service"
        if hasattr(self, service_attr):
            setattr(self, service_attr, None)

    def reset_all_services(self) -> None:
        """Reset all services, forcing reinitialization."""
        service_names = [
            "sentiment",
            "risk",
            "hedging",
            "framing",
            "topic",
            "anomaly",
            "segment",
        ]

        for service_name in service_names:
            self.reset_service(service_name)

    def get_service_status(self) -> dict[str, bool]:
        """Get initialization status of all services.

        Returns:
            Dictionary mapping service names to initialization status
        """
        status = {}
        service_names = [
            "sentiment",
            "risk",
            "hedging",
            "framing",
            "topic",
            "anomaly",
            "segment",
        ]

        for service_name in service_names:
            service_attr = f"_{service_name}_service"
            status[service_name] = getattr(self, service_attr) is not None

        return status

    def create_analysis_pipeline(self) -> "AnalysisPipeline":
        """Create a configured analysis pipeline.

        Returns:
            AnalysisPipeline instance with all services
        """
        return AnalysisPipeline(
            sentiment_service=self.sentiment,
            risk_service=self.risk,
            hedging_service=self.hedging,
            framing_service=self.framing,
            topic_service=self.topic,
            anomaly_service=self.anomaly,
            segment_service=self.segment,
        )


class AnalysisPipeline:
    """Pipeline for coordinated analysis using multiple services."""

    def __init__(
        self,
        sentiment_service: SentimentServiceProtocol,
        risk_service: RiskServiceProtocol,
        hedging_service: HedgingServiceProtocol,
        framing_service: FramingServiceProtocol,
        topic_service: TopicServiceProtocol,
        anomaly_service: AnomalyServiceProtocol,
        segment_service: SegmentService,
    ):
        """Initialize the analysis pipeline.

        Args:
            sentiment_service: Sentiment analysis service
            risk_service: Risk assessment service
            hedging_service: Hedging analysis service
            framing_service: Framing analysis service
            topic_service: Topic analysis service
            anomaly_service: Anomaly detection service
        """
        self.sentiment = sentiment_service
        self.risk = risk_service
        self.hedging = hedging_service
        self.framing = framing_service
        self.topic = topic_service
        self.anomaly = anomaly_service
        self.segment = segment_service

    def analyze_sentence(self, sentence: "Sentence") -> dict[str, Any]:
        """Perform comprehensive analysis on a sentence.

        Args:
            sentence: Sentence to analyze

        Returns:
            Dictionary containing all analysis results
        """
        results: dict[str, Any] = {}

        # Sentiment analysis
        results["sentiment"] = self.sentiment.analyze(sentence)

        # Hedging analysis
        results["hedging"] = self.hedging.analyze_hedging(sentence.text)

        # Framing analysis
        results["framing"] = self.framing.detect_frame(sentence)

        # Topic analysis
        results["topic"] = self.topic.analyze_topics(sentence.text)

        return results

    def analyze_segment(self, segment: "Segment") -> dict[str, Any]:
        """Perform comprehensive analysis on a segment.

        Args:
            segment: Segment to analyze

        Returns:
            Dictionary containing all analysis results
        """
        results: dict[str, Any] = {}

        # Risk assessment (segment-level)
        results["risk"] = self.risk.assess_risk(segment)

        # Topic analysis for segment text
        segment_text = getattr(segment, "text", "") or " ".join(
            [s.text for s in getattr(segment, "sentences", [])]
        )
        if segment_text:
            results["topic"] = self.topic.analyze_topics(segment_text)

        # 2.0 Segment Enrichment (Structure Parity)
        if hasattr(segment, "sentences"):
            self.segment.enrich_segment(segment, segment.sentences)

        return results

    async def detect_anomalies(self, analysis: "Analysis") -> AnomalyResult:
        """Detect anomalies in analysis results.

        Args:
            analysis: Analysis results to check

        Returns:
            Detected anomaly result
        """
        return await self.anomaly.detect(analysis)


# Global service container instance
@lru_cache(maxsize=1)
def get_default_container() -> ServiceContainer:
    """Get the default service container instance.

    Returns:
        Default ServiceContainer instance
    """
    return ServiceContainer()


# Convenience functions for quick access
def get_sentiment_service() -> SentimentServiceProtocol:
    """Get the default sentiment service."""
    return get_default_container().sentiment


def get_risk_service() -> RiskServiceProtocol:
    """Get the default risk service."""
    return get_default_container().risk


def get_hedging_service() -> HedgingServiceProtocol:
    """Get the default hedging service."""
    return get_default_container().hedging


def get_framing_service() -> FramingServiceProtocol:
    """Get the default framing service."""
    return get_default_container().framing


def get_topic_service() -> TopicServiceProtocol:
    """Get the default topic service."""
    return get_default_container().topic


def get_anomaly_service() -> AnomalyServiceProtocol:
    """Get the default anomaly service."""
    return get_default_container().anomaly


def get_segment_service() -> SegmentService:
    """Get the default segment service."""
    return get_default_container().segment
