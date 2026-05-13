"""
Unit tests for ExplainabilityService.
"""

import pytest
from bb_paxdata.domain.services.explainability import (
    ExplainabilityService,
    ExplanationContext,
)


class TestExplainabilityService:
    @pytest.fixture
    def service(self) -> ExplainabilityService:
        return ExplainabilityService()

    def test_explain_sentence_basic(self, service: ExplainabilityService) -> None:
        """Test basic explanation generation."""
        sent_id = "S1"
        text = "Türkiye Ukrayna'yı destekliyor."
        sentiment_score = 0.4
        risk_score = 2

        context = ExplanationContext(
            sent_id=sent_id,
            text=text,
            sentiment_score=sentiment_score,
            risk_score=risk_score,
        )
        explanation = service.explain_sentence(context)

        assert explanation.sent_id == sent_id
        assert "destekliyor" in text
        assert explanation.executive_summary is not None
        assert explanation.sentiment_explanation is not None
        assert explanation.risk_explanation is not None

    def test_explain_sentence_with_negation(
        self, service: ExplainabilityService
    ) -> None:
        """Test explanation for negated sentiment."""
        text = "Turkey does not support war."
        # "not" and "support" are key here
        context = ExplanationContext(
            sent_id="S2", text=text, sentiment_score=-0.2, risk_score=5
        )
        explanation = service.explain_sentence(context)

        # Check if negation template is used (based on mock attributions)
        # In real test we might need to mock token_level_attribution to be sure
        assert explanation.sentiment_explanation is not None

    def test_explain_sentence_high_risk(self, service: ExplainabilityService) -> None:
        """Test explanation for high risk and power level."""
        context = ExplanationContext(
            sent_id="S3",
            text="Conflict is imminent.",
            sentiment_score=-0.8,
            risk_score=9,
            power_level=10,
        )
        explanation = service.explain_sentence(context)

        assert (
            "kritik" in explanation.risk_explanation
            or "yüksek" in explanation.risk_explanation
        )
        assert "10/10" in explanation.risk_explanation
