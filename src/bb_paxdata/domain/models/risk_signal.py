from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.domain.enums.signal_type import SignalType


class RiskSignal(BaseModel):
    """Diplomatik metindeki risk sinyalinin domain modeli.

    Zagare (2004) escalation theory + Trager (2010) costly signaling.
    Immutable.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    signal_text: str = Field(..., min_length=1, description="Sinyal ifadesi metni")
    signal_start: int = Field(..., ge=0, description="Başlangıç karakter indeksi")
    signal_end: int = Field(..., ge=0, description="Bitiş karakter indeksi")

    signal_type: SignalType = Field(..., description="Trager/Zagare sınıflandırması")

    # Zagare (2004) escalation multiplier
    escalation_multiplier: float = Field(
        default=1.0,
        ge=1.0,
        le=2.0,
        description="Zagare tırmanış çarpanı: 1.0 (base), 1.5 (red_line), 2.0 (retaliation)",
    )

    # Trager (2010) credibility
    credibility_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sinyal güvenilirliği (power_level × commitment_cost proxy)",
    )

    sentence_id: str = Field(..., description="Ait olduğu sentence UUID")

    @property
    def weighted_risk_contribution(self) -> float:
        """Bu sinyalin risk skoruna katkısı: multiplier × credibility."""
        return self.escalation_multiplier * self.credibility_score
