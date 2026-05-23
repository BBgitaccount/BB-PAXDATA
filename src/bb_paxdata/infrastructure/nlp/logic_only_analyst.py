# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/nlp/logic_only_analyst.py
# AÇIKLAMA: Yapay zeka çağrısı yapmadan NLP tabanlı analiz servisi.
#           AIAnalystProtocol'u tam olarak uygular.
#           Build, watch ve analyze komutlarında --logic-only bayrağı
#           ile aktive edilir.
# ============================================================

from __future__ import annotations

import logging
import re

from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult

logger = logging.getLogger(__name__)

# ── Diplomatik Duygu Sözlükleri ───────────────────────────────────────────────

_POSITIVE_KEYWORDS: frozenset[str] = frozenset(
    {
        # English
        "cooperation",
        "partnership",
        "peace",
        "dialogue",
        "agreement",
        "solidarity",
        "unity",
        "progress",
        "support",
        "collaborate",
        "opportunity",
        "constructive",
        "stability",
        "prosperity",
        "achieve",
        "success",
        "hope",
        "benefit",
        "mutual",
        "respect",
        "trust",
        "diplomatic",
        "resolve",
        "inclusive",
        "reform",
        "development",
        # Turkish
        "işbirliği",
        "barış",
        "diyalog",
        "anlaşma",
        "dayanışma",
        "birlik",
        "ilerleme",
        "destek",
        "fırsat",
        "yapıcı",
        "istikrar",
        "refah",
        "başarı",
        "umut",
        "kazanım",
        "karşılıklı",
        "saygı",
        "güven",
        "çözüm",
        "kalkınma",
        "gelişme",
        "müzakere",
        "uzlaşı",
        "uzlaşma",
    }
)

_NEGATIVE_KEYWORDS: frozenset[str] = frozenset(
    {
        # English
        "war",
        "conflict",
        "tension",
        "crisis",
        "threat",
        "sanction",
        "aggression",
        "violation",
        "attack",
        "confrontation",
        "hostile",
        "unacceptable",
        "condemn",
        "reject",
        "oppose",
        "failure",
        "collapse",
        "destabilize",
        "escalation",
        "occupation",
        "genocide",
        "illegal",
        "veto",
        # Turkish
        "savaş",
        "çatışma",
        "gerilim",
        "kriz",
        "tehdit",
        "yaptırım",
        "saldırganlık",
        "ihlal",
        "saldırı",
        "düşmanca",
        "kabul edilemez",
        "kınamak",
        "reddetmek",
        "başarısız",
        "çöküş",
        "istikrarsızlaştırma",
        "tırmanma",
        "işgal",
        "soykırım",
        "yasa dışı",
        "veto",
        "terör",
        "terörizm",
    }
)

_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        # English
        "war",
        "military",
        "attack",
        "nuclear",
        "weapon",
        "blockade",
        "genocide",
        "occupation",
        "hostage",
        "ceasefire",
        "escalation",
        "sanction",
        "threat",
        "chemical",
        "biological",
        # Turkish
        "savaş",
        "askeri",
        "saldırı",
        "nükleer",
        "silah",
        "abluka",
        "soykırım",
        "işgal",
        "rehine",
        "ateşkes",
        "tırmanma",
        "yaptırım",
        "tehdit",
        "kimyasal",
        "biyolojik",
        "bomba",
        "bombalama",
    }
)

_NEGATION_WORDS: frozenset[str] = frozenset(
    {
        "not",
        "no",
        "never",
        "cannot",
        "don't",
        "doesn't",
        "didn't",
        "won't",
        "wouldn't",
        "değil",
        "yok",
        "hayır",
        "asla",
    }
)


def _tokenize(text: str) -> list[str]:
    """Minimal tokenizer: lowercase, split on non-alphanumeric."""
    return re.findall(r"\b\w+\b", text.lower())


def _compute_sentiment(tokens: list[str]) -> tuple[float, str]:
    """
    Kural tabanlı duygu skoru hesaplar.
    Returns: (compound_score [-1, 1], label)
    """
    pos_hits = 0
    neg_hits = 0
    negation_active = False

    for i, token in enumerate(tokens):
        if token in _NEGATION_WORDS:
            negation_active = True
            continue

        in_positive = token in _POSITIVE_KEYWORDS
        in_negative = token in _NEGATIVE_KEYWORDS

        if negation_active:
            # Negation flips valence
            if in_positive:
                neg_hits += 1
            elif in_negative:
                pos_hits += 1
            negation_active = False
        else:
            if in_positive:
                pos_hits += 1
            if in_negative:
                neg_hits += 1

        # Negation window: 3 tokens max
        if negation_active and (i - tokens.index(token)) > 3:
            negation_active = False

    total = pos_hits + neg_hits
    if total == 0:
        return 0.0, "neutral"

    # Normalize to [-1, 1]
    score = (pos_hits - neg_hits) / total
    score = max(-1.0, min(1.0, score))

    if score > 0.05:
        label = "positive"
    elif score < -0.05:
        label = "negative"
    else:
        label = "neutral"

    return round(score, 4), label


def _compute_risk(tokens: list[str]) -> tuple[float, list[str]]:
    """
    Kural tabanlı risk skoru hesaplar.
    Returns: (risk_score [0, 1], triggered_factors)
    """
    triggered = [t for t in tokens if t in _RISK_KEYWORDS]
    # Unique risk words / saturation at 5
    unique_risks = list(set(triggered))
    score = min(1.0, len(unique_risks) / 5.0)
    return round(score, 4), unique_risks


def _extract_summary(text: str, max_chars: int = 200) -> str:
    """İlk anlamlı cümleyi özet olarak döner."""
    # Cümle sonlandırıcılara göre böl
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if sentences:
        return sentences[0][:max_chars]
    return text[:max_chars]


class LogicOnlyAIAnalyst:
    """
    Yapay zeka (LLM) çağrısı yapmayan, tamamen kural tabanlı analiz servisi.

    AIAnalystProtocol'u tam olarak uygular → ServiceContainer'da
    gerçek AIAnalyst'in yerini alabilir.

    Kullanım:
        container = ServiceContainer(logic_mode=True)
        pipeline = container.pipeline  # LLM çağrısı olmayacak
    """

    PROMPT_VERSION = "logic_only@1.0"
    MODEL_NAME = "rule_based_nlp"

    async def analyze(
        self,
        text: str,
        prompt_id: str | None = None,
        forced_version: str | None = None,
        language: str | None = None,
    ) -> AIAnalysisResult:
        """
        Metin üzerinde kural tabanlı analiz çalıştırır.
        LLM çağrısı YAPILMAZ — tamamen deterministik.
        """
        tokens = _tokenize(text)
        sentiment_score, sentiment_label = _compute_sentiment(tokens)
        risk_score, risk_factors = _compute_risk(tokens)
        summary = _extract_summary(text)

        logger.debug(
            "LogicOnlyAIAnalyst: analiz tamamlandı "
            f"sentiment={sentiment_score} risk={risk_score}"
        )

        return AIAnalysisResult(
            sentiment_score=sentiment_score,
            risk_score=risk_score,
            sentiment_label=sentiment_label,
            risk_factors=risk_factors,
            summary=summary,
            key_claims=[],
            prompt_version=self.PROMPT_VERSION,
            prompt_hash=None,
            model_name=self.MODEL_NAME,
        )
