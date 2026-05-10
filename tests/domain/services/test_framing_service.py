"""Unit tests for FramingService."""

from unittest.mock import Mock

import pytest
from bb_paxdata.domain.enums import (
    AppraisalAttitude,
    AudienceType,
    EvidenceType,
    FrameType,
)
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.services.framing_service import FramingService


class TestFramingService:
    """Test cases for FramingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FramingService()

    def test_framing_service_initialization(self):
        """Test that FramingService initializes correctly."""
        assert self.service is not None
        assert self.service.confidence == 1.0
        assert self.service._ner_service is None

    def test_framing_service_with_ner(self):
        """Test FramingService initialization with NER service."""
        mock_ner = Mock()
        service = FramingService(ner_service=mock_ner)
        assert service._ner_service is mock_ner

    def test_frame_lexicon_coverage(self):
        """Test that frame lexicon has all required topics."""
        lexicon = self.service.FRAME_LEXICON

        required_topics = [
            "Gazze_Filistin_İsrail",
            "Ukrayna_Rusya",
            "BM_Reformu",
            "Ekonomi_Ticaret_Enerji",
            "Güvenlik_Çatışma",
        ]

        for topic in required_topics:
            assert topic in lexicon
            assert len(lexicon[topic]) > 0

    def test_infer_topic_gaza(self):
        """Test topic inference for Gaza conflict."""
        text = "gaza palestine ceasefire humanitarian aid"

        topic = self.service._infer_topic(text)

        assert topic == "Gazze_Filistin_İsrail"

    def test_infer_topic_ukraine(self):
        """Test topic inference for Ukraine conflict."""
        text = "ukraine russia invasion sovereignty kyiv"

        topic = self.service._infer_topic(text)

        assert topic == "Ukrayna_Rusya"

    def test_infer_topic_un_reform(self):
        """Test topic inference for UN reform."""
        text = "united nations security council reform veto"

        topic = self.service._infer_topic(text)

        assert topic == "BM_Reformu"

    def test_infer_topic_no_match(self):
        """Test topic inference with no matching topic."""
        text = "This is a simple sentence."

        topic = self.service._infer_topic(text)

        assert topic is None

    def test_detect_frame_type_conflict(self):
        """Test conflict frame detection."""
        text = "war conflict military aggression"
        topic = "Güvenlik_Çatışma"

        frame = self.service._detect_frame_type(text, topic)

        assert frame == FrameType.CONFLICT

    def test_detect_frame_type_humanitarian(self):
        """Test humanitarian frame detection."""
        text = "humanitarian aid refugees civilians suffering"
        topic = "Gazze_Filistin_İsrail"

        frame = self.service._detect_frame_type(text, topic)

        assert frame == FrameType.HUMANITARIAN

    def test_detect_frame_type_neutral(self):
        """Test neutral frame detection."""
        text = "This is a simple sentence."

        frame = self.service._detect_frame_type(text, None)

        assert frame == FrameType.NEUTRAL

    def test_classify_evidence_statistical(self):
        """Test statistical evidence classification."""
        text = "The data shows statistics indicate 50 percent rate"

        evidence = self.service._classify_evidence(text)

        assert EvidenceType.STATISTICAL in evidence

    def test_classify_evidence_expert(self):
        """Test expert evidence classification."""
        text = "According to experts specialists and academic research"

        evidence = self.service._classify_evidence(text)

        assert EvidenceType.EXPERT in evidence

    def test_classify_evidence_historical(self):
        """Test historical evidence classification."""
        text = "Historically in the past traditionally as history shows"

        evidence = self.service._classify_evidence(text)

        assert EvidenceType.HISTORICAL in evidence

    def test_classify_evidence_no_evidence(self):
        """Test evidence classification with no evidence types."""
        text = "This is a simple statement."

        evidence = self.service._classify_evidence(text)

        assert evidence == [EvidenceType.NONE]

    def test_appraisal_score_positive(self):
        """Test positive appraisal attitude."""
        text = "This is good positive beneficial helpful"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.POSITIVE

    def test_appraisal_score_negative(self):
        """Test negative appraisal attitude."""
        text = "This is bad negative harmful dangerous"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.NEGATIVE

    def test_appraisal_score_neutral(self):
        """Test neutral appraisal attitude."""
        text = "This is neutral objective balanced impartial"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.NEUTRAL

    def test_appraisal_score_mixed(self):
        """Test mixed appraisal attitude."""
        text = "This has good and bad aspects"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.NEUTRAL

    def test_detect_audience_international(self):
        """Test international audience detection."""
        text = "united nations international global foreign countries"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.INTERNATIONAL

    def test_detect_audience_domestic(self):
        """Test domestic audience detection."""
        text = "domestic national local internal citizens"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.DOMESTIC

    def test_detect_audience_expert(self):
        """Test expert audience detection."""
        text = "expert technical professional specialized academic"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.EXPERT

    def test_detect_audience_general(self):
        """Test general audience detection."""
        text = "people public society community everyone"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.GENERAL

    def test_detect_audience_with_ner(self):
        """Test audience detection with NER entities."""
        mock_ner = Mock()
        mock_ner.extract_entities.return_value = {"GPE": ["syria", "turkey"]}

        service = FramingService(ner_service=mock_ner)
        text = "international community"

        audience = service._detect_audience(text)

        assert audience == AudienceType.INTERNATIONAL
        mock_ner.extract_entities.assert_called_once_with(text)

    def test_calculate_confidence_basic(self):
        """Test confidence calculation."""
        confidence = self.service._calculate_confidence(
            "test text", FrameType.CONFLICT, [EvidenceType.STATISTICAL]
        )

        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_neutral_frame(self):
        """Test confidence calculation with neutral frame."""
        confidence = self.service._calculate_confidence(
            "test text", FrameType.NEUTRAL, [EvidenceType.STATISTICAL]
        )

        # Should be lower for neutral frame
        assert confidence < 0.7

    def test_calculate_confidence_no_evidence(self):
        """Test confidence calculation with no evidence."""
        confidence = self.service._calculate_confidence(
            "short", FrameType.CONFLICT, [EvidenceType.NONE]
        )

        # Should be lower for no evidence
        assert confidence < 0.8

    def test_detect_frame_complete_analysis(self):
        """Test complete frame detection analysis."""
        text = "war conflict causes humanitarian crisis according to statistics"
        sentence = Sentence(id="1", text=text)
        sentence.dominant_topic = "Güvenlik_Çatışma"

        result = self.service.detect_frame(sentence)

        assert result is not None
        assert hasattr(result, "frame_type")
        assert hasattr(result, "evidence_types")
        assert hasattr(result, "appraisal_attitude")
        assert hasattr(result, "audience_type")
        assert hasattr(result, "confidence")

        assert result.frame_type == FrameType.CONFLICT
        assert EvidenceType.STATISTICAL in result.evidence_types
        assert 0.0 <= result.confidence <= 1.0

    def test_detect_frame_without_topic(self):
        """Test frame detection without explicit topic."""
        text = "united nations security council reform"
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type == FrameType.REFORM
        assert result.confidence > 0.0

    def test_detect_frame_mixed_signals(self):
        """Test frame detection with mixed signals."""
        text = "war conflict but also peace cooperation"
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type in [
            FrameType.CONFLICT,
            FrameType.POLITICAL,
            FrameType.NEUTRAL,
        ]

    def test_edge_case_complex_diplomatic_text(self):
        """Test with complex diplomatic text."""
        text = (
            "The united nations security council reform is essential for "
            "peaceful resolution of the ukraine conflict through "
            "diplomatic negotiations"
        )
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type in [
            FrameType.POLITICAL,
            FrameType.REFORM,
            FrameType.DIPLOMATIC,
        ]
        assert result.confidence > 0.0

    def test_edge_case_no_framing_signals(self):
        """Test with no framing signals."""
        text = "This is a simple statement."
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type == FrameType.NEUTRAL
        assert result.confidence < 0.7

    def test_edge_case_very_long_text(self):
        """Test with very long text."""
        text = "conflict war " * 50
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type == FrameType.CONFLICT
        assert result.confidence > 0.0

    def test_case_insensitive_detection(self):
        """Test that frame detection is case insensitive."""
        text_lower = "war conflict"
        text_upper = "WAR CONFLICT"

        sentence_lower = Sentence(id="1", text=text_lower)
        sentence_upper = Sentence(id="1", text=text_upper)

        result_lower = self.service.detect_frame(sentence_lower)
        result_upper = self.service.detect_frame(sentence_upper)

        assert result_lower.frame_type == result_upper.frame_type

    def test_multiple_evidence_types(self):
        """Test detection of multiple evidence types."""
        text = "According to experts, historical data and statistics show"
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert len(result.evidence_types) >= 2
        assert EvidenceType.EXPERT in result.evidence_types
        assert (
            EvidenceType.HISTORICAL in result.evidence_types
            or EvidenceType.STATISTICAL in result.evidence_types
        )


if __name__ == "__main__":
    pytest.main([__file__])
