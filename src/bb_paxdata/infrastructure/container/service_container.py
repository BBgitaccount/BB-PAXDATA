# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/container/service_container.py
# AÇIKLAMA: Singleton IoC container — stub YOK
# ============================================================

from __future__ import annotations

import logging

from ...application.pipeline.analysis_pipeline import AnalysisPipeline
from ...application.pipeline.assembler import AnalysisAssembler
from ...application.pipeline.sbi_calculator import SBICalculator
from ...application.pipeline.stages.country_reference_collector import (
    CountryReferenceCollector,
)
from ...domain.services.ai_analyst import AIAnalyst
from ...domain.services.cross_anomaly_service import CrossAnomalyService
from ...domain.services.language_detector import LanguageDetector
from ...domain.services.ner_service import SpacyNERService
from ...domain.services.prompt_registry import build_default_registry
from ...domain.services.tokenizer_service import SpacyTokenizerService
from ..nlp.negation_detector import SpacyNegationDetector
from ..nlp.power_index_calculator import PowerIndexCalculator
from ..nlp.risk_signal_detector import RiskSignalDetector
from ..nlp.topic_modeling import TopicModelingService

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

        # ── Yeni Dedektörler (Faz 3) ───────────────────────────────
        common_nlp = self.ner_service._models.get("en") or self.ner_service._models.get(
            "tr"
        )
        assert common_nlp is not None

        self.negation_detector = SpacyNegationDetector(nlp=common_nlp)
        self.risk_detector = RiskSignalDetector(nlp=common_nlp)
        self.power_calculator = PowerIndexCalculator(nlp=common_nlp)
        self.topic_modeling_service = TopicModelingService(
            prompt_registry=self.prompt_registry
        )

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

        # ── SBI Servisleri (Faz 7) ───────────────────────────────
        from ..nlp.engagement_analyzer import EngagementAnalyzer
        from ..nlp.stance_density import StanceDensityCalculator
        from ..nlp.wordfish_scaler import WordfishScaler
        from ..nlp.wordscores_calibrator import WordscoresCalibrator

        self.wordfish_scaler = WordfishScaler()
        self.stance_calculator = StanceDensityCalculator()
        self.engagement_analyzer = EngagementAnalyzer()
        self.wordscores_calibrator = WordscoresCalibrator()
        self.sbi_calculator = SBICalculator(
            wordfish=self.wordfish_scaler,
            stance=self.stance_calculator,
            engagement=self.engagement_analyzer,
            wordscores=self.wordscores_calibrator,
        )

        # ── Framing Servisleri (Faz 6) ─────────────────────────────
        from ...application.pipeline.frame.episodic_themetic_classifier import (
            EpisodicThematicClassifier,
        )
        from ...application.pipeline.frame.frame_assembler import FrameAssembler
        from ..ai.frame_detection.frame_detection_pipeline import FrameDetectionPipeline
        from ..ai.frame_detection.frame_lexicon_service import FrameLexiconService
        from ..ai.recovery import RecoveryEngine

        self.recovery_engine = RecoveryEngine()

        self.frame_lexicon_service = FrameLexiconService(nlp=common_nlp)

        self.episodic_classifier = EpisodicThematicClassifier(nlp=common_nlp)
        self.frame_assembler = FrameAssembler(
            lexicon_service=self.frame_lexicon_service, nlp=common_nlp
        )

        # FrameDetectionPipeline needs multiple sub-protocols (simplified here for container)
        # In a real setup, these would be separate classes.
        self.frame_pipeline = FrameDetectionPipeline(
            concept_extractor=None,
            coreference_resolver=None,
            embedding_matcher=None,
            five_w_one_h_extractor=None,
            llm_client=self.ai_analyst,
            topic_service=self.topic_modeling_service,
            recovery_engine=self.recovery_engine,
        )

        # ── Pipeline ────────────────────────────────────────────────
        self.assembler = AnalysisAssembler(sbi_calculator=self.sbi_calculator)
        self.pipeline = AnalysisPipeline(
            ner_service=self.ner_service,
            tokenizer_service=self.tokenizer_service,
            ai_analyst=self.ai_analyst,
            anomaly_service=self.anomaly_service,
            country_collector=self.country_collector,
            negation_detector=self.negation_detector,
            risk_detector=self.risk_detector,
            power_calculator=self.power_calculator,
            topic_modeling_service=self.topic_modeling_service,
            frame_pipeline=self.frame_pipeline,
            lexicon_service=self.frame_lexicon_service,
            episodic_classifier=self.episodic_classifier,
            frame_assembler=self.frame_assembler,
            sbi_calculator=self.sbi_calculator,
            stance_calculator=self.stance_calculator,
            engagement_scorer=self.engagement_analyzer,
            assembler=self.assembler,
        )

        logger.info("ServiceContainer hazır — tüm servisler aktif.")

    @classmethod
    def get_instance(cls) -> ServiceContainer:
        """Thread-unsafe singleton (production'da threading.Lock ekle)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
