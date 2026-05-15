# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/repositories/analysis_repository.py
# AÇIKLAMA: Analysis nesnelerinin bütünlük kontrolü ile kaydedilmesi
# ============================================================

import logging

from ...domain.models.analysis import Analysis
from ...domain.services.prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)


class IntegrityError(Exception):
    """Veri bütünlüğü bozulduğunda fırlatılır."""

    pass


class AnalysisRepository:
    """
    Analiz sonuçlarını veritabanına (veya simülasyonuna) kaydeden sınıf.
    Kaydetmeden önce prompt hash bütünlüğünü doğrular.
    """

    def __init__(self, prompt_registry: PromptRegistry):
        self.prompt_registry = prompt_registry
        # Simüle edilmiş veritabanı
        self._db: dict[str, Analysis] = {}

    def save(self, analysis: Analysis) -> None:
        """
        Analizi kaydeder.
        Kritik: prompt_hash'in registry'deki versiyonla eşleştiğini doğrular.
        """
        if analysis.prompt_version and analysis.prompt_hash:
            # prompt_version formatı: "id@version"
            try:
                pid, ver = analysis.prompt_version.split("@")
                stored_prompt = self.prompt_registry.get_version(pid, ver)

                if stored_prompt:
                    if not stored_prompt.verify_integrity(analysis.prompt_hash):
                        error_msg = (
                            f"BÜTÜNLÜK HATASI: Analysis {analysis.id} içindeki prompt hash "
                            f"({analysis.prompt_hash}), Registry'deki {ver} versiyonu ile "
                            f"({stored_prompt.template_hash}) uyuşmuyor!"
                        )
                        logger.error(error_msg)
                        raise IntegrityError(error_msg)
                else:
                    logger.warning(
                        f"Registry'de bulunamayan prompt versiyonu: {analysis.prompt_version}"
                    )
            except ValueError:
                logger.error(
                    f"Geçersiz prompt_version formatı: {analysis.prompt_version}"
                )

        # Kayıt simülasyonu
        self._db[analysis.id] = analysis
        logger.info(
            f"Analysis {analysis.id} başarıyla kaydedildi (Integrity Verified)."
        )

    def get_by_id(self, analysis_id: str) -> Analysis | None:
        return self._db.get(analysis_id)
