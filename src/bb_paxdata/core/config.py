# ============================================================
# DOSYA: src/bb_paxdata/core/config.py
# AÇIKLAMA: Uygulama genelindeki merkezi konfigürasyon sabitleri
# ============================================================

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Uygulama ayarları — magic number'ların tek kaynağı (Single Source of Truth)."""

    # Dil Tespit Eşikleri
    TURKISH_CHAR_RATIO_THRESHOLD: float = (
        0.025  # %2.5 (Önceki 0.02 ve 0.03'ün ortak mantıklı kararı)
    )

    # Risk Hesaplama
    RISK_AI_WEIGHT: float = 0.6
    RISK_ANOMALY_WEIGHT: float = 0.4
    RISK_FALLBACK_ANOMALY_WEIGHT: float = 1.0  # AI devredışıyken anomali ağırlığı

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = AppSettings()
