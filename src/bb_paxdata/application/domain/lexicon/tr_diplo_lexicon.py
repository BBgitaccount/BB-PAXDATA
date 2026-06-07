"""
Turkish diplomatic lexicon for BB-PAXDATA.

Provides:
- DIPLO_LEXICON_TR: Sentiment scores for Turkish diplomatic vocabulary
- NEGATION_WORDS_TR: Turkish negation markers

Scoring convention (same as English DIPLO_LEXICON):
    Positive values → cooperative/constructive diplomatic tone
    Negative values → confrontational/aggressive diplomatic tone
    Range: [-1.0, 1.0]

Note:
    This lexicon covers ~50 high-priority Turkish diplomatic terms.
    Scores are aligned with the English DIPLO_LEXICON via manual
    review of diplomatic usage. Machine translation was used as a
    starting point; all scores were validated for diplomatic context.
"""

# ---------------------------------------------------------------------------
# Turkish Diplomatic Sentiment Lexicon
# ---------------------------------------------------------------------------

DIPLO_LEXICON_TR: dict[str, float] = {
    # Extreme Negative (-0.7 to -0.9)
    "soykırım": -0.8,
    "katliam": -0.8,
    "savaş suçu": -0.7,
    "insanlık suçu": -0.8,
    "terör": -0.7,
    "terörizm": -0.7,
    "işgal": -0.7,
    "saldırganlık": -0.7,
    "kabul edilemez": -0.6,
    "şiddetle kınıyoruz": -0.6,
    # Strong Negative (-0.5 to -0.6)
    "savaş": -0.6,
    "şiddet": -0.6,
    "agresyon": -0.6,
    "egemenlik ihlali": -0.6,
    "toprak ihlali": -0.6,
    "güç kullanma tehdidi": -0.6,
    "ilhak": -0.5,
    "yasa dışı ilhak": -0.6,
    "provokasyon": -0.5,
    "kışkırtma": -0.5,
    "provokatif eylemler": -0.5,
    "düşmanlık": -0.5,
    "düşmanlıklar": -0.5,
    "vekalet savaşı": -0.5,
    "vekalet çatışması": -0.5,
    "sınır ihlali": -0.5,
    "siber savaş": -0.5,
    "abluka": -0.5,
    "çatışma": -0.5,
    "tehdit": -0.5,
    # Mid Negative (-0.3 to -0.4)
    "baskı": -0.4,
    "misilleme": -0.4,
    "ambargo": -0.4,
    "gerilim": -0.4,
    "kınama": -0.4,
    "kınadı": -0.4,
    "kınıyoruz": -0.4,
    "reddediyoruz": -0.4,
    "kabul etmiyoruz": -0.4,
    "çift standart": -0.4,
    "dezenformasyon": -0.4,
    "siber saldırı": -0.4,
    "askeri yığınak": -0.4,
    "tek taraflı eylemler": -0.4,
    "kriz": -0.4,
    "yaptırım": -0.3,
    "boykot": -0.3,
    "gerginlik": -0.3,
    "haksızlık": -0.3,
    "derin endişe": -0.3,
    "endişe": -0.3,
    # Low Negative (-0.1 to -0.2)
    "kaygı": -0.2,
    "belirsizlik": -0.2,
    "güvensizlik": -0.2,
    "bağımlılık": -0.2,
    "tek taraflı": -0.2,
    # Extreme Positive (+0.6 to +0.8)
    "barış": 0.6,
    "kapsamlı barış": 0.7,
    "adil barış": 0.6,
    "barışçıl birliktelik": 0.6,
    "küresel dayanışma": 0.6,
    # Strong Positive (+0.4 to +0.5)
    "stratejik ortaklık": 0.5,
    "dayanışma": 0.5,
    "işbirliği": 0.5,
    "barışçıl çözüm": 0.5,
    "refah": 0.5,
    "ortak sorumluluk": 0.5,
    "diyalog": 0.4,
    "destek": 0.4,
    "uzlaşı": 0.4,
    "anlaşma": 0.4,
    "antlaşma": 0.4,
    "uzlaşma": 0.4,
    "ortaklık": 0.4,
    "yardım": 0.4,
    "insancıl": 0.4,
    "toprak bütünlüğü": 0.4,
    "destekliyoruz": 0.4,
    "arabuluculuk": 0.4,
    "arabulucu": 0.4,
    "karşılıklı saygı": 0.4,
    "güven artırıcı önlemler": 0.4,
    "güven artırıcı": 0.4,
    "güvenlik garantileri": 0.4,
    "yapıcı diyalog": 0.4,
    "silahsızlanma": 0.4,
    "normalleşme": 0.4,
    "insani yardım": 0.4,
    # Mid Positive (+0.2 to +0.3)
    "müzakere": 0.3,
    "ateşkes": 0.3,
    "çözüm": 0.3,
    "saygı": 0.3,
    "güven": 0.3,
    "dostluk": 0.3,
    "ittifak": 0.3,
    "insani": 0.3,
    "bütünlük": 0.3,
    "bağımsızlık": 0.3,
    "özgürlük": 0.3,
    "adalet": 0.3,
    "uluslararası hukuk": 0.3,
    "memnuniyetle": 0.3,
    "diplomatik çaba": 0.3,
    "diplomatik ilişkiler": 0.3,
    "gerilimi düşürmek": 0.3,
    "gerilimin azaltılması": 0.3,
    "iyi niyet": 0.3,
    "insani koridor": 0.3,
    "uzlaşı arayışı": 0.3,
    "istikrar": 0.3,
    "sürdürülebilir çözüm": 0.3,
    "sürdürülebilir kalkınma": 0.3,
    "ortak bildiri": 0.3,
    "mutabakat zaptı": 0.3,
    "çok taraflılık": 0.3,
    "kolaylaştırıcı": 0.3,
    "egemen eşitlik": 0.3,
    "egemenlik": 0.2,
    "hukuk": 0.2,
    "ikili ilişkiler": 0.2,
    "yapıcı katılım": 0.2,
    # Low Positive (+0.1)
    "geçiş": 0.1,
    "diyalog arayışı": 0.1,
    "temas": 0.1,
}

# ---------------------------------------------------------------------------
# Turkish Negation Words
# ---------------------------------------------------------------------------

NEGATION_WORDS_TR: frozenset[str] = frozenset(
    {
        # Standalone negation words
        "değil",
        "hayır",
        "yok",
        "hiç",
        "hiçbir",
        "asla",
        "olmadan",
        "olmaz",
        "yetersiz",
        "eksik",
        # Verb endings that indicate negation (verb stems with -me/-ma suffix)
        "istemiyoruz",
        "istemiyorum",
        "istemiyor",
        "kabul etmiyoruz",
        "kabul etmiyor",
        "desteklemiyoruz",
        "desteklemiyor",
        "onaylamıyoruz",
        "tanımıyoruz",
        "reddediyoruz",
        "karşıyız",
        "karşı çıkıyoruz",
        "uygun değildir",
        "mümkün değildir",
        "izin vermeyeceğiz",
        "izin vermeyiz",
        "asla kabul edilemez",
        "müsaade etmeyeceğiz",
        "müsaade etmeyiz",
    }
)
