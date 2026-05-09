from enum import Enum


class TopicCategory(str, Enum):
    BM_REFORUMU = "BM_Reformu"
    GUVENLIK_CATISMA = "Güvenlik_Çatışma"
    EKONOMI_TICARET_ENERJI = "Ekonomi_Ticaret_Enerji"
    LIDERLIK_YONETIM = "Liderlik_Yönetim"
    DIPLOMATIK_COZUM = "Diplomatik_Çözüm"
    AB_NATO_GENISLEME = "AB_NATO_Genişleme"
    YAPAY_ZEKA_TEKNOLOJI = "Yapay_Zeka_Teknoloji"
    ORTA_GUCLER_BOLGESEL = "Orta_Güçler_Bölgesel"
    GAZZE_FILISTIN_ISRAIL = "Gazze_Filistin_İsrail"
    UKRAYNA_RUSYA = "Ukrayna_Rusya"
    SURIYE_GECIS = "Suriye_Geçiş"
    AFRIKA_ORTADOGU = "Afrika_Ortadoğu"
    INSANI_YARDIM_HAKLAR = "İnsani_Yardım_Haklar"
    COK_KUTUPLULUK_DUZEN = "Çok_Kutupluluk_Düzen"
    RISK_KIRILIM = "Risk_Kırılım"
