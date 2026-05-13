from __future__ import annotations

"""
Templates for Rule-based Explainability in BB-PAXDATA.
"""

TEMPLATES: dict[str, str] = {
    "risk_high_power": (
        "Güçlü aktör ({power}/10) tarafından iletilen '{signal}' ifadesi, "
        "diplomatik denge açısından {severity} kabul edilir."
    ),
    "sentiment_negation": (
        "'{keyword}' kelimesi olumsuz anlam taşır, ancak '{negation}' "
        "ile birlikte kullanıldığı için polarite tersine çevrilmiştir "
        "(skor: {score})."
    ),
    "anomaly_risk_hedge": (
        "Yüksek risk ({risk}/10) ile yüksek belirsizlik ({hedge:.2f}) "
        "bir arada. Bu, 'plausible deniability' (makul reddedilebilirlik) "
        "stratejisinin işareti olabilir."
    ),
    "discrepancy_sentiment": (
        "AI duygu skoru ({ai:.2f}) ile formül skoru ({formula:.2f}) "
        "arasında {diff:.2f} fark var. AI bağlamsal yumuşatıcıları "
        "göz önünde bulundururken, formül sözcük-bazlı hesaplama yapıyor."
    ),
    "dependency_actor_action": (
        "{subject} → {verb} → {object} yapısı tespit edildi. "
        "Bu, {subject}'in {object} üzerinde aktif bir diplomatik "
        "eylemde bulunduğunu gösterir."
    ),
    "risk_signal_formula": ("Formül tabanlı risk sinyalleri tespit edildi: {signals}."),
    "power_level_impact": (
        "Konuşmacı güç seviyesi yüksek ({power}/10), bu durum diplomatik risk "
        "algısını yükseltir."
    ),
    "self_referential_action": (
        "Konuşmacı ({speaker}) özne ve nesne olarak aynı aktörü ({actor}) kullanıyor. "
        "Bu, stratejik bir özeleştiri veya anlatım bozukluğu olabilir."
    ),
    "lexicon_match": (
        "'{token}' kelimesi diplomatik sözlükte {score} puanlık bir "
        "'{category}' katkısı sağlar."
    ),
}
