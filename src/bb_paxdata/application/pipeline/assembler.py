# ============================================================
# DOSYA: src/bb_paxdata/application/pipeline/assembler.py
# AÇIKLAMA: Ham servis çıktılarını Analysis modeline dönüştüren assembler
# ============================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ...domain.models.ai_analysis import AIAnalysisResult
from ...domain.models.analysis import Analysis

logger = logging.getLogger(__name__)


class AnalysisAssembler:
    """
    TEK SORUMLULUK: Alt-servis dict çıktılarını + AIAnalysisResult'ı
    doğrulanmış bir Analysis (Pydantic) nesnesine dönüştürmek.

    Dict → Analysis dönüşümü YA burada YA da doğrudan modelde olmalı.
    Pipeline sınıfı bu dönüşüm mantığını içermemelidir.
    """

    @staticmethod
    def assemble(
        source_text: str,
        language: str,
        ner_result: dict[str, Any],
        tokenizer_result: dict[str, Any],
        ai_result: AIAnalysisResult,
        metadata: dict[str, Any] | None = None,
    ) -> Analysis:
        """
        Tüm alt-servis çıktılarını birleştirip doğrulanmış Analysis üretir.

        Args:
            source_text    : Orijinal metin
            language       : Önceden tespit edilmiş dil
            ner_result     : {"entities": [...]}
            tokenizer_result: {"tokens": [...], "sentences": [...], "sentence_count": 2}
            ai_result      : AIAnalysisResult Pydantic modeli (tip güvenli)
            metadata       : {"id": "...", "timestamp": "..."} gibi ek bilgiler

        Returns:
            Doğrulanmış Analysis nesnesi
        """
        metadata = metadata or {}

        analysis = Analysis(
            id=metadata.get("id", f"anal-{uuid.uuid4().hex[:8]}"),
            source_text=source_text,
            language=language,
            timestamp=metadata.get("timestamp", datetime.now(timezone.utc).isoformat()),
            # ── NLP Alanları ──
            entities=ner_result.get("entities", []),
            tokens=tokenizer_result.get("tokens", []),
            sentences=tokenizer_result.get("sentences", []),
            sentence_count=tokenizer_result.get("sentence_count", 0),
            # ── AI Alanları (AIAnalysisResult'tan güvenli aktarım) ──
            ai_sentiment_score=ai_result.sentiment_score,
            ai_risk_score=ai_result.risk_score,
            ai_sentiment_label=ai_result.sentiment_label,
            ai_risk_factors=ai_result.risk_factors,
            ai_summary=ai_result.summary,
            ai_key_claims=ai_result.key_claims,
            # ── Prompt Audit Trail ──
            prompt_version=ai_result.prompt_version,
            prompt_hash=ai_result.prompt_hash,
            model_name=ai_result.model_name,
        )

        logger.debug(
            f"Assembly tamamlandı: id={analysis.id}, "
            f"language={analysis.language}, "
            f"has_ai_output={analysis.has_ai_output}, "
            f"prompt_version={analysis.prompt_version}"
        )
        return analysis
