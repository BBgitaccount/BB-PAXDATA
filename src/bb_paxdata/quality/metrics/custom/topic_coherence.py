# src/bb_paxdata/quality/metrics/custom/topic_coherence.py

import numpy as np
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class MetricResult(BaseModel):
    score: float
    threshold: float
    passed: bool
    reason: str = ""


class TopicCoherenceEvaluator:
    """NPMI (Normalized Pointwise Mutual Information) tabanlı konu tutarlılığı ölçer.

    Referans: Bouma, G. (2009). Normalized Word Co-occurrence and Complementary Measures.
    """

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def measure(
        self, topic_keywords: dict[str, float], corpus: list[str]
    ) -> MetricResult:
        """Konu kelimeleri arasındaki NPMI skorunu hesaplar.

        Args:
            topic_keywords: {word: c-tfidf_score}
            corpus: Tokenize edilmiş doküman listesi
        """
        words = list(topic_keywords.keys())[:10]
        if len(words) < 2:
            return MetricResult(
                score=1.0,
                threshold=self.threshold,
                passed=True,
                reason="Too few words to measure coherence",
            )

        npmi_scores = []
        n_docs = len(corpus)

        # Kelime doküman matrisi (basit)
        word_presence: dict[str, set[int]] = {w: set() for w in words}
        for i, doc in enumerate(corpus):
            doc_words = set(doc.lower().split())
            for w in words:
                if w in doc_words:
                    word_presence[w].add(i)

        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                w1, w2 = words[i], words[j]
                p_w1 = len(word_presence[w1]) / n_docs
                p_w2 = len(word_presence[w2]) / n_docs
                p_w1_w2 = len(word_presence[w1] & word_presence[w2]) / n_docs

                if p_w1_w2 > 0:
                    # PMI = log(P(w1,w2) / (P(w1)*P(w2)))
                    pmi = np.log(p_w1_w2 / (p_w1 * p_w2))
                    # NPMI = PMI / -log(P(w1,w2))
                    denom = -np.log(p_w1_w2)
                    npmi = pmi / denom if denom != 0 else 1.0
                    npmi_scores.append(npmi)
                else:
                    npmi_scores.append(-1.0)  # Hiç birlikte geçmiyorlarsa en düşük skor

        avg_npmi = float(np.mean(npmi_scores)) if npmi_scores else 0.0
        # NPMI [-1, 1] aralığındadır. [0, 1] aralığına normalize edelim (opsiyonel ama threshold için iyi olur)
        normalized_score = (avg_npmi + 1) / 2

        return MetricResult(
            score=normalized_score,
            threshold=self.threshold,
            passed=normalized_score >= self.threshold,
            reason=f"Average NPMI: {avg_npmi:.4f}",
        )
