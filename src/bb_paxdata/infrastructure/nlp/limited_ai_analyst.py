# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/nlp/limited_ai_analyst.py
# AÇIKLAMA: AI Analyst wrapper — cümle bazlı limit.
#           İlk N CÜMLE'de tüm AI işlemleri gerçek AI'a gider,
#           N+1'den itibaren tüm AI işlemleri LogicOnly'ye düşer.
#           Token/maliyet kontrolü için kullanılır.
#
# Mimari:
#   ServiceContainer tüm AI-bağımlı servislere (frame pipeline,
#   anomaly controller, country collector vb.) AYNI LimitedAIAnalyst
#   nesnesini enjekte eder. begin_sentence() çağrıldığında sayaç
#   artar. Limiti aşan cümlelerde, o cümle boyunca yapılan TÜM
#   analyze() çağrıları LogicOnly'ye düşer.
# ============================================================

from __future__ import annotations

import logging
import threading
from typing import Any

from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.infrastructure.nlp.logic_only_analyst import LogicOnlyAIAnalyst

logger = logging.getLogger(__name__)


class LimitedAIAnalyst:
    """
    Cümle bazlı AI limiti uygulayan wrapper.

    Pipeline her cümle için birden fazla AI çağrısı yapar (duygu analizi,
    frame detection, anomali doğrulama vb.). Bu wrapper **cümle** bazında
    sayar — ``begin_sentence()`` çağrıldığında sayaç artar.

    İlk ``limit`` cümle için tüm ``analyze()`` çağrıları gerçek AI'a gider.
    Limiti aşan cümlelerde tüm ``analyze()`` çağrıları LogicOnly'ye düşer.

    Kullanım (build loop)::

        limited = LimitedAIAnalyst(delegate=real_ai, limit=50)

        for sentence in sentences:
            limited.begin_sentence()       # cümle sayacını artır
            result = await pipeline.run()  # tüm AI servisleri aynı nesneyi kullanır

    Thread-safe: asyncio gather ile paralel çağrılarda da doğru davranır.
    """

    def __init__(
        self,
        delegate: Any,
        limit: int,
        *,
        fallback: LogicOnlyAIAnalyst | None = None,
    ) -> None:
        """
        Args:
            delegate: Gerçek AIAnalystProtocol implementasyonu (AIAnalyst vb.)
            limit: Maksimum AI destekli CÜMLE sayısı. 0 → hiç AI yok.
            fallback: Limit aşılınca kullanılacak analyst. None ise otomatik oluşturulur.
        """
        if limit < 0:
            raise ValueError(f"limit negatif olamaz: {limit}")

        self._delegate = delegate
        self._limit = limit
        self._fallback = fallback or LogicOnlyAIAnalyst()

        # Cümle sayacı (begin_sentence ile artırılır)
        self._sentence_count = 0
        # O anki cümle AI mı yoksa logic-only mi?
        self._current_sentence_uses_ai = False
        # İstatistik: toplam analyze() çağrısı (AI + LogicOnly)
        self._total_analyze_calls = 0
        self._ai_analyze_calls = 0
        self._logic_analyze_calls = 0
        self._lock = threading.Lock()

    # ── Cümle Yaşam Döngüsü ────────────────────────────────────────

    def begin_sentence(self) -> None:
        """
        Her cümle işlenmeden önce çağrılır.
        Cümle sayacını artırır ve o cümlenin AI mı yoksa logic-only mı
        olacağına karar verir.

        Build loop'unda ``pipeline.run()``'dan önce çağrılmalıdır.
        """
        with self._lock:
            self._sentence_count += 1
            if self._sentence_count <= self._limit:
                self._current_sentence_uses_ai = True
            else:
                self._current_sentence_uses_ai = False

            current = self._sentence_count

        if current == 1:
            logger.info(
                f"LimitedAIAnalyst: AI analizi basliyor (limit={self._limit} cumle)"
            )

        if current == self._limit:
            logger.warning(
                f"LimitedAIAnalyst: AI limiti doldu ({self._limit} cumle). "
                "Sonraki cumleler LogicOnly ile analiz edilecek."
            )

        if current % 25 == 0:
            logger.info(
                f"LimitedAIAnalyst: {current} cumle islendi "
                f"(AI: {min(current, self._limit)}, LogicOnly: {max(0, current - self._limit)})"
            )

    # ── Propertyler ────────────────────────────────────────────────

    @property
    def sentence_count(self) -> int:
        """Şu ana kadar işlenen cümle sayısı."""
        return self._sentence_count

    @property
    def remaining(self) -> int:
        """Kalan AI destekli cümle hakkı."""
        return max(0, self._limit - self._sentence_count)

    @property
    def limit(self) -> int:
        """Toplam AI destekli cümle limiti."""
        return self._limit

    @property
    def is_exhausted(self) -> bool:
        """Limit aşıldı mı?"""
        return self._sentence_count >= self._limit

    # ── AIAnalystProtocol uygulaması ───────────────────────────────

    async def analyze(
        self,
        text: str,
        prompt_id: str | None = None,
        forced_version: str | None = None,
        language: str | None = None,
    ) -> AIAnalysisResult:
        """
        AI analizi çağırır.

        Hangi backend'e yönlendirileceği ``begin_sentence()`` ile
        belirlenen cümle durumuna bağlıdır:

        - Cümle limiti dahilinde → delegate (gerçek AI) — tüm AI servisleri çalışır
        - Cümle limiti aşıldı   → LogicOnlyAIAnalyst — sıfır maliyet
        """
        with self._lock:
            self._total_analyze_calls += 1
            use_ai = self._current_sentence_uses_ai

        if use_ai:
            with self._lock:
                self._ai_analyze_calls += 1

            result = await self._delegate.analyze(
                text,
                prompt_id=prompt_id,
                forced_version=forced_version,
                language=language,
            )
            return result
        else:
            with self._lock:
                self._logic_analyze_calls += 1

            result = await self._fallback.analyze(
                text,
                prompt_id=prompt_id,
                forced_version=forced_version,
                language=language,
            )
            return result

    # ── Raporlama ──────────────────────────────────────────────────

    def get_usage_summary(self) -> dict[str, int | bool]:
        """Kullanım özetini döner (CLI raporlama için)."""
        return {
            "sentences_processed": self._sentence_count,
            "ai_sentence_limit": self._limit,
            "ai_sentences_used": min(self._sentence_count, self._limit),
            "logic_only_sentences": max(0, self._sentence_count - self._limit),
            "remaining_ai_sentences": self.remaining,
            "is_exhausted": self.is_exhausted,
            "total_analyze_calls": self._total_analyze_calls,
            "ai_analyze_calls": self._ai_analyze_calls,
            "logic_analyze_calls": self._logic_analyze_calls,
            # Compatibility keys for build.py
            "ai_calls_made": min(self._sentence_count, self._limit),
            "ai_limit": self._limit,
            "remaining": self.remaining,
        }
