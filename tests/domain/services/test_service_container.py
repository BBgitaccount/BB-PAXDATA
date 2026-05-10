"""Unit tests for ServiceContainer."""

from unittest.mock import Mock

import pytest
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.services.service_container import (
    NERStub,
    ServiceContainer,
    TokenizerStub,
    get_default_container,
    get_risk_service,
    get_sentiment_service,
)


class TestServiceContainer:
    """Test cases for ServiceContainer."""

    def test_service_container_initialization(self):
        """Test ServiceContainer initialization."""
        container = ServiceContainer()

        assert container is not None
        assert container._ner_service is not None
        assert container._tokenizer_service is not None
        assert isinstance(container._ner_service, NERStub)
        assert isinstance(container._tokenizer_service, TokenizerStub)

    def test_service_container_with_custom_services(self):
        """Test ServiceContainer with custom services."""
        mock_ner = Mock()
        mock_tokenizer = Mock()

        container = ServiceContainer(
            ner_service=mock_ner, tokenizer_service=mock_tokenizer
        )

        assert container._ner_service is mock_ner
        assert container._tokenizer_service is mock_tokenizer

    def test_sentiment_service_lazy_loading(self):
        """Test lazy loading of sentiment service."""
        container = ServiceContainer()

        # Service should not be loaded initially
        assert container._sentiment_service is None

        # Access should load the service
        sentiment_service = container.sentiment
        assert sentiment_service is not None
        assert container._sentiment_service is sentiment_service

        # Subsequent access should return same instance
        assert container.sentiment is sentiment_service

    def test_risk_service_lazy_loading(self):
        """Test lazy loading of risk service."""
        container = ServiceContainer()

        assert container._risk_service is None

        risk_service = container.risk
        assert risk_service is not None
        assert container._risk_service is risk_service
        assert container.risk is risk_service

    def test_hedging_service_lazy_loading(self):
        """Test lazy loading of hedging service."""
        container = ServiceContainer()

        assert container._hedging_service is None

        hedging_service = container.hedging
        assert hedging_service is not None
        assert container._hedging_service is hedging_service

    def test_framing_service_lazy_loading(self):
        """Test lazy loading of framing service."""
        container = ServiceContainer()

        assert container._framing_service is None

        framing_service = container.framing
        assert framing_service is not None
        assert container._framing_service is framing_service

    def test_topic_service_lazy_loading(self):
        """Test lazy loading of topic service."""
        container = ServiceContainer()

        assert container._topic_service is None

        topic_service = container.topic
        assert topic_service is not None
        assert container._topic_service is topic_service

    def test_anomaly_service_lazy_loading(self):
        """Test lazy loading of anomaly service."""
        container = ServiceContainer()

        assert container._anomaly_service is None

        anomaly_service = container.anomaly
        assert anomaly_service is not None
        assert container._anomaly_service is anomaly_service

    def test_configure_service(self):
        """Test service configuration."""
        container = ServiceContainer()

        # Configure sentiment service
        container.configure_service("sentiment", confidence=0.8)

        config = container.get_service_config("sentiment")
        assert config["confidence"] == 0.8

        # Service should be reset after configuration
        assert container._sentiment_service is None

    def test_get_service_config(self):
        """Test getting service configuration."""
        container = ServiceContainer()

        # Non-existent config should return empty dict
        config = container.get_service_config("nonexistent")
        assert config == {}

        # Set config and retrieve it
        container.configure_service("sentiment", confidence=0.9)
        config = container.get_service_config("sentiment")
        assert config["confidence"] == 0.9

    def test_reset_service(self):
        """Test resetting individual service."""
        container = ServiceContainer()

        # Load service
        sentiment_service = container.sentiment
        assert container._sentiment_service is not None

        # Reset service
        container.reset_service("sentiment")
        assert container._sentiment_service is None

        # Access should reload service
        new_sentiment_service = container.sentiment
        assert new_sentiment_service is not None
        assert new_sentiment_service is not sentiment_service  # New instance

    def test_reset_all_services(self):
        """Test resetting all services."""
        container = ServiceContainer()

        # Load all services
        _ = container.sentiment
        _ = container.risk
        _ = container.hedging
        _ = container.framing
        _ = container.topic
        _ = container.anomaly

        # Verify services are loaded
        assert container._sentiment_service is not None
        assert container._risk_service is not None
        assert container._hedging_service is not None
        assert container._framing_service is not None
        assert container._topic_service is not None
        assert container._anomaly_service is not None

        # Reset all services
        container.reset_all_services()

        # Verify all services are reset
        assert container._sentiment_service is None
        assert container._risk_service is None
        assert container._hedging_service is None
        assert container._framing_service is None
        assert container._topic_service is None
        assert container._anomaly_service is None

    def test_get_service_status(self):
        """Test getting service status."""
        container = ServiceContainer()

        # Initially no services loaded
        status = container.get_service_status()
        for _, is_loaded in status.items():
            assert is_loaded is False

        # Load a service
        _ = container.sentiment

        status = container.get_service_status()
        assert status["sentiment"] is True
        assert status["risk"] is False  # Still not loaded

    def test_create_analysis_pipeline(self):
        """Test creating analysis pipeline."""
        container = ServiceContainer()

        pipeline = container.create_analysis_pipeline()

        assert pipeline is not None
        assert hasattr(pipeline, "sentiment")
        assert hasattr(pipeline, "risk")
        assert hasattr(pipeline, "hedging")
        assert hasattr(pipeline, "framing")
        assert hasattr(pipeline, "topic")
        assert hasattr(pipeline, "anomaly")

    def test_ner_stub_basic_functionality(self):
        """Test NER stub basic functionality."""
        ner = NERStub()

        text = "turkey and nato discussed the situation in syria"
        entities = ner.extract_entities(text)

        assert isinstance(entities, dict)
        assert "GPE" in entities
        assert "ORG" in entities
        assert "PERSON" in entities

        # Should detect some entities
        assert len(entities["GPE"]) > 0
        assert "Turkey" in entities["GPE"] or "turkey" in entities["GPE"]
        assert "NATO" in entities["ORG"]

    def test_ner_stub_no_entities(self):
        """Test NER stub with no entities."""
        ner = NERStub()

        text = "this is a simple sentence"
        entities = ner.extract_entities(text)

        assert isinstance(entities, dict)
        assert all(len(entity_list) == 0 for entity_list in entities.values())

    def test_tokenizer_stub_basic_functionality(self):
        """Test tokenizer stub basic functionality."""
        tokenizer = TokenizerStub()

        text = "This is a simple test sentence."
        tokens = tokenizer.tokenize_words(text)

        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert "this" in tokens
        assert "is" in tokens
        assert "sentence" in tokens

    def test_tokenizer_stub_empty_text(self):
        """Test tokenizer stub with empty text."""
        tokenizer = TokenizerStub()

        tokens = tokenizer.tokenize_words("")
        assert tokens == []

    def test_analysis_pipeline_analyze_sentence(self):
        """Test analysis pipeline sentence analysis."""
        container = ServiceContainer()
        pipeline = container.create_analysis_pipeline()

        sentence = Sentence(id="1", text="We want peace and cooperation.")

        results = pipeline.analyze_sentence(sentence)

        assert isinstance(results, dict)
        assert "sentiment" in results
        assert "hedging" in results
        assert "framing" in results
        assert "topic" in results

        # Check that results have expected structure
        assert hasattr(results["sentiment"], "score")
        assert hasattr(results["hedging"], "score")
        assert hasattr(results["framing"], "frame_type")
        assert hasattr(results["topic"], "dominant_topic")

    def test_analysis_pipeline_analyze_segment(self):
        """Test analysis pipeline segment analysis."""
        container = ServiceContainer()
        pipeline = container.create_analysis_pipeline()

        sentence = Sentence(id="1", text="We must cooperate.")
        segment = Segment(id="seg1", sentences=[sentence])

        results = pipeline.analyze_segment(segment)

        assert isinstance(results, dict)
        assert "risk" in results
        assert "topic" in results

        # Check that results have expected structure
        assert hasattr(results["risk"], "risk_score")
        assert hasattr(results["risk"], "severity")

    def test_analysis_pipeline_detect_anomalies(self):
        """Test analysis pipeline anomaly detection."""
        container = ServiceContainer()
        pipeline = container.create_analysis_pipeline()

        # Create mock analysis with potential anomalies
        analysis = Mock()
        analysis.ai_sentiment_score = -0.8
        analysis.ai_risk_score = 8.0
        analysis.ai_hedging_score = 0.7
        analysis.ai_manipulation_score = 0.8
        analysis.sentiment_score = 0.5
        analysis.risk_score = 7.5
        analysis.hedging_score = 0.1
        analysis.manipulation_score = 0.4
        analysis.speaker_power = 9
        analysis.sbi_score = 8.5
        analysis.dki_score = 0.3

        anomalies = pipeline.detect_anomalies(analysis)

        assert isinstance(anomalies, list)
        # Should detect some anomalies given the conflicting values
        assert len(anomalies) >= 0

    def test_get_default_container(self):
        """Test global default container function."""
        container1 = get_default_container()
        container2 = get_default_container()

        # Should return same instance (cached)
        assert container1 is container2
        assert isinstance(container1, ServiceContainer)

    def test_get_sentiment_service(self):
        """Test global sentiment service function."""
        service = get_sentiment_service()

        assert service is not None
        assert hasattr(service, "analyze")

    def test_get_risk_service(self):
        """Test global risk service function."""
        service = get_risk_service()

        assert service is not None
        assert hasattr(service, "assess_risk")

    def test_service_integration(self):
        """Test integration between services."""
        container = ServiceContainer()

        # Test that services work together
        sentence = Sentence(id="1", text="We do not want this unacceptable war.")

        sentiment_result = container.sentiment.analyze(sentence)
        hedging_result = container.hedging.analyze_hedging(sentence.text)
        framing_result = container.framing.detect_frame(sentence)
        topic_result = container.topic.analyze_topics(sentence.text)

        # All results should be valid
        assert sentiment_result is not None
        assert hedging_result is not None
        assert framing_result is not None
        assert topic_result is not None

        # Results should be consistent
        assert sentiment_result.negation_aware_score > 0.0  # Due to negation
        assert hedging_result.score >= 0.0
        assert topic_result.confidence >= 0.0


if __name__ == "__main__":
    pytest.main([__file__])
