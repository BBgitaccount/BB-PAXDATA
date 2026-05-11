"""Unit tests for CrossAnomalyService."""

from unittest.mock import Mock

import pytest
from bb_paxdata.domain.enums import AnomalySeverity, AnomalyType
from bb_paxdata.domain.services.cross_anomaly_service import CrossAnomalyService


class TestCrossAnomalyService:
    """Test cases for CrossAnomalyService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CrossAnomalyService()

    async def test_cross_anomaly_service_initialization(self):
        """Test that CrossAnomalyService initializes correctly."""
        assert self.service is not None
        assert self.service.confidence == 1.0

    async def test_anomaly_thresholds(self):
        """Test that anomaly thresholds are properly set."""
        assert self.service.ANOMALY_RISK_HIGH == 7
        assert self.service.ANOMALY_HEDGE_HIGH == 0.6
        assert self.service.ANOMALY_HEDGE_LOW == 0.2
        assert self.service.ANOMALY_MANIP_HIGH == 0.7
        assert self.service.ANOMALY_SENT_NEG == -0.5
        assert self.service.ANOMALY_SENT_POS == 0.3
        assert self.service.ANOMALY_POWER_HIGH == 8

    async def test_extract_ai_values(self):
        """Test AI values extraction."""
        analysis = Mock()
        analysis.ai_sentiment_score = -0.3
        analysis.ai_risk_score = 8.0
        analysis.ai_hedging_score = 0.7
        analysis.ai_manipulation_score = 0.8
        analysis.ai_politeness_score = 0.6
        analysis.ai_diplomatic_tone = "confrontational"
        analysis.ai_frame_type = "conflict"
        analysis.ai_appraisal_attitude = "negative"

        ai_values = self.service._extract_ai_values(analysis)

        assert ai_values["ai_sentiment"] == -0.3
        assert ai_values["ai_risk"] == 8.0
        assert ai_values["ai_hedging"] == 0.7
        assert ai_values["ai_manipulation"] == 0.8
        assert ai_values["ai_politeness"] == 0.6
        assert ai_values["ai_diplomatic_tone"] == "confrontational"

    async def test_extract_formula_values(self):
        """Test formula values extraction."""
        analysis = Mock()
        analysis.sentiment_score = -0.2
        analysis.risk_score = 7.5
        analysis.hedging_score = 0.6
        analysis.manipulation_score = 0.4
        analysis.speaker_power = 9
        analysis.sbi_score = 8.5
        analysis.dki_score = 0.3

        formula_values = self.service._extract_formula_values(analysis)

        assert formula_values["formula_sentiment"] == -0.2
        assert formula_values["formula_risk"] == 7.5
        assert formula_values["formula_hedging"] == 0.6
        assert formula_values["power_level"] == 9
        assert formula_values["sbi_score"] == 8.5

    async def test_detect_risk_hedging_conflict_high(self):
        """Test risk-hedging conflict detection with high values."""
        ai_values = {"ai_risk": 8.0}
        formula_values = {"formula_hedging": 0.7}

        anomalies = self.service._detect_risk_hedging_conflict(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.RISK_HEDGING_CONFLICT
        assert anomalies[0].severity == AnomalySeverity.HIGH
        assert "deception" in anomalies[0].description.lower()

    async def test_detect_risk_hedging_conflict_no_anomaly(self):
        """Test risk-hedging conflict with no anomaly."""
        ai_values = {"ai_risk": 3.0}
        formula_values = {"formula_hedging": 0.3}

        anomalies = self.service._detect_risk_hedging_conflict(
            ai_values, formula_values
        )

        assert len(anomalies) == 0

    async def test_detect_negative_confrontational_amplification(self):
        """Test negative confrontational amplification detection."""
        ai_values = {"ai_sentiment": -0.8, "ai_diplomatic_tone": "confrontational"}
        formula_values = {"power_level": 9}

        anomalies = self.service._detect_negative_confrontational_amplification(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.NEGATIVE_CONFRONTATIONAL_AMPLIFICATION
        assert anomalies[0].severity == AnomalySeverity.CRITICAL
        assert "high-power" in anomalies[0].description.lower()

    async def test_detect_velvet_glove_confrontation(self):
        """Test velvet glove confrontation detection."""
        ai_values = {"ai_politeness": 0.8, "ai_risk": 6.5}
        formula_values = {"formula_hedging": 0.1}

        anomalies = self.service._detect_velvet_glove_confrontation(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.VELVET_GLOVE_CONFRONTATION
        assert anomalies[0].severity == AnomalySeverity.MEDIUM
        assert "velvet glove" in anomalies[0].description.lower()

    async def test_detect_high_risk_conciliatory_mask(self):
        """Test high risk conciliatory mask detection."""
        ai_values = {"ai_risk": 8.0, "ai_diplomatic_tone": "conciliatory"}

        anomalies = self.service._detect_high_risk_conciliatory_mask(ai_values, {})

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.HIGH_RISK_CONCILIATORY_MASK
        assert anomalies[0].severity == AnomalySeverity.HIGH

    async def test_detect_direct_manipulation_low_hedge(self):
        """Test direct manipulation with low hedging detection."""
        ai_values = {"ai_manipulation": 0.8}
        formula_values = {"formula_hedging": 0.1}

        anomalies = self.service._detect_direct_manipulation_low_hedge(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.DIRECT_MANIPULATION_LOW_HEDGE
        assert anomalies[0].severity == AnomalySeverity.CRITICAL

    async def test_detect_dominant_actor_pressure(self):
        """Test dominant actor pressure detection."""
        ai_values = {"ai_risk": 6.5}
        formula_values = {"power_level": 9, "sbi_score": 8.0}

        anomalies = self.service._detect_dominant_actor_pressure(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.DOMINANT_ACTOR_PRESSURE
        assert anomalies[0].severity == AnomalySeverity.HIGH

    async def test_detect_vague_demand_plausible_deniability(self):
        """Test vague demand plausible deniability detection."""
        ai_values = {"ai_risk": 5.0}
        formula_values = {"formula_hedging": 0.7}

        anomalies = self.service._detect_vague_demand_plausible_deniability(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.VAGUE_DEMAND_PLAUSIBLE_DENIABILITY
        assert anomalies[0].severity == AnomalySeverity.MEDIUM

    async def test_detect_conflict_frame_positive_wrap(self):
        """Test conflict frame positive wrap detection."""
        ai_values = {"ai_frame": "conflict", "ai_sentiment": 0.5, "ai_risk": 6.5}

        anomalies = self.service._detect_conflict_frame_positive_wrap(ai_values, {})

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.CONFLICT_FRAME_POSITIVE_WRAP
        assert anomalies[0].severity == AnomalySeverity.MEDIUM

    async def test_detect_inconsistency_plus_manipulation(self):
        """Test inconsistency plus manipulation detection."""
        ai_values = {"ai_manipulation": 0.8}
        formula_values = {"formula_sentiment": 0.8}

        anomalies = self.service._detect_inconsistency_plus_manipulation(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.INCONSISTENCY_PLUS_MANIPULATION
        assert anomalies[0].severity == AnomalySeverity.HIGH

    async def test_detect_negative_appraisal_persuasive_tone(self):
        """Test negative appraisal persuasive tone detection."""
        ai_values = {
            "ai_appraisal": "negative",
            "ai_sentiment": -0.7,
            "ai_politeness": 0.7,
        }

        anomalies = self.service._detect_negative_appraisal_persuasive_tone(
            ai_values, {}
        )

        assert len(anomalies) == 1
        assert anomalies[0].type == AnomalyType.NEGATIVE_APPRAISAL_PERSUASIVE_TONE
        assert anomalies[0].severity == AnomalySeverity.MEDIUM

    async def test_detect_anomalies_comprehensive(self):
        """Test comprehensive anomaly detection."""
        # Create analysis with multiple anomalies
        analysis = Mock()
        analysis.ai_sentiment_score = -0.8
        analysis.ai_risk_score = 8.0
        analysis.ai_hedging_score = 0.7
        analysis.ai_manipulation_score = 0.8
        analysis.ai_politeness_score = 0.8
        analysis.ai_diplomatic_tone = "confrontational"
        analysis.ai_frame_type = "conflict"
        analysis.ai_appraisal_attitude = "negative"

        analysis.sentiment_score = 0.5
        analysis.risk_score = 7.5
        analysis.hedging_score = 0.1
        analysis.manipulation_score = 0.4
        analysis.speaker_power = 9
        analysis.sbi_score = 8.5
        analysis.dki_score = 0.3

        anomalies = self.service.detect_anomalies(analysis)

        # Should detect multiple anomalies
        assert len(anomalies) >= 2

        # Check that anomalies have required fields
        for anomaly in anomalies:
            assert hasattr(anomaly, "type")
            assert hasattr(anomaly, "severity")
            assert hasattr(anomaly, "category")
            assert hasattr(anomaly, "description")
            assert hasattr(anomaly, "ai_values")
            assert hasattr(anomaly, "formula_values")
            assert hasattr(anomaly, "confidence")

    async def test_detect_anomalies_no_anomalies(self):
        """Test anomaly detection with no anomalies."""
        # Create analysis with no anomalies
        analysis = Mock()
        analysis.ai_sentiment_score = 0.1
        analysis.ai_risk_score = 3.0
        analysis.ai_hedging_score = 0.3
        analysis.ai_manipulation_score = 0.2
        analysis.ai_politeness_score = 0.4
        analysis.ai_diplomatic_tone = "neutral"
        analysis.ai_frame_type = "neutral"
        analysis.ai_appraisal_attitude = "neutral"

        analysis.sentiment_score = 0.1
        analysis.risk_score = 3.0
        analysis.hedging_score = 0.3
        analysis.manipulation_score = 0.2
        analysis.speaker_power = 5
        analysis.sbi_score = 4.0
        analysis.dki_score = 0.1

        anomalies = self.service.detect_anomalies(analysis)

        # Should detect no anomalies
        assert len(anomalies) == 0

    async def test_edge_case_critical_anomaly_combination(self):
        """Test critical anomaly combination."""
        ai_values = {
            "ai_sentiment": -0.9,
            "ai_risk": 9.0,
            "ai_manipulation": 0.9,
            "ai_diplomatic_tone": "confrontational",
        }
        formula_values = {
            "formula_sentiment": 0.8,
            "power_level": 10,
            "formula_hedging": 0.1,
        }

        # Test multiple anomaly types
        anomalies = []
        anomalies.extend(
            self.service._detect_negative_confrontational_amplification(
                ai_values, formula_values
            )
        )
        anomalies.extend(
            self.service._detect_direct_manipulation_low_hedge(
                ai_values, formula_values
            )
        )
        anomalies.extend(
            self.service._detect_inconsistency_plus_manipulation(
                ai_values, formula_values
            )
        )

        # Should detect multiple critical anomalies
        critical_anomalies = [
            a for a in anomalies if a.severity == AnomalySeverity.CRITICAL
        ]
        assert len(critical_anomalies) >= 2

    async def test_anomaly_result_structure(self):
        """Test that anomaly results have correct structure."""
        ai_values = {"ai_risk": 8.0}
        formula_values = {"formula_hedging": 0.7}

        anomalies = self.service._detect_risk_hedging_conflict(
            ai_values, formula_values
        )

        assert len(anomalies) == 1
        anomaly = anomalies[0]

        assert isinstance(anomaly.type, AnomalyType)
        assert isinstance(anomaly.severity, AnomalySeverity)
        assert isinstance(anomaly.category, str)
        assert isinstance(anomaly.description, str)
        assert isinstance(anomaly.ai_values, dict)
        assert isinstance(anomaly.formula_values, dict)
        assert isinstance(anomaly.confidence, int | float)
        assert 0.0 <= anomaly.confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__])
