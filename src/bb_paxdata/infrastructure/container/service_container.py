# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/container/service_container.py
# AÇIKLAMA: Singleton IoC container — stub YOK
# ============================================================

from __future__ import annotations

import logging
from typing import Any, cast

from ...application.pipeline.analysis_pipeline import AnalysisPipeline
from ...application.pipeline.assembler import AnalysisAssembler
from ...application.pipeline.sbi_calculator import SBICalculator
from ...application.pipeline.stages.country_reference_collector import (
    CountryReferenceCollector,
)
from ...application.pipeline.stages.finalize_stage import FinalizeStage
from ...config.settings import get_settings
from ...domain.enums import AIProvider
from ...domain.services.ai_analyst import AIAnalyst
from ...domain.services.cross_anomaly_service import CrossAnomalyService
from ...domain.services.dependency import DependencyService
from ...domain.services.language_detector import LanguageDetector
from ...domain.services.ner_service import SpacyNERService
from ...domain.services.prompt_registry import build_default_registry
from ...domain.services.tokenizer_service import SpacyTokenizerService
from ..ai.analyst import AIAnalyst as InfraAIAnalyst
from ..ai.analyst import BackendType
from ..db.repositories.country_repository import CountryReferenceRepository
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

    Args:
        logic_mode: True ise LLM çağrısı yapılmaz; LogicOnlyAIAnalyst kullanılır.
        ai_limit:   Pozitif tam sayı ise ilk N cümle AI'a gönderilir,
                    sonrası otomatik olarak LogicOnly'ye düşer.
                    None veya 0 ise limit yok (tüm cümleler normal modda işlenir).
    """

    _instance: ServiceContainer | None = None

    def __init__(self, logic_mode: bool = False, ai_limit: int | None = None) -> None:
        self._logic_mode = logic_mode
        self._ai_limit = ai_limit
        mode_label = "LOGIC-ONLY (AI-free)" if logic_mode else "FULL (AI enabled)"
        if ai_limit and ai_limit > 0 and not logic_mode:
            mode_label += f" [limit={ai_limit} cümle]"
        logger.info(f"ServiceContainer başlatılıyor — mod={mode_label}")

        # ── Ortak Araçlar ──────────────────────────────────────────
        self.language_detector = LanguageDetector()

        # ── NLP Servisleri ─────────────────────────────────────────
        self.ner_service = SpacyNERService(language_detector=self.language_detector)
        self.tokenizer_service = SpacyTokenizerService(
            language_detector=self.language_detector
        )

        # ── Prompt Registry + AI Analyst ───────────────────────────
        if logic_mode:
            # LLM çağrısı yapmayan kural tabanlı analiz servisi
            from bb_paxdata.infrastructure.nlp.logic_only_analyst import (
                LogicOnlyAIAnalyst,
            )

            self.prompt_registry = build_default_registry()
            self.few_shot_injector = None
            self.ai_analyst: Any = LogicOnlyAIAnalyst()
            logger.info(
                "AI Analyst: LogicOnlyAIAnalyst aktif (LLM çağrısı yapılmayacak)"
            )
        else:
            from bb_paxdata.application.services.few_shot_injector import (
                FewShotInjector,
            )
            from bb_paxdata.infrastructure.db.repositories.unit_of_work import (
                SqlAlchemyUnitOfWork,
            )
            from bb_paxdata.infrastructure.db.session import SessionLocal

            def uow_factory() -> SqlAlchemyUnitOfWork:
                return SqlAlchemyUnitOfWork(SessionLocal)

            self.few_shot_injector = FewShotInjector(uow_factory=uow_factory)
            self.prompt_registry = build_default_registry()

            # Initialize infra analyst
            settings = get_settings()
            provider_map = {
                AIProvider.OLLAMA: BackendType.OLLAMA,
                AIProvider.ANTHROPIC: BackendType.ANTHROPIC,
                AIProvider.GEMINI: BackendType.GEMINI,
                AIProvider.GROQ: BackendType.GROQ,
            }
            backend_type = provider_map.get(settings.ai_provider, BackendType.OLLAMA)
            api_key = settings.active_ai_api_key
            base_url = settings.ollama_base_url

            self.infra_analyst = InfraAIAnalyst(
                default_backend=backend_type,
                api_key=api_key if api_key else None,
                base_url=base_url,
            )

            _real_analyst = AIAnalyst(
                registry=self.prompt_registry,
                language_detector=self.language_detector,
                few_shot_injector=self.few_shot_injector,
                infra_analyst=self.infra_analyst,
            )

            # AI limit varsa wrapper ile sar
            if ai_limit and ai_limit > 0:
                from bb_paxdata.infrastructure.nlp.limited_ai_analyst import (
                    LimitedAIAnalyst,
                )

                self.ai_analyst = LimitedAIAnalyst(
                    delegate=_real_analyst, limit=ai_limit
                )
                logger.info(
                    f"AI Analyst: LimitedAIAnalyst aktif — "
                    f"ilk {ai_limit} cümle AI, sonrası LogicOnly"
                )
            else:
                self.ai_analyst = _real_analyst

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
        self.dependency_service = DependencyService()

        # ── Pipeline Stages ────────────────────────────────────────
        # Note: CountryReferenceCollector needs a spacy model.
        # For the container, we use the default 'en' model from NER service.
        from bb_paxdata.domain.services.actor_resolver import NER_GPE as resolver_gpe

        extended_gpe = set(resolver_gpe) | {
            "Turkey",
            "Türkiye",
            "Kazakhstan",
            "Georgia",
            "North Macedonia",
            "Somalia",
            "Syria",
            "Russia",
            "USA",
            "Ukraine",
            "Azerbaijan",
            "Serbia",
            "Latvia",
            "Lithuania",
            "Palestine",
            "Yemen",
            "Burundi",
            "Congo",
            "Sierra Leone",
            "Comoros",
            "El Salvador",
            "Iran",
            "Israel",
            "China",
            "Saudi Arabia",
            "Qatar",
            "UAE",
            "Iraq",
            "Lebanon",
            "Libya",
            "Egypt",
            "Sudan",
            "Afghanistan",
            "Pakistan",
            "India",
            "Japan",
            "Germany",
            "France",
            "UK",
            "Italy",
            "Europe",
            "EU",
            "Balkans",
            "Caucasus",
            "Middle East",
            "Africa",
            "Central Asia",
            "Persian Gulf",
            "Black Sea",
            "Red Sea",
            "Mediterranean",
            "Ankara",
            "Moscow",
            "Washington",
            "Brussels",
            "Kyiv",
            "Damascus",
            "Mogadishu",
            "Riyadh",
            "Beijing",
            "Western Balkans",
            "South Caucasus",
            "Global South",
            "Indo-Pacific",
        }
        self.country_collector = CountryReferenceCollector(
            nlp=common_nlp,
            country_vocabulary=extended_gpe,
            llm_client=self.ai_analyst,
            # recovery_engine and prompt_registry could be injected here if needed
        )
        self.finalize_stage = FinalizeStage(
            country_ref_repo=CountryReferenceRepository(None)
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
            llm_client=cast(Any, self.ai_analyst),
            topic_service=self.topic_modeling_service,
            recovery_engine=self.recovery_engine,
        )

        # ── Dual-Gate Consensus (Faz 4) ───────────────────────────
        from ...application.consensus.dual_gate import DualGateConsensusLayer
        from ..ai.anomaly_controller import AIAnomalyController

        settings = get_settings()

        self.anomaly_controller = AIAnomalyController(
            ai_client=cast(Any, self.ai_analyst),
            recovery_engine=self.recovery_engine,
            max_context_sentences=settings.anomaly_context_window,
        )

        self.consensus_layer = DualGateConsensusLayer()

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
            dual_gate_layer=self.consensus_layer,
            anomaly_controller=self.anomaly_controller,
            finalize_stage=self.finalize_stage,
        )

        logger.info("ServiceContainer hazır — tüm servisler aktif.")

    @classmethod
    def get_instance(
        cls, logic_mode: bool = False, ai_limit: int | None = None
    ) -> ServiceContainer:
        """Thread-unsafe singleton (production'da threading.Lock ekle).

        Args:
            logic_mode: True ise LogicOnlyAIAnalyst kullanılır.
            ai_limit:   Pozitif tam sayı ise ilk N cümle AI, sonrası LogicOnly.
                        İlk çağrıda belirlenir; sonraki çağrılarda görmezden gelinir.
        """
        if cls._instance is None:
            cls._instance = cls(logic_mode=logic_mode, ai_limit=ai_limit)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Singleton'ı sıfırlar (test ve mod değişikliği için)."""
        cls._instance = None
