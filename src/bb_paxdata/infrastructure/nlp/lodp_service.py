from __future__ import annotations

import math
from collections import Counter
from typing import Final

from bb_paxdata.domain.models.lodp_result import LODPResult
from bb_paxdata.domain.models.segment import Segment


class LODPService:
    """Monroe (2009) Log Odds Ratio with Informative Dirichlet Prior.

    İki korpus arasındaki ayırt edici kelimeleri z-skoruyla çıkarır.
    Rare word overfitting'i Dirichlet prior (α) ile engeller.

    Reference:
        - Monroe, B.L., Colaresi, M.P. & Quinn, K.M. (2009).
          Fightin' Words: Lexical Feature Selection and Evaluation
          for Identifying the Content of Political Conflict.
    """

    DEFAULT_ALPHA: Final[float] = 0.01
    DEFAULT_TOP_K: Final[int] = 20

    def __init__(self, alpha: float = DEFAULT_ALPHA) -> None:
        self.alpha = alpha

    def _count_words(self, texts: list[str]) -> Counter[str]:
        """Metin listesinden kelime frekansları çıkarır."""
        counter: Counter[str] = Counter()
        for text in texts:
            # Basit temizleme ve tokenize (Faz 5'te spaCy ile güçlendirilecek)
            words = text.lower().split()
            counter.update(words)
        return counter

    def _compute_odds(self, count: int, total: int, alpha: float) -> float:
        """Dirichlet prior ile düzeltilmiş odds hesaplar."""
        # Dirichlet prior sayesinde count + alpha > 0
        # total - count + alpha > 0 (total >= count olduğu sürece)
        return (count + alpha) / (max(0, total - count) + alpha)

    def analyze(
        self,
        corpus1_texts: list[str],
        corpus2_texts: list[str],
        top_k: int = DEFAULT_TOP_K,
    ) -> list[LODPResult]:
        """İki korpus arasındaki ayırt edici kelimeleri LODP ile çıkarır.

        Args:
            corpus1_texts: Birinci korpus metinleri.
            corpus2_texts: İkinci korpus metinleri.
            top_k: Döndürülecek en yüksek z-skorlu kelime sayısı.

        Returns:
            list[LODPResult]: z_skor'a göre sıralanmış ayırt edici kelimeler.
        """
        counts1 = self._count_words(corpus1_texts)
        counts2 = self._count_words(corpus2_texts)

        total1 = sum(counts1.values())
        total2 = sum(counts2.values())

        # Tüm kelimelerin birleşim kümesi
        all_words = set(counts1.keys()) | set(counts2.keys())

        results: list[LODPResult] = []

        for word in all_words:
            c1 = counts1.get(word, 0)
            c2 = counts2.get(word, 0)

            # Dirichlet prior ile düzeltilmiş odds
            odds1 = self._compute_odds(c1, total1, self.alpha)
            odds2 = self._compute_odds(c2, total2, self.alpha)

            log_odds1 = math.log(odds1)
            log_odds2 = math.log(odds2)
            log_odds_diff = log_odds1 - log_odds2

            # Standart hata
            # Monroe (2009) SE formülü
            se = math.sqrt(
                1 / (c1 + self.alpha)
                + 1 / (c2 + self.alpha)
                + 1 / (max(0, total1 - c1) + self.alpha)
                + 1 / (max(0, total2 - c2) + self.alpha)
            )

            if se == 0:
                z_score = 0.0
            else:
                z_score = log_odds_diff / se

            results.append(
                LODPResult(
                    word=word,
                    z_score=round(z_score, 6),
                    log_odds_diff=round(log_odds_diff, 6),
                    corpus1_count=c1,
                    corpus2_count=c2,
                    se=round(se, 6),
                )
            )

        # z_skor'a göre mutlak değerde büyükten küçüğe sırala
        results.sort(key=lambda r: abs(r.z_score), reverse=True)
        return results[:top_k]

    async def analyze_segment_pair(
        self,
        segment1: Segment,
        segment2: Segment,
    ) -> list[LODPResult]:
        """İki segment arasındaki ayırt edici kelimeleri çıkarır.

        Bu metod, `AnalysisAssembler` tarafından `key_phrases`
        alanını zenginleştirmek için kullanılır.

        Args:
            segment1: Birinci segment.
            segment2: İkinci segment.

        Returns:
            list[LODPResult]: Ayırt edici kelimeler (z_skor sıralı).
        """
        # Segment text extraction logic
        # Segment modelinde 'text' alanı yokmuş gibi duruyor, 'sentences' birleştirilir.
        text1 = " ".join(s.text for s in segment1.sentences)
        text2 = " ".join(s.text for s in segment2.sentences)

        return self.analyze(
            corpus1_texts=[text1],
            corpus2_texts=[text2],
        )
