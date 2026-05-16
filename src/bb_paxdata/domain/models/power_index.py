from pydantic import BaseModel, ConfigDict, Field


class PowerIndex(BaseModel):
    """Konuşmacının söylemsel güç indeksi (Van Dijk 1993 CDA).

    PowerIndex(speaker) = α·AuthorityMarkers + β·DominancePatterns + γ·LegitimationStrategies
    """

    model_config = ConfigDict(frozen=True, strict=True)

    speaker_id: str = Field(..., description="Konuşmacı kimliği")
    segment_id: str = Field(..., description="Ait olduğu segment UUID")

    # Van Dijk (1993) üç boyutu
    authority_markers: float = Field(
        default=0.0, ge=0.0, description="Otorite işaretçisi yoğunluğu"
    )
    dominance_patterns: float = Field(
        default=0.0, ge=0.0, description="Baskı örüntüsü yoğunluğu"
    )
    legitimation_strategies: float = Field(
        default=0.0, ge=0.0, description="Meşrulaştırma stratejisi yoğunluğu"
    )

    # Ağırlıklar (ampirik kalibre edilecek; toplam = 1.0)
    alpha: float = Field(default=0.4, ge=0.0, le=1.0, description="Authority ağırlığı")
    beta: float = Field(default=0.35, ge=0.0, le=1.0, description="Dominance ağırlığı")
    gamma: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Legitimation ağırlığı"
    )

    @property
    def total_power_index(self) -> float:
        """Bileşik güç indeksi (Van Dijk 1993)."""
        return (
            self.alpha * self.authority_markers
            + self.beta * self.dominance_patterns
            + self.gamma * self.legitimation_strategies
        )

    # Normalized (z-score benzeri, 0-1 arası)
    normalized_score: float | None = Field(default=None, ge=0.0, le=1.0)
