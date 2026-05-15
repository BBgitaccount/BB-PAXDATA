# ============================================================
# DOSYA: src/bb_paxdata/domain/models/ai_analysis.py
# AÇIKLAMA: AIAnalyst servisinin dönüş tipi — Pydantic DTO
# ============================================================


from pydantic import BaseModel, Field


class AIAnalysisResult(BaseModel):
    """
    AIAnalyst.analyze() metodunun dönüş tipi.
    Ham dict yerine Pydantic modeli kullanılır → tip güvenliği + validasyon.
    """

    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    sentiment_label: str | None = None
    risk_factors: list[str] = Field(default_factory=list)
    summary: str | None = None
    key_claims: list[str] = Field(default_factory=list)
    raw_output: str | None = Field(default=None, description="Ham AI metin yanıtı")

    # Audit trail alanları — AnalysisAssembler tarafından Analysis modeline aktarılır
    prompt_version: str = Field(description="prompt_id@version formatı")
    prompt_hash: str | None = Field(
        default=None, description="SHA256 hash (ilk 16 karakter)"
    )
    model_name: str = Field(default="", description="Kullanılan AI modeli")

    # Hata durumunda doldurulur
    error: str | None = None
    parse_error: str | None = None
