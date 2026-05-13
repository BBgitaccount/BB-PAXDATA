"""Unit tests for FramingService."""

from unittest.mock import Mock

import pytest
from bb_paxdata.domain.enums import (
    AppraisalAttitude,
    AudienceType,
    EvidenceType,
    FrameType,
)
from bb_paxdata.domain.enums.topic_category import TopicCategory
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.services.framing_service import FramingService


class TestFramingService:
    """Test cases for FramingService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = FramingService()

    async def test_framing_service_initialization(self) -> None:
        """Test that FramingService initializes correctly."""
        assert self.service is not None
        assert self.service.confidence == 1.0
        assert self.service._ner_service is None

    async def test_framing_service_with_ner(self) -> None:
        """Test FramingService initialization with NER service."""
        mock_ner = Mock()
        service = FramingService(ner_service=mock_ner)
        assert service._ner_service is mock_ner

    async def test_frame_lexicon_coverage(self) -> None:
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

    async def test_infer_topic_gaza(self) -> None:
        """Test topic inference for Gaza conflict."""
        text = "gaza palestine ceasefire humanitarian aid"

        topic = self.service._infer_topic(text)

        assert topic == "Gazze_Filistin_İsrail"

    async def test_infer_topic_ukraine(self) -> None:
        """Test topic inference for Ukraine conflict."""
        text = "ukraine russia invasion sovereignty kyiv"

        topic = self.service._infer_topic(text)

        assert topic == "Ukrayna_Rusya"

    async def test_infer_topic_un_reform(self) -> None:
        """Test topic inference for UN reform."""
        text = "BM_Reformu reform modernize transform"

        topic = self.service._infer_topic(text)

        assert topic == "BM_Reformu"

    async def test_infer_topic_no_match(self) -> None:
        """Test topic inference with no matching topic."""
        text = "This is a simple sentence."

        topic = self.service._infer_topic(text)

        assert topic is None

    async def test_detect_frame_type_conflict(self) -> None:
        """Test conflict frame detection."""
        text = "war conflict military aggression"
        topic = "Gazze_Filistin_İsrail"

        frame = self.service._detect_frame_type(text, topic)

        assert frame == FrameType.CONFLICT_FRAME

    async def test_detect_frame_type_humanitarian(self) -> None:
        """Test humanitarian frame detection."""
        text = "humanitarian aid refugees civilians suffering"
        topic = "Gazze_Filistin_İsrail"

        frame = self.service._detect_frame_type(text, topic)

        assert frame == FrameType.HUMANITARIAN_FRAME

    async def test_detect_frame_type_neutral(self) -> None:
        """Test neutral frame detection."""
        text = "This is a simple sentence."

        frame = self.service._detect_frame_type(text, None)

        assert frame == FrameType.NEUTRAL

    async def test_classify_evidence_statistical(self) -> None:
        """Test statistical evidence classification."""
        text = "The data shows statistics indicate 50 percent rate"

        evidence = self.service._classify_evidence(text)

        assert EvidenceType.STATISTICAL in evidence

    async def test_classify_evidence_expert(self) -> None:
        """Test expert evidence classification."""
        text = "According to experts specialists and academic research"

        evidence = self.service._classify_evidence(text)

        assert EvidenceType.AUTHORITY in evidence

    async def test_classify_evidence_historical(self) -> None:
        """Test historical evidence classification."""
        text = "Historically in the past traditionally as history shows"

        evidence = self.service._classify_evidence(text)

        assert EvidenceType.HISTORICAL in evidence

    async def test_classify_evidence_no_evidence(self) -> None:
        """Test evidence classification with no evidence types."""
        text = "This is a simple statement."

        evidence = self.service._classify_evidence(text)

        assert evidence == [EvidenceType.NONE]

    async def test_appraisal_score_positive(self) -> None:
        """Test positive appraisal attitude."""
        text = "This is good positive beneficial helpful"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.JUDGEMENT_POSITIVE

    async def test_appraisal_score_negative(self) -> None:
        """Test negative appraisal attitude."""
        text = "This is bad negative harmful dangerous"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.JUDGEMENT_NEGATIVE

    async def test_appraisal_score_neutral(self) -> None:
        """Test neutral appraisal attitude."""
        text = "This is neutral objective balanced impartial"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.NEUTRAL

    async def test_appraisal_score_mixed(self) -> None:
        """Test mixed appraisal attitude."""
        text = "This has good and bad aspects"

        appraisal = self.service._appraisal_score(text)

        assert appraisal == AppraisalAttitude.NEUTRAL

    async def test_detect_audience_international(self) -> None:
        """Test international audience detection."""
        text = "united nations international global foreign countries"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.GLOBAL_AUDIENCE

    async def test_detect_audience_domestic(self) -> None:
        """Test domestic audience detection."""
        text = "domestic national local internal citizens"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.DOMESTIC_AUDIENCE

    async def test_detect_audience_expert(self) -> None:
        """Test expert audience detection."""
        text = "expert technical professional specialized academic"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.INSTITUTIONAL_AUDIENCE

    async def test_detect_audience_general(self) -> None:
        """Test general audience detection."""
        text = "people public society masses everyone"

        audience = self.service._detect_audience(text)

        assert audience == AudienceType.GENERAL

    async def test_detect_audience_with_ner(self) -> None:
        """Test audience detection with NER entities."""
        mock_ner = Mock()
        mock_ner.extract_entities.return_value = {"GPE": ["syria", "turkey"]}

        service = FramingService(ner_service=mock_ner)
        text = "international community"

        audience = service._detect_audience(text)

        assert audience == AudienceType.GLOBAL_AUDIENCE
        mock_ner.extract_entities.assert_called_once_with(text)

    async def test_calculate_confidence_basic(self) -> None:
        """Test confidence calculation."""
        confidence = self.service._calculate_confidence(
            "test text", FrameType.CONFLICT_FRAME, [EvidenceType.STATISTICAL]
        )

        assert 0.0 <= confidence <= 1.0

    async def test_calculate_confidence_neutral_frame(self) -> None:
        """Test confidence calculation with neutral frame."""
        confidence = self.service._calculate_confidence(
            "test text", FrameType.NEUTRAL, [EvidenceType.STATISTICAL]
        )

        # Should be lower for neutral frame
        assert confidence < 0.7

    async def test_calculate_confidence_no_evidence(self) -> None:
        """Test confidence calculation with no evidence."""
        confidence = self.service._calculate_confidence(
            "short", FrameType.CONFLICT_FRAME, [EvidenceType.NONE]
        )

        # Should be lower for no evidence
        assert confidence < 0.8

    async def test_detect_frame_complete_analysis(self) -> None:
        """Test complete frame detection analysis."""
        text = "war conflict causes humanitarian crisis according to statistics"
        sentence = Sentence(id="1", text=text)
        sentence.dominant_topic = TopicCategory.UKRAYNA_RUSYA

        result = self.service.detect_frame(sentence)

        assert result is not None
        assert hasattr(result, "frame_type")
        assert hasattr(result, "evidence_types")
        assert hasattr(result, "appraisal_attitude")
        assert hasattr(result, "audience_type")
        assert hasattr(result, "confidence")

        assert result.frame_type == FrameType.CONFLICT_FRAME
        assert EvidenceType.STATISTICAL in result.evidence_types
        assert 0.0 <= result.confidence <= 1.0

    async def test_detect_frame_without_topic(self) -> None:
        """Test frame detection without explicit topic."""
        text = "united nations reform"
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type == FrameType.NEGOTIATION_FRAME
        assert result.confidence > 0.0

    async def test_detect_frame_mixed_signals(self) -> None:
        """Test frame detection with mixed signals."""
        text = "war conflict but also peace cooperation"
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type in [
            FrameType.CONFLICT_FRAME,
            FrameType.NEGOTIATION_FRAME,
            FrameType.NEUTRAL,
        ]

    async def test_edge_case_complex_diplomatic_text(self) -> None:
        """Test with complex diplomatic text."""
        text = (
            "The united nations security council reform is essential for "
            "peaceful resolution of the ukraine conflict through "
            "diplomatic negotiations"
        )
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type in [
            FrameType.NEGOTIATION_FRAME,
        ]
        assert result.confidence > 0.0

    async def test_edge_case_no_framing_signals(self) -> None:
        """Test with no framing signals."""
        text = "This is a simple statement."
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type == FrameType.NEUTRAL
        assert result.confidence < 0.7

    async def test_edge_case_very_long_text(self) -> None:
        """Test with very long text."""
        text = "conflict war " * 50
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert result.frame_type == FrameType.CONFLICT_FRAME
        assert result.confidence > 0.0

    async def test_case_insensitive_detection(self) -> None:
        """Test that frame detection is case insensitive."""
        text_lower = "war conflict"
        text_upper = "WAR CONFLICT"

        sentence_lower = Sentence(id="1", text=text_lower)
        sentence_upper = Sentence(id="1", text=text_upper)

        result_lower = self.service.detect_frame(sentence_lower)
        result_upper = self.service.detect_frame(sentence_upper)

        assert result_lower.frame_type == result_upper.frame_type

    async def test_multiple_evidence_types(self) -> None:
        """Test detection of multiple evidence types."""
        text = "According to experts, historical data and statistics show"
        sentence = Sentence(id="1", text=text)

        result = self.service.detect_frame(sentence)

        assert len(result.evidence_types) >= 2
        assert EvidenceType.AUTHORITY in result.evidence_types
        assert (
            EvidenceType.HISTORICAL in result.evidence_types
            or EvidenceType.STATISTICAL in result.evidence_types
        )


if __name__ == "__main__":
    pytest.main([__file__])
