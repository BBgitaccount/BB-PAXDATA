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
    # Conflict / Aggression (negative)
    "savaş": -0.6,
    "işgal": -0.7,
    "saldırganlık": -0.7,
    "agresyon": -0.6,
    "tehdit": -0.5,
    "baskı": -0.4,
    "şiddet": -0.6,
    "terör": -0.7,
    "provokasyon": -0.5,
    "kışkırtma": -0.5,
    "misilleme": -0.4,
    "yaptırım": -0.3,
    "ambargo": -0.4,
    "gerilim": -0.4,
    "çatışma": -0.5,
    "kınama": -0.4,
    "kınadı": -0.4,
    "kınıyoruz": -0.4,
    "reddediyoruz": -0.4,
    "kabul edilemez": -0.6,
    "endişe": -0.3,
    # Cooperation / Diplomacy (positive)
    "barış": 0.6,
    "diyalog": 0.4,
    "destek": 0.4,
    "dayanışma": 0.5,
    "işbirliği": 0.5,
    "uzlaşı": 0.4,
    "müzakere": 0.3,
    "anlaşma": 0.4,
    "antlaşma": 0.4,
    "ateşkes": 0.3,
    "çözüm": 0.3,
    "uzlaşma": 0.4,
    "saygı": 0.3,
    "güven": 0.3,
    "dostluk": 0.4,
    "ortaklık": 0.4,
    "ittifak": 0.3,
    "yardım": 0.4,
    "insancıl": 0.4,
    "insani": 0.3,
    "egemenlik": 0.2,
    "bütünlük": 0.3,
    "toprak bütünlüğü": 0.4,
    "bağımsızlık": 0.3,
    "özgürlük": 0.3,
    "adalet": 0.3,
    "hukuk": 0.2,
    "uluslararası hukuk": 0.3,
    "destekliyoruz": 0.4,
    "memnuniyetle": 0.3,
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
        # Verb endings that indicate negation (verb stems with -me/-ma suffix)
        # Listed as full common forms
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
    }
)
