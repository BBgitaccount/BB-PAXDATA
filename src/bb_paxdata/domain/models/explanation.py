"""
Domain models for Explainability and XAI (Explainable AI) in BB-PAXDATA.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TokenContribution(BaseModel):
    """
    Contribution of a specific token to the overall sentiment or risk score.
    """

    token: str
    sentiment_contrib: float
    risk_contrib: float
    explanation: str


class SentenceExplanation(BaseModel):
    """
    Comprehensive explanation for a sentence's analysis results.
    """

    sent_id: str
    generated_at: datetime = Field(default_factory=datetime.now)

    # Layered explanations
    risk_explanation: str
    sentiment_explanation: str
    anomaly_explanation: str | None = None
    grammatical_explanation: str | None = None
    discrepancy_explanation: str | None = None

    # Summary for reporting
    executive_summary: str

    # Token-level attribution (optional)
    token_attributions: list[TokenContribution] | None = None
