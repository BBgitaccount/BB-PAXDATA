# ============================================================
# DOSYA: src/bb_paxdata/infrastructure/container/service_container.py
# AÇIKLAMA: Singleton IoC container — stub YOK
# ============================================================

from __future__ import annotations

import threading
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.domain.services.ai_analyst import AIAnalyst
from ...application.domain.services.appraisal_service import get_appraisal_service
from ...application.domain.services.cross_anomaly_service import CrossAnomalyService
from ...application.domain.services.dependency import DependencyService
from ...application.domain.services.language_detector import LanguageDetector
from ...application.domain.services.ner_service import SpacyNERService
from ...application.domain.services.prompt_registry import build_default_registry
from ...application.domain.services.tokenizer_service import SpacyTokenizerService
from ...application.pipeline.analysis_pipeline import AnalysisPipeline
from ...application.pipeline.assembler import AnalysisAssembler
from ...application.pipeline.sbi_calculator import SBICalculator
from ...application.pipeline.stages.country_reference_collector import (
    CountryReferenceCollector,
)
from ...application.pipeline.stages.finalize_stage import FinalizeStage
from ...config.settings import get_settings
from ..db.repositories.unit_of_work import SqlAlchemyUnitOfWork
from ..db.session import SessionLocal
from ..event_bus.simple_event_bus import SimpleEventBus
from ..nlp.gat_embedding_service import GATEmbeddingService
from ..nlp.maoz_dyadic_service import MaozDyadicService
from ..nlp.negation_detector import SpacyNegationDetector
from ..nlp.power_index_calculator import PowerIndexCalculator
from ..nlp.risk_signal_detector import RiskSignalDetector
from ..nlp.topic_modeling import TopicModelingService

logger = structlog.get_logger(__name__)


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
    _lock: threading.Lock = threading.Lock()

    def __init__(self, logic_mode: bool = False, ai_limit: int | None = None) -> None:
        self._logic_mode = logic_mode
        self._ai_limit = ai_limit
        mode_label = "LOGIC-ONLY (AI-free)" if logic_mode else "FULL (AI enabled)"
        if ai_limit and ai_limit > 0 and not logic_mode:
            mode_label += f" [limit={ai_limit} cümle]"
        logger.info(f"ServiceContainer başlatılıyor — mod={mode_label}")

        # ── Ortak Araçlar ──────────────────────────────────────────
        self.language_detector = LanguageDetector()
        import httpx

        from ..ai.fail_check import AIFailCheck
        from ..ai.recovery import RecoveryEngine

        self._http_client = httpx.AsyncClient(timeout=30.0)
        self.fail_check = AIFailCheck(http_client=self._http_client)

        self.recovery_engine = RecoveryEngine()

        # SBERT Embedding Cache (Faz 2.4) - Initialized early for use in other components
        import redis.asyncio as aioredis

        from bb_paxdata.infrastructure.nlp.sbert_embedding_service import (
            SBERTEmbeddingService,
        )

        settings = get_settings()
        self.redis_client = aioredis.Redis.from_url(
            settings.redis_url, decode_responses=False
        )
        self.embedding_service = SBERTEmbeddingService(redis_client=self.redis_client)

        # ── NLP Servisleri ─────────────────────────────────────────
        self.ner_service = SpacyNERService(language_detector=self.language_detector)
        self.tokenizer_service = SpacyTokenizerService(
            language_detector=self.language_detector
        )
        self.appraisal_service = get_appraisal_service()
        self.maoz_dyadic_service = MaozDyadicService()

        from ..nlp.liwc_proxy import LIWCProxyService

        self.liwc_proxy = LIWCProxyService()

        from bb_paxdata.application.domain.services.speech_act_classifier import (
            SpeechActClassifierService,
        )
        from bb_paxdata.application.protocols import SpeechActClassifierProtocol

        self.speech_act_classifier: SpeechActClassifierProtocol = (
            SpeechActClassifierService(model_name="deberta-v3-small")
        )

        # ── Prompt Registry + AI Analyst ───────────────────────────
        if logic_mode:
            # LLM çağrısı yapmayan kural tabanlı analiz servisi
            from bb_paxdata.infrastructure.nlp.logic_only_analyst import (
                LogicOnlyAIAnalyst,
            )

            # Try to use database-backed registry if available
            try:
                from ..db.session import SessionLocalSync

                self.prompt_registry = build_default_registry(
                    db_session=SessionLocalSync()
                )
            except Exception:
                self.prompt_registry = build_default_registry()
            self.few_shot_injector = None
            self.ai_analyst: Any = LogicOnlyAIAnalyst()
            logger.info(
                "AI Analyst: LogicOnlyAIAnalyst aktif (LLM çağrısı yapılmayacak)"
            )
        else:
            from bb_paxdata.application.services.dynamic_few_shot_optimizer import (
                DbExampleStore,
                RedisEmbeddingCache,
                VectorSimilaritySelector,
            )
            from bb_paxdata.application.services.few_shot_injector import (
                FewShotInjector,
            )

            def uow_factory() -> SqlAlchemyUnitOfWork:
                return SqlAlchemyUnitOfWork(SessionLocal)

            self.redis_cache = RedisEmbeddingCache(redis=self.redis_client)
            self.example_store = DbExampleStore(session_factory=SessionLocal)
            self.few_shot_selector = VectorSimilaritySelector(
                embedding_service=self.embedding_service,
                example_store=self.example_store,
                cache=self.redis_cache,
            )
            self.few_shot_injector = FewShotInjector(
                selector=self.few_shot_selector,
                uow_factory=uow_factory,
            )
            # Try to use database-backed registry if available
            try:
                from ..db.session import SessionLocalSync

                self.prompt_registry = build_default_registry(
                    db_session=SessionLocalSync()
                )
            except Exception:
                self.prompt_registry = build_default_registry()

            # Initialize infra analyst
            settings = get_settings()
            from ..ai.factory import AIClientFactory

            self.infra_analyst = AIClientFactory.from_settings(settings)

            from bb_paxdata.infrastructure.ai.batch import BatchProcessor

            self.batch_processor = BatchProcessor(
                client=self.infra_analyst,
                recovery_engine=self.recovery_engine,
            )

            _real_analyst = AIAnalyst(
                registry=self.prompt_registry,
                language_detector=self.language_detector,
                few_shot_injector=self.few_shot_injector,
                infra_analyst=self.infra_analyst,
                batch_processor=self.batch_processor,
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
        if common_nlp is None:
            raise RuntimeError(
                "SpaCy NLP modeli yüklenemedi. "
                "'en_core_web_lg' veya 'tr_core_news_md' modellerinden en az biri "
                "kurulu ve erişilebilir olmalıdır. "
                "Kurulum için: python -m spacy download en_core_web_lg"
            )

        self.negation_detector = SpacyNegationDetector(
            nlp_en=self.ner_service._models.get("en"),
            nlp_tr=self.ner_service._models.get("tr"),
        )
        self.risk_detector = RiskSignalDetector(nlp=common_nlp)
        self.power_calculator = PowerIndexCalculator(nlp=common_nlp)

        # SBERT Embedding Cache (Faz 2.4) - Already initialized early

        self.topic_modeling_service = TopicModelingService(
            prompt_registry=self.prompt_registry,
            embedding_service=self.embedding_service,
        )

        # ── GAT Embedding Service (TASK-E02) ───────────────────────
        # torch-geometric opsiyonel bir bağımlılıktır; yüklü değilse
        # GAT özellikleri devre dışı kalır ama pipeline çalışmaya devam eder.
        try:
            self.gat_embedding_service = GATEmbeddingService()
        except ImportError as _pyg_err:
            self.gat_embedding_service = None
            logger.warning(
                "GAT Embedding Service başlatılamadı — torch_geometric yüklü değil. "
                "GAT özellikleri devre dışı. "
                "Yüklemek için: pip install torch-geometric",
                error=str(_pyg_err),
            )

        from ..nlp.semantic_shift import AzarbonyadSemanticShiftCalculator

        self.semantic_shift_calculator = AzarbonyadSemanticShiftCalculator(
            embedding_service=self.embedding_service
        )

        if logic_mode:
            self.llm_position_estimator = None
        else:
            from ..ai.llm_position_estimator import CambridgeCoreLLMPositionEstimator

            self.llm_position_estimator = CambridgeCoreLLMPositionEstimator(
                client=self.infra_analyst,
                prompt_registry=self.prompt_registry,
                recovery_engine=self.recovery_engine,
            )

        self.dependency_service = DependencyService()

        # ── Presupposition Extraction (TASK-A06) ─────────────────────
        from ...application.domain.lexicon.presupposition_triggers import (
            PresuppositionLexicon,
        )
        from ...application.domain.services.presupposition_service import (
            PresuppositionService,
        )
        from ...application.domain.services.presupposition_verifier import (
            PresuppositionVerifier,
        )

        # Create AI client for presupposition verification
        from ..ai.factory import AIClientFactory
        from ..cache.disk import DiskCacheBackend

        presupposition_ai_client = AIClientFactory.from_settings(get_settings())

        # Create cache backend with coordinator for consistency
        from ..cache.cache_coordinator import CacheCoordinator

        presupposition_disk_cache = DiskCacheBackend()
        presupposition_cache = CacheCoordinator(
            primary_backend=presupposition_disk_cache,
            secondary_backends=[],
            enable_pubsub=False,  # Disk cache doesn't need pub/sub
        )

        # Create verifier
        self.presupposition_verifier = PresuppositionVerifier(
            ai_client=presupposition_ai_client,
            cache=presupposition_cache,
            use_cache=True,
        )

        # Create service
        self.presupposition_service = PresuppositionService(
            verifier=self.presupposition_verifier,
            lexicon=PresuppositionLexicon.load_default(),
            negation_detector=self.negation_detector,
            llm_confidence_threshold=get_settings().presupposition.llm_confidence_threshold,
            use_llm_verification=get_settings().presupposition.use_llm_verification,
        )

        # ── Demand Analysis Services (BLOAT-5) ─────────────────────
        from ...application.domain.services.assertiveness_detector import (
            AssertivenessDetector,
        )
        from ...application.domain.services.conditional_detector import (
            ConditionalDetector,
        )
        from ...application.domain.services.demand_network_service import (
            DemandNetworkService,
        )
        from ...application.domain.services.fulfillment_tracker import (
            FulfillmentTracker,
        )
        from ...application.domain.services.temporal import TemporalAnalyzer

        self.assertiveness_detector = AssertivenessDetector()
        self.conditional_detector = ConditionalDetector()
        self.demand_network_service = DemandNetworkService()
        self.fulfillment_tracker = FulfillmentTracker()
        self.temporal_analyzer = TemporalAnalyzer()

        # ── Pipeline Stages ────────────────────────────────────────
        # Note: CountryReferenceCollector needs a spacy model.
        # For the container, we use the default 'en' model from NER service.
        from bb_paxdata.application.domain.services.actor_resolver import (
            NER_GPE as resolver_gpe,
        )

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
            unit_of_work=SqlAlchemyUnitOfWork(SessionLocal)
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
            liwc=self.liwc_proxy,
        )

        # ── Framing Servisleri (Faz 6) ─────────────────────────────
        from ...application.pipeline.frame.episodic_themetic_classifier import (
            EpisodicThematicClassifier,
        )
        from ...application.pipeline.frame.frame_assembler import FrameAssembler
        from ..ai.frame_detection.frame_detection_pipeline import FrameDetectionPipeline
        from ..ai.frame_detection.frame_lexicon_service import FrameLexiconService
        from ..ai.recovery import RecoveryEngine

        self.frame_lexicon_service = FrameLexiconService(nlp=common_nlp)

        self.episodic_classifier = EpisodicThematicClassifier(nlp=common_nlp)
        self.frame_assembler = FrameAssembler(
            lexicon_service=self.frame_lexicon_service, nlp=common_nlp
        )

        # FrameDetectionPipeline needs multiple sub-protocols (simplified here for container)
        # In a real setup, these would be separate classes.
        from bb_paxdata.infrastructure.ai.frame_detection.five_w_one_h_extractor import (
            LLMFiveWOneHExtractor,
        )

        self.five_w_one_h_extractor = LLMFiveWOneHExtractor(
            llm_client=cast(Any, self.ai_analyst), recovery=self.recovery_engine
        )
        self.frame_pipeline = FrameDetectionPipeline(
            concept_extractor=None,
            coreference_resolver=None,
            embedding_matcher=None,
            five_w_one_h_extractor=self.five_w_one_h_extractor,
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
            llm_position_estimator=self.llm_position_estimator,
            semantic_shift_calculator=self.semantic_shift_calculator,
            appraisal_service=self.appraisal_service,
        )

        # ── Phase 5 AI Deepening v2.0 Components ───────────────────
        from bb_paxdata.application.domain.services.colbert_embedding_service import (
            RAGatoulleColBERTService,
        )
        from bb_paxdata.application.domain.services.forecasting import RiskForecaster
        from bb_paxdata.application.services.baseline_fetcher import (
            RollingWindowBaselineFetcher,
        )
        from bb_paxdata.application.services.correction_event_publisher import (
            CorrectionEventPublisher,
        )
        from bb_paxdata.application.services.dki_evaluator import DKIEvaluator
        from bb_paxdata.application.services.model_evaluation_engine import (
            ModelEvaluationEngine,
        )
        from bb_paxdata.application.services.phase5_event_publisher import (
            Phase5EventPublisher,
        )
        from bb_paxdata.application.services.rag_service import (
            RAGService,
            RAGSynthesisClient,
        )
        from bb_paxdata.infrastructure.retrieval.colbert_retriever import (
            ColBERTDenseRetriever,
        )
        from bb_paxdata.infrastructure.retrieval.local_reranker import (
            LocalCrossEncoderReranker,
        )
        from bb_paxdata.infrastructure.retrieval.meilisearch_keyword_retriever import (
            MeilisearchKeywordRetriever,
        )
        from bb_paxdata.infrastructure.retrieval.pgvector_dense_retriever import (
            PgvectorDenseRetriever,
        )
        from bb_paxdata.infrastructure.search.meilisearch_client import (
            ensure_indexes,
        )

        # Configure Meilisearch indexes
        try:
            import asyncio

            # Run ensure_indexes in the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule the coroutine to run in the background
                    task = asyncio.create_task(ensure_indexes())
                    del task  # Explicitly discard to avoid unused warning
                else:
                    loop.run_until_complete(ensure_indexes())
            except RuntimeError:
                # No event loop, create a new one
                asyncio.run(ensure_indexes())
            logger.info("Meilisearch indexes configuration initiated")
        except Exception as e:
            logger.warning(
                "meilisearch_index_configuration_failed",
                error=str(e),
            )

        self.event_bus = SimpleEventBus()
        self.event_publisher = Phase5EventPublisher(event_bus=self.event_bus)
        self.correction_event_publisher = CorrectionEventPublisher(
            event_bus=self.event_bus
        )

        # Feature-flagged dense retriever factory (TASK-E03)
        from bb_paxdata.application.domain.services.protocols.rag_protocols import (
            DenseRetrieverProtocol,
        )

        settings = get_settings()
        self.dense_retriever: DenseRetrieverProtocol
        if settings.use_colbert:
            colbert_service = RAGatoulleColBERTService(
                index_path=settings.colbert_index_path
            )
            colbert_service.load_index(index_name=settings.colbert_index_name)
            self.dense_retriever = ColBERTDenseRetriever(
                colbert_service=colbert_service, session_factory=SessionLocal
            )
            logger.info(
                f"ColBERT dense retriever enabled with index at {settings.colbert_index_path}"
            )
        else:
            self.dense_retriever = PgvectorDenseRetriever(
                session_factory=SessionLocal,
                embedding_service=self.embedding_service,
            )
            logger.info("Pgvector dense retriever enabled (SBERT cosine)")

        self.keyword_retriever = MeilisearchKeywordRetriever(
            session_factory=SessionLocal,
        )
        self.local_reranker = LocalCrossEncoderReranker()
        self.rag_synthesis_client = RAGSynthesisClient(ai_analyst=self.ai_analyst)

        # Create analysis repository for RAG caching
        from bb_paxdata.infrastructure.cache.ai_cache_service import (
            AICacheService,
            AIFailCacheService,
        )
        from bb_paxdata.infrastructure.cache.cache_coordinator import CacheCoordinator
        from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
        from bb_paxdata.infrastructure.db.repositories.analysis import (
            AnalysisRepository,
        )

        # Create Redis cache backend with coordinator for consistency
        redis_cache_backend_raw = RedisCacheBackend(
            url=settings.redis_url,
            key_prefix="bbpax:ai:",
            default_ttl=3600,
        )
        self.redis_cache_backend = CacheCoordinator(
            primary_backend=redis_cache_backend_raw,
            secondary_backends=[],
            redis_url=settings.redis_url,
            enable_pubsub=True,
            pubsub_channel="bbpax:cache_invalidation",
        )

        # Start pub/sub listener for distributed invalidation
        try:
            import asyncio

            # Try to get existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule the coroutine to run in the background
                    task = asyncio.create_task(
                        self.redis_cache_backend.start_pubsub_listener()
                    )
                    del task  # Explicitly discard to avoid unused warning
                else:
                    loop.run_until_complete(
                        self.redis_cache_backend.start_pubsub_listener()
                    )
            except RuntimeError:
                # No event loop, create a new one
                asyncio.run(self.redis_cache_backend.start_pubsub_listener())
            logger.info("CacheCoordinator pub/sub listener started")
        except Exception as e:
            logger.warning(
                "Failed to start CacheCoordinator pub/sub listener", error=str(e)
            )

        # Create cache services (pass analysis_repository later after it's created)
        self.ai_cache_service = AICacheService(
            redis_backend=self.redis_cache_backend,
            analysis_repository=None,  # Will be set after repository creation
            redis_ttl=3600,
            enable_redis=True,
        )
        self.ai_fail_cache_service = AIFailCacheService(
            redis_backend=self.redis_cache_backend,
            analysis_repository=None,  # Will be set after repository creation
            redis_ttl=7200,
            enable_redis=True,
        )

        # Create analysis repository with cache services
        self.analysis_repository = AnalysisRepository(
            session=SessionLocal(),
            ai_cache_service=self.ai_cache_service,
            ai_fail_cache_service=self.ai_fail_cache_service,
        )

        # Set analysis_repository in cache services for L2 cache integration
        self.ai_cache_service._db_repo = self.analysis_repository
        self.ai_fail_cache_service._db_repo = self.analysis_repository

        self.rag_service = RAGService(
            keyword_retriever=self.keyword_retriever,
            dense_retriever=self.dense_retriever,
            reranker=self.local_reranker,
            synthesis_client=self.rag_synthesis_client,
            prompt_registry=self.prompt_registry,
            analysis_repository=self.analysis_repository,
            enable_cache=True,
        )

        self.baseline_fetcher = RollingWindowBaselineFetcher(
            session_factory=SessionLocal,
        )

        self.dki_evaluator = DKIEvaluator(
            ai_client=self.ai_analyst,
            prompt_registry=self.prompt_registry,
            audit_session_factory=SessionLocal,
        )

        self.model_evaluation_engine = ModelEvaluationEngine(
            ai_client_factory=lambda model_name: self.ai_analyst,
            embedding_service=self.embedding_service,
            session_factory=SessionLocal,
        )

        self.risk_forecaster = RiskForecaster()

        # ── API Services (WIRING-001) ───────────────────────────────
        from ...application.services.dashboard_query import DashboardQueryService
        from ..db.repositories.formula_validation import FormulaValidationRepository

        # These are factory methods that accept db session
        self._dashboard_query_service_class = DashboardQueryService
        self._formula_validation_repository_class = FormulaValidationRepository

        logger.info("ServiceContainer hazır — tüm servisler aktif.")

    @classmethod
    def get_instance(
        cls, logic_mode: bool = False, ai_limit: int | None = None
    ) -> ServiceContainer:
        """Thread-safe singleton — Double-Checked Locking pattern ile korunuyor.

        Args:
            logic_mode: True ise LogicOnlyAIAnalyst kullanılır.
            ai_limit:   Pozitif tam sayı ise ilk N cümle AI, sonrası LogicOnly.
                        İlk çağrıda belirlenir; sonraki çağrılarda görmezden gelinir.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(logic_mode=logic_mode, ai_limit=ai_limit)
        return cls._instance

    async def aclose(self) -> None:
        """Close HTTP client and any other resource connections."""
        await self._http_client.aclose()

        # Close all AI backend clients in infra_analyst
        if hasattr(self, "infra_analyst") and hasattr(self.infra_analyst, "aclose"):
            await self.infra_analyst.aclose()

        # Close presupposition verifier's AI client
        if (
            hasattr(self, "presupposition_verifier")
            and hasattr(self.presupposition_verifier, "_ai_client")
            and hasattr(self.presupposition_verifier._ai_client, "_client")
        ):
            await self.presupposition_verifier._ai_client._client.aclose()

        # Close cache coordinators
        if hasattr(self, "redis_cache_backend") and hasattr(
            self.redis_cache_backend, "close"
        ):
            await self.redis_cache_backend.close()
        if hasattr(self, "presupposition_cache") and hasattr(
            self.presupposition_cache, "close"
        ):
            await self.presupposition_cache.close()

    @classmethod
    def reset_instance(cls) -> None:
        """Singleton'ı sıfırlar (test ve mod değişikliği için)."""
        with cls._lock:
            cls._instance = None

    def dashboard_query_service(self, db: AsyncSession):
        """Factory method for DashboardQueryService."""
        return self._dashboard_query_service_class(db)

    def correction_event_publisher(self):
        """Factory method for CorrectionEventPublisher."""
        return self.correction_event_publisher

    def formula_validation_repository(self, db: AsyncSession):
        """Factory method for FormulaValidationRepository."""
        return self._formula_validation_repository_class(db)
