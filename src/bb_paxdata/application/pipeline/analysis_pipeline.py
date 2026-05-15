# ============================================================
# DOSYA: src/bb_paxdata/application/pipeline/analysis_pipeline.py
# AÇIKLAMA: 4 aşamalı end-to-end pipeline
# ============================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ...domain.exceptions import MissingAIOutputException
from ...domain.models.ai_analysis import AIAnalysisResult
from ...domain.models.analysis import Analysis
from ...domain.services.language_detector import LanguageDetector
from ...domain.services.protocols import (
    AIAnalystProtocol,
    AnomalyServiceProtocol,
    NERServiceProtocol,
    TokenizerProtocol,
)
from .assembler import AnalysisAssembler

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """
    Pipeline çıktı zarfı.
    Hem nihai Analysis modelini hem ham servis verilerini taşır.
    Ham veriler debug ve audit amacıyla korunur.
    """

    analysis: Analysis
    raw_ner: dict[str, Any] = field(default_factory=dict)
    raw_tokenizer: dict[str, Any] = field(default_factory=dict)
    raw_ai: AIAnalysisResult | None = None
    success: bool = True
    errors: list[str] = field(default_factory=list)
    stage: str = "completed"  # Hata durumunda hangi aşamada kaldığı


class AnalysisPipeline:
    """
    Diplomatik metin analizi için uçtan uca 4 aşamalı pipeline.

    Aşamalar:
    1. COLLECT  — Her alt-servis bağımsız çalışır, ham veri/model üretir
    2. ASSEMBLE — AnalysisAssembler ile Analysis modeline dönüştürülür
    3. DETECT   — CrossAnomalyService ile anomali tespiti; model_copy ile güncellenir
    4. FINALIZE — PipelineResult zarfı oluşturulur

    Tasarım kararları:
    - Hiçbir aşama Analysis nesnesini doğrudan mutate etmez (immutable data flow)
    - Birden fazla aşama hatası tolere edilir (graceful degradation)
    - AI çıktısı eksikse MissingAIOutputException loglanır ama pipeline durdurmaz
    """

    def __init__(
        self,
        ner_service: NERServiceProtocol,
        tokenizer_service: TokenizerProtocol,
        ai_analyst: AIAnalystProtocol,
        anomaly_service: AnomalyServiceProtocol,
        language_detector: LanguageDetector | None = None,
        assembler: AnalysisAssembler | None = None,
        fail_fast_on_missing_ai: bool = False,
    ):
        self.ner_service = ner_service
        self.tokenizer_service = tokenizer_service
        self.ai_analyst = ai_analyst
        self.anomaly_service = anomaly_service
        self.language_detector = language_detector or LanguageDetector()
        self.assembler = assembler or AnalysisAssembler()
        # True ise AI çıktısı eksik olduğunda pipeline exception fırlatır
        self.fail_fast_on_missing_ai = fail_fast_on_missing_ai

    def run(self, text: str, metadata: dict[str, Any] | None = None) -> PipelineResult:
        """Metni uçtan uca analiz eder. Tüm hatalar PipelineResult.errors'a eklenir."""
        errors: list[str] = []
        raw_ner: dict[str, Any] = {}
        raw_tokenizer: dict[str, Any] = {}
        raw_ai: AIAnalysisResult | None = None

        # ─────────────────────────────────────────
        # AŞAMA 0: PRE-PROCESS (Centralized Language Detection)
        # ─────────────────────────────────────────
        detected_language = self.language_detector.detect(text)
        logger.info(
            f"Pipeline başladı: Dil='{detected_language}', Metin Uzunluğu={len(text)}"
        )

        # ─────────────────────────────────────────
        # AŞAMA 1: COLLECT
        # ─────────────────────────────────────────
        try:
            raw_ner = self.ner_service.extract(text, language=detected_language)
            logger.debug(f"NER tamamlandı: {len(raw_ner.get('entities', []))} varlık")
        except Exception as e:
            errors.append(f"[COLLECT/NER] {e}")
            logger.warning(f"NER servisi başarısız: {e}")

        try:
            raw_tokenizer = self.tokenizer_service.tokenize(
                text, language=detected_language
            )
            logger.debug(
                f"Tokenizer tamamlandı: {len(raw_tokenizer.get('tokens', []))} token"
            )
        except Exception as e:
            errors.append(f"[COLLECT/TOKENIZER] {e}")
            logger.warning(f"Tokenizer servisi başarısız: {e}")

        try:
            raw_ai = self.ai_analyst.analyze(text, language=detected_language)
            logger.debug(
                f"AI analizi tamamlandı: "
                f"sentiment={raw_ai.sentiment_score}, "
                f"risk={raw_ai.risk_score}, "
                f"version={raw_ai.prompt_version}"
            )
        except Exception as e:
            errors.append(f"[COLLECT/AI] {e}")
            logger.error(f"AI Analyst başarısız: {e}")
            # AI çıktısı pipeline için kritik; boş sonuç placeholder'ı oluştur
            from ...domain.models.ai_analysis import AIAnalysisResult

            raw_ai = AIAnalysisResult(prompt_version="unknown@error", error=str(e))

        # ─────────────────────────────────────────
        # AŞAMA 2: ASSEMBLE
        # ─────────────────────────────────────────
        try:
            analysis = self.assembler.assemble(
                source_text=text,
                language=detected_language,
                ner_result=raw_ner,
                tokenizer_result=raw_tokenizer,
                ai_result=raw_ai,
                metadata=metadata,
            )
        except Exception as e:
            errors.append(f"[ASSEMBLE] {e}")
            logger.error(f"Assembly başarısız: {e}")
            # Assembly kritik hata — kısmi PipelineResult döndür
            return PipelineResult(
                analysis=Analysis(source_text=text),
                raw_ner=raw_ner,
                raw_tokenizer=raw_tokenizer,
                raw_ai=raw_ai,
                success=False,
                errors=errors,
                stage="assemble",
            )

        # ─────────────────────────────────────────
        # AŞAMA 3: DETECT (Immutable update)
        # ─────────────────────────────────────────
        try:
            if self.fail_fast_on_missing_ai and not analysis.has_ai_output:
                raise MissingAIOutputException(
                    analysis_id=analysis.id,
                    missing_fields=["ai_sentiment_score", "ai_risk_score"],
                )

            anomaly_result = self.anomaly_service.detect(analysis)

            # IMMUTABLE: model_copy ile yeni Analysis nesnesi üretilir, mevcut mutate edilmez
            analysis = analysis.model_copy(
                update={
                    "anomaly_score": anomaly_result.score,
                    "anomaly_flags": anomaly_result.flags,
                    "risk_level": anomaly_result.risk_level,
                }
            )
            logger.info(
                f"Anomali tespiti tamamlandı: "
                f"id={analysis.id}, "
                f"score={analysis.anomaly_score}, "
                f"risk_level={analysis.risk_level}"
            )
        except MissingAIOutputException as e:
            errors.append(f"[DETECT/MISSING_AI] {e}")
            logger.error(str(e))
        except Exception as e:
            errors.append(f"[DETECT] {e}")
            logger.error(f"Anomali servisi başarısız: {e}")

        # ─────────────────────────────────────────
        # AŞAMA 4: FINALIZE
        # ─────────────────────────────────────────
        return PipelineResult(
            analysis=analysis,
            raw_ner=raw_ner,
            raw_tokenizer=raw_tokenizer,
            raw_ai=raw_ai,
            success=len(errors) == 0,
            errors=errors,
            stage="completed" if len(errors) == 0 else "completed_with_errors",
        )

    def analyze_sentence(
        self, text: str, metadata: dict[str, Any] | None = None
    ) -> PipelineResult:
        """Geriye uyumlu alias — dış API contract'ı bozulmaz."""
        return self.run(text, metadata)
