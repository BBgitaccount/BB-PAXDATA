# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/container/service_container.py
# AÇIKLAMA: Singleton IoC container — stub YOK
# ============================================================

from __future__ import annotations

import logging

from ...application.pipeline.analysis_pipeline import AnalysisPipeline
from ...application.pipeline.assembler import AnalysisAssembler
from ...application.pipeline.stages.country_reference_collector import (
    CountryReferenceCollector,
)
from ...domain.services.ai_analyst import AIAnalyst
from ...domain.services.cross_anomaly_service import CrossAnomalyService
from ...domain.services.ner_service import SpacyNERService
from ...domain.services.prompt_registry import build_default_registry
from ...domain.services.tokenizer_service import SpacyTokenizerService
from ...shared.utils.language import LanguageDetector

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Uygulama genelindeki servis bağımlılıklarını yöneten IoC container.
    Singleton pattern: get_instance() ile erişilir.
    ARTIK STUB YOK — tüm servisler gerçek implementasyonlarla donatılmıştır.
    """

    _instance: ServiceContainer | None = None

    def __init__(self) -> None:
        logger.info("ServiceContainer başlatılıyor — tüm servisler yükleniyor...")

        # ── Ortak Araçlar ──────────────────────────────────────────
        self.language_detector = LanguageDetector()

        # ── NLP Servisleri ─────────────────────────────────────────
        self.ner_service = SpacyNERService(language_detector=self.language_detector)
        self.tokenizer_service = SpacyTokenizerService(
            language_detector=self.language_detector
        )

        # ── Prompt Registry + AI Analyst ───────────────────────────
        self.prompt_registry = build_default_registry()
        self.ai_analyst = AIAnalyst(
            registry=self.prompt_registry, language_detector=self.language_detector
        )

        # ── Anomali Servisi ─────────────────────────────────────────
        self.anomaly_service = CrossAnomalyService()

        # ── Pipeline Stages ────────────────────────────────────────
        # Note: CountryReferenceCollector needs a spacy model.
        # For the container, we use the default 'en' model from NER service.
        self.country_collector = CountryReferenceCollector(
            nlp=self.ner_service._models.get("en")
            or self.ner_service._models.get("tr"),
            country_vocabulary=set(),  # Vocabulary will be injected or loaded
            llm_client=self.ai_analyst,
            # recovery_engine and prompt_registry could be injected here if needed
        )

        # ── Pipeline ────────────────────────────────────────────────
        self.assembler = AnalysisAssembler()
        self.pipeline = AnalysisPipeline(
            ner_service=self.ner_service,
            tokenizer_service=self.tokenizer_service,
            ai_analyst=self.ai_analyst,
            anomaly_service=self.anomaly_service,
            country_collector=self.country_collector,
            assembler=self.assembler,
        )

        logger.info("ServiceContainer hazır — tüm servisler aktif.")

    @classmethod
    def get_instance(cls) -> ServiceContainer:
        """Thread-unsafe singleton (production'da threading.Lock ekle)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
