# ============================================================
# DOSYA: src/bb_paxdata/domain/exceptions.py
# AÇIKLAMA: Pipeline özel istisnaları
# ============================================================


class MissingAIOutputException(Exception):
    """AI servisinden beklenen çıktı gelmediğinde fırlatılır."""

    def __init__(self, analysis_id: str, missing_fields: list[str]):
        self.analysis_id = analysis_id
        self.missing_fields = missing_fields
        super().__init__(
            f"Analysis ID={analysis_id} için AI çıktısı eksik: {missing_fields}"
        )


class PipelineStageException(Exception):
    """Pipeline'ın belirli bir aşamasında oluşan hata."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"[{stage.upper()}] {message}")
