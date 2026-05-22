from __future__ import annotations

import re

from bb_paxdata.domain.models.sentiment_result import LIWCScores

# LIWC2015 lexicon proxy — Türkçe/İngilizce diplomatik metinler için
# Faz 1'de basit keyword listeleri; Faz 5'te BERTopic ile zenginleştirilecek
LIWC_LEXICON: dict[str, list[str]] = {
    "clout": [
        # Otorite/iddia ifadeleri (TR)
        "emrediyoruz",
        "talimat",
        "şartsız",
        "kesinlikle",
        "mutlaka",
        "talep",
        "ısrar",
        "gerekiyor",
        "zorunlu",
        "hüküm",
        "yetki",
        "yetkili",
        # Otorite/iddia ifadeleri (EN)
        "unambiguously",
        "categorically",
        "unequivocally",
        "demand",
        "insist",
        "require",
        "command",
        "directive",
        "mandate",
        "authority",
        # Diplomatik otorite
        "büyükelçi",
        "devlet başkanı",
        "bakan",
        "ambassador",
        "president",
        "minister",
    ],
    "analytic": [
        # Nedensellik ve analiz (TR)
        "çünkü",
        "sonuç olarak",
        "bu nedenle",
        "analiz",
        "değerlendirme",
        "dolayısıyla",
        "incelenmiştir",
        "strateji",
        "politika",
        "sistem",
        # Nedensellik ve analiz (EN)
        "because",
        "therefore",
        "consequently",
        "analysis",
        "evaluate",
        "assessment",
        "review",
        "examine",
        "investigate",
        "study",
        "policy",
        "strategy",
        "framework",
        "mechanism",
        "system",
    ],
    "authenticity": [
        # Samimiyet ifadeleri (TR)
        "samimi",
        "dürüst",
        "açık",
        "gerçek",
        "içten",
        "doğru",
        # Samimiyet ifadeleri (EN)
        "sincere",
        "honest",
        "open",
        "genuine",
        "frank",
        "candid",
        "truthful",
        "transparent",
        "heartfelt",
    ],
    "tone_positive": [
        "olumlu",
        "yapıcı",
        "işbirliği",
        "uzlaşı",
        "barış",
        "destek",
        "positive",
        "constructive",
        "cooperation",
        "consensus",
        "peace",
        "support",
    ],
    "tone_negative": [
        "olumsuz",
        "yıkıcı",
        "çatışma",
        "kriz",
        "tehdit",
        "gerginlik",
        "negative",
        "destructive",
        "conflict",
        "crisis",
        "threat",
        "tension",
    ],
    # Bilişsel Durum Analizi Kategorileri (A2)
    "causal": [
        "because",
        "therefore",
        "consequently",
        "consequence",
        "thus",
        "hence",
        "since",
        "result",
        "effect",
        "cause",
        "çünkü",
        "dolayısıyla",
        "nedenle",
        "neden",
        "sonuç",
        "yüzden",
    ],
    "insight": [
        "think",
        "thought",
        "know",
        "knew",
        "known",
        "understand",
        "understood",
        "realize",
        "realized",
        "believe",
        "believed",
        "insight",
        "feel",
        "felt",
        "düşünmek",
        "düşünüyorum",
        "düşündü",
        "düşünce",
        "anlamak",
        "anlıyorum",
        "anladı",
        "bilmek",
        "biliyorum",
        "bildi",
        "fark etmek",
        "inanmak",
        "hissediyorum",
    ],
    "certainty": [
        "always",
        "never",
        "certainly",
        "absolutely",
        "sure",
        "definitely",
        "completely",
        "totally",
        "inevitably",
        "undeniably",
        "kesinlikle",
        "asla",
        "her zaman",
        "hiçbir zaman",
        "mutlaka",
        "şüphesiz",
        "tamamen",
    ],
    "tentative": [
        "maybe",
        "perhaps",
        "possibly",
        "possible",
        "guess",
        "tentative",
        "likely",
        "unlikely",
        "suggests",
        "claims",
        "belki",
        "herhalde",
        "sanırım",
        "muhtemelen",
        "olabilir",
        "iddia",
        "şüpheli",
    ],
}


class LIWCProxyResult:
    """Internal helper to hold matches before mapping to domain model."""

    def __init__(
        self,
        clout: float,
        analytic: float,
        authenticity: float,
        tone: float,
        word_count: int,
        category_hits: dict[str, int],
    ) -> None:
        self.clout = clout
        self.analytic = analytic
        self.authenticity = authenticity
        self.tone = tone
        self.word_count = word_count
        self.category_hits = category_hits


class LIWCProxyService:
    """LIWC2015 kategorilerinin lexicon-tabanlı proxy implementasyonu.

    Faz 1'de basit keyword matching; Faz 5'te BERT embedding tabanlı
    semantic matching ile değiştirilecektir.

    Reference:
        - Pennebaker, J.W. et al. (2015). LIWC2015.
        - ACADEMIC_FOUNDATIONS.md F5: clout, analytic skorları.
    """

    def __init__(self, lexicon: dict[str, list[str]] | None = None) -> None:
        self.lexicon = lexicon or LIWC_LEXICON
        # Regex pattern'leri ön-compile et (performans)
        self.patterns: dict[str, re.Pattern[str]] = {
            cat: re.compile(
                r"\b(?:" + "|".join(re.escape(word) for word in words) + r")\b",
                re.IGNORECASE,
            )
            for cat, words in self.lexicon.items()
        }

    def analyze(self, text: str) -> LIWCScores:
        """Metni LIWC kategorilerine göre analiz eder.

        Args:
            text: Analiz edilecek metin.

        Returns:
            LIWCScores: Kategori skorları (domain modeli).
        """
        word_count = len(re.findall(r"\w+", text))

        if word_count == 0:
            return LIWCScores(
                clout=0.0,
                analytic=0.0,
                authenticity=0.0,
                tone=0.0,
                word_count=0,
                cognitive_processing_score=0.0,
                causal_word_ratio=0.0,
                certainty_vs_tentative_ratio=0.0,
            )

        hits: dict[str, int] = {}
        for cat, pattern in self.patterns.items():
            matches = len(pattern.findall(text))
            hits[cat] = matches

        # Skorlar: kategori eşleşmesi / toplam kelime sayısı
        clout_score = hits.get("clout", 0) / word_count
        analytic_score = hits.get("analytic", 0) / word_count
        authenticity_score = hits.get("authenticity", 0) / word_count

        # Tone: (positive - negative) / total_tone_hits if > 0
        pos = hits.get("tone_positive", 0)
        neg = hits.get("tone_negative", 0)
        total_tone = pos + neg
        tone_score = (pos - neg) / total_tone if total_tone > 0 else 0.0

        # Bilişsel Durum Analizi skorları (A2)
        causal_hits = hits.get("causal", 0)
        insight_hits = hits.get("insight", 0)
        certainty_hits = hits.get("certainty", 0)
        tentative_hits = hits.get("tentative", 0)

        cognitive_processing_score = (causal_hits + insight_hits) / word_count
        causal_word_ratio = causal_hits / word_count
        certainty_vs_tentative_ratio = certainty_hits / (tentative_hits + 1e-6)

        return LIWCScores(
            clout=round(min(clout_score, 1.0), 6),
            analytic=round(min(analytic_score, 1.0), 6),
            authenticity=round(min(authenticity_score, 1.0), 6),
            tone=round(max(-1.0, min(tone_score, 1.0)), 6),
            word_count=word_count,
            cognitive_processing_score=round(cognitive_processing_score, 6),
            causal_word_ratio=round(causal_word_ratio, 6),
            certainty_vs_tentative_ratio=round(certainty_vs_tentative_ratio, 6),
        )
