"""Unit tests for RiskService."""

from unittest.mock import Mock

import pytest
from bb_paxdata.domain.enums import RiskLevel
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.services.risk_service import RiskService


class TestRiskService:
    """Test cases for RiskService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = RiskService()

    async def test_risk_service_initialization(self) -> None:
        """Test that RiskService initializes correctly."""
        assert self.service is not None
        assert self.service.confidence == 1.0
        assert self.service._ner_service is None

    async def test_risk_service_with_ner(self) -> None:
        """Test RiskService initialization with NER service."""
        mock_ner = Mock()
        service = RiskService(ner_service=mock_ner)
        assert service._ner_service is mock_ner

    async def test_compute_sbi_formula(self) -> None:
        """Test SBI calculation formula."""
        power_level = 10.0
        demand_weight = 0.8
        risk_score = 5.0

        expected_sbi = (10.0 * 0.8) / 2.0 + 5.0  # 4.0 + 5.0 = 9.0
        actual_sbi = self.service.compute_sbi(power_level, demand_weight, risk_score)

        assert actual_sbi == expected_sbi

    async def test_compute_sbi_edge_cases(self) -> None:
        """Test SBI calculation with edge cases."""
        # Test with minimum values
        sbi = self.service.compute_sbi(0.0, 0.0, 0.0)
        assert sbi == 0.0

        # Test with maximum values
        sbi = self.service.compute_sbi(10.0, 1.0, 10.0)
        assert sbi == 15.0  # (10 * 1) / 2 + 10

    async def test_compute_dki_formula(self) -> None:
        """Test DKI calculation formula."""
        norm_diplo = 0.7
        norm_risk = 0.3
        norm_demand = 0.6
        norm_manip = 0.4

        expected_dki = (
            0.7 * 0.4 + (1 - 0.3) * 0.3 + 0.6 * 0.2 + (1 - 0.4) * 0.1
        ) * 2 - 1
        actual_dki = self.service.compute_dki(
            norm_diplo, norm_risk, norm_demand, norm_manip
        )

        assert abs(actual_dki - expected_dki) < 0.001

    async def test_compute_dki_edge_cases(self) -> None:
        """Test DKI calculation with edge cases."""
        # Test with all zeros
        dki = self.service.compute_dki(0.0, 0.0, 0.0, 0.0)
        expected = (0.0 * 0.4 + 1.0 * 0.3 + 0.0 * 0.2 + 1.0 * 0.1) * 2 - 1
        assert dki == expected

        # Test with all ones
        dki = self.service.compute_dki(1.0, 1.0, 1.0, 1.0)
        expected = (1.0 * 0.4 + 0.0 * 0.3 + 1.0 * 0.2 + 0.0 * 0.1) * 2 - 1
        assert dki == expected

    async def test_contextual_risk_basic(self) -> None:
        """Test basic contextual risk calculation."""
        text = "This is unacceptable and we will retaliate."

        risk_score = self.service.contextual_risk(text)

        assert risk_score > 0.0
        assert risk_score <= 10.0

    async def test_contextual_risk_with_entities(self) -> None:
        """Test contextual risk with NER entities."""
        text = "Syria conflict escalation unacceptable"
        entities = {"GPE": ["syria"], "ORG": ["military"]}

        risk_score = self.service.contextual_risk(text, entities)

        assert risk_score > 0.0
        assert risk_score <= 10.0

    async def test_contextual_risk_with_ner_service(self) -> None:
        """Test contextual risk using NER service."""
        mock_ner = Mock()
        mock_ner.extract_entities.return_value = {"GPE": ["Syria"]}

        service = RiskService(ner_service=mock_ner)
        # Must include a risk signal so base_score > 0 → multiplier applies
        text = "The situation in Syria is unacceptable"

        risk_score = service.contextual_risk(text)

        assert risk_score > 0.0
        mock_ner.extract_entities.assert_called_once_with(text)

    async def test_risk_detect_basic(self) -> None:
        """Test basic risk detection."""
        text = "This is unacceptable and we will retaliate with military action."

        risk_score, signals = self.service.risk_detect(text)

        assert risk_score > 0.0
        assert len(signals) > 0
        assert "unacceptable" in [s.lower() for s in signals]
        assert risk_score <= 10.0

    async def test_risk_detect_no_signals(self) -> None:
        """Test risk detection with no risk signals."""
        text = "We had a productive meeting yesterday."

        risk_score, signals = self.service.risk_detect(text)

        assert risk_score == 0.0
        assert len(signals) == 0

    async def test_risk_detect_multiple_signals(self) -> None:
        """Test risk detection with multiple signals."""
        text = "This is unacceptable red line. We will retaliate and escalate."

        risk_score, signals = self.service.risk_detect(text)

        assert risk_score > 0.0
        assert len(signals) >= 2
        assert risk_score <= 10.0

    async def test_normalize_value(self) -> None:
        """Test value normalization."""
        # Test normal case
        normalized = self.service._normalize_value(5.0, 0.0, 10.0)
        assert normalized == 0.5

        # Test edge cases
        assert self.service._normalize_value(0.0, 0.0, 10.0) == 0.0
        assert self.service._normalize_value(10.0, 0.0, 10.0) == 1.0

        # Test out of range
        assert self.service._normalize_value(-5.0, 0.0, 10.0) == 0.0
        assert self.service._normalize_value(15.0, 0.0, 10.0) == 1.0

    async def test_classify_risk_severity(self) -> None:
        """Test risk severity classification."""
        assert self.service._classify_risk_severity(9.0) == RiskLevel.CRITICAL
        assert self.service._classify_risk_severity(7.0) == RiskLevel.CRITICAL
        assert self.service._classify_risk_severity(5.0) == RiskLevel.HIGH
        assert self.service._classify_risk_severity(3.0) == RiskLevel.MEDIUM
        assert self.service._classify_risk_severity(1.0) == RiskLevel.LOW

    async def test_assess_risk_single_sentence(self) -> None:
        """Test risk assessment with single sentence."""
        sentence = Sentence(id="1", text="This is unacceptable and we will retaliate.")
        segment = Segment(id="seg1", sentences=[sentence])

        result = self.service.assess_risk(segment)

        assert result is not None
        assert hasattr(result, "sbi_score")
        assert hasattr(result, "dki_score")
        assert hasattr(result, "risk_score")
        assert hasattr(result, "risk_signals")
        assert hasattr(result, "severity")
        assert hasattr(result, "confidence")

        assert result.risk_score > 0.0
        assert len(result.risk_signals) > 0
        assert result.severity in RiskLevel
        assert 0.0 <= result.confidence <= 1.0

    async def test_assess_risk_multiple_sentences(self) -> None:
        """Test risk assessment with multiple sentences."""
        sentences = [
            Sentence(id="1", text="We must cooperate."),
            Sentence(id="2", text="This is unacceptable red line."),
            Sentence(id="3", text="We will retaliate if necessary."),
        ]
        segment = Segment(id="seg1", sentences=sentences)

        result = self.service.assess_risk(segment)

        assert result is not None
        assert result.risk_score > 0.0  # Should be elevated due to risk signals
        assert len(result.risk_signals) > 0

    async def test_assess_risk_with_speaker_power(self) -> None:
        """Test risk assessment considering speaker power."""
        sentence = Sentence(id="1", text="This is unacceptable.")
        segment = Segment(id="seg1", sentences=[sentence])

        # Mock speaker with high power
        mock_speaker = Mock()
        mock_speaker.power_level = 9
        segment.speaker = mock_speaker

        result = self.service.assess_risk(segment)

        assert result.sbi_score > 0.0  # High power should increase SBI

    async def test_assess_risk_empty_segment(self) -> None:
        """Test risk assessment with empty segment."""
        segment = Segment(id="seg1", sentences=[])

        result = self.service.assess_risk(segment)

        assert result is not None
        assert result.risk_score < 0.1
        assert len(result.risk_signals) == 0
        assert result.severity == RiskLevel.LOW

    async def test_risk_signals_coverage(self) -> None:
        """Test that risk signals list is comprehensive."""
        signals = self.service.RISK_SIGNALS

        # Check for key risk indicators
        assert "unacceptable" in signals
        assert "red line" in signals
        assert "escalate" in signals
        assert "retaliate" in signals
        assert "military option" in signals

    async def test_risk_severity_mapping(self) -> None:
        """Test risk severity mapping."""
        mapping = self.service.RISK_SEVERITY

        assert "low" in mapping
        assert "medium" in mapping
        assert "high" in mapping
        assert "critical" in mapping

        assert mapping["low"] == RiskLevel.LOW
        assert mapping["critical"] == RiskLevel.CRITICAL

    async def test_edge_case_very_risky_text(self) -> None:
        """Test with very risky text."""
        text = (
            "UNACCEPTABLE RED LINE! We will retaliate with military action "
            "and escalate to nuclear conflict!"
        )
        sentence = Sentence(id="1", text=text)
        segment = Segment(id="seg1", sentences=[sentence])

        result = self.service.assess_risk(segment)

        assert result.risk_score >= 6.5
        assert result.severity in [
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]

    async def test_edge_case_no_risk_text(self) -> None:
        """Test with no risk text."""
        text = (
            "We had a productive discussion about cooperation and mutual understanding."
        )
        sentence = Sentence(id="1", text=text)
        segment = Segment(id="seg1", sentences=[sentence])

        result = self.service.assess_risk(segment)

        assert result.risk_score < 3.0
        assert result.severity in [RiskLevel.LOW, RiskLevel.MEDIUM]

    async def test_confidence_calculation(self) -> None:
        """Test confidence calculation based on signals."""
        text = "unacceptable"  # Single signal
        sentence = Sentence(id="1", text=text)
        segment = Segment(id="seg1", sentences=[sentence])

        result = self.service.assess_risk(segment)

        # Should have some confidence based on signal count
        assert result.confidence >= 0.2


if __name__ == "__main__":
    pytest.main([__file__])
