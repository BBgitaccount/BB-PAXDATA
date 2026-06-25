from enum import StrEnum


class FailCategory(StrEnum):
    NEGASYON_TUZAGI = "negasyon_tuzagi"
    BAGLAMSAL_KAYMA = "baglamsal_kayma"
    SOZCUK_CIFT_ANLAMLILIGI = "sozcuk_cift_anlamliligi"
    TON_AYRIMI = "ton_ayrimi"
    TEMPORAL_DRIFT = "temporal_drift"
    ANOMALI_KAYNAKLI = "anomali_kaynakli"
    DIGER = "diger"
