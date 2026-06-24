from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from bb_paxdata.application.domain.enums import AIProvider, DatabaseMode, LogLevel


class PresuppositionConfig(BaseModel):
    """
    Configuration for presupposition extraction (TASK-A06).
    """

    trigger_specificity_overrides: dict[str, float] = Field(
        default_factory=lambda: {
            "regret": 0.90,
            "acknowledge": 0.85,
            "fail": 0.82,
            "manage": 0.80,
            "realize": 0.70,
            "still": 0.68,
            "again": 0.65,
            "know": 0.60,
            "start": 0.50,
            "stop": 0.50,
            "continue": 0.55,
        },
        description="Trigger-specific specificity weights for confidence calculation",
    )
    default_specificity: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Default specificity for triggers not in overrides",
    )
    llm_confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Threshold for LLM verification of low-confidence candidates",
    )
    batch_size: int = Field(
        default=20, ge=1, le=100, description="Batch size for LLM verification"
    )
    cache_ttl_seconds: int | None = Field(
        default=None,
        description="Cache TTL in seconds (None = no TTL, LRU eviction only)",
    )
    use_llm_verification: bool = Field(
        default=True,
        description="Whether to use LLM verification for low-confidence candidates",
    )


class RetentionPolicyConfig(BaseModel):
    """
    Configuration for data retention policies (TASK-1.3.1).
    """

    raw_transcript_retention_years: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Retention period for raw transcripts in years",
    )
    ai_analysis_retention_years: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Retention period for AI analysis results in years",
    )
    anonymized_statistics_permanent: bool = Field(
        default=True,
        description="Whether anonymized statistics are kept permanently",
    )
    hitl_corrections_permanent: bool = Field(
        default=True,
        description="Whether HITL corrections are kept permanently as training data",
    )
    archive_after_retention: bool = Field(
        default=True,
        description="Whether to archive data before deletion after retention period",
    )
    archive_cleanup_enabled: bool = Field(
        default=True,
        description="Enable automatic cleanup of archived data after retention period",
    )


class ArchiveConfig(BaseModel):
    """
    Configuration for data archiving pipeline (TASK-1.3.2).
    """

    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="S3/MinIO endpoint URL",
    )
    s3_access_key: str = Field(default="", description="S3/MinIO access key")
    s3_secret_key: SecretStr = Field(
        default=SecretStr(""), description="S3/MinIO secret key"
    )
    s3_bucket_name: str = Field(
        default="paxdata-archives",
        description="S3/MinIO bucket name for archives",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3/MinIO region",
    )
    archive_compression: bool = Field(
        default=True,
        description="Whether to compress archives with gzip",
    )
    archive_encryption_enabled: bool = Field(
        default=True,
        description="Whether to encrypt archives with AES-256",
    )
    archive_encryption_key: SecretStr = Field(
        default=SecretStr(""),
        description="Encryption key for archives (if enabled)",
    )


class PIIAnonymizationConfig(BaseModel):
    """
    Configuration for PII detection and anonymization (TASK-1.3.3).
    """

    speaker_name_encoding_prefix: str = Field(
        default="P",
        description="Prefix for encoded speaker names (e.g., P-001, P-002)",
    )
    location_generalization_enabled: bool = Field(
        default=True,
        description="Whether to generalize location information",
    )
    location_generalization_level: Literal["country", "region", "city"] = Field(
        default="country",
        description="Level of location generalization",
    )
    gdpr_right_to_be_forgotten_enabled: bool = Field(
        default=True,
        description="Enable GDPR Right to be Forgotten automation",
    )
    pii_detection_model: str = Field(
        default="en_core_web_sm",
        description="spaCy model for PII detection",
    )
    custom_pii_patterns: dict[str, str] = Field(
        default_factory=dict,
        description="Custom regex patterns for PII detection",
    )


class Settings(BaseSettings):
    """
    Uygulama çapındaki yapılandırma.
    Tüm env değişkenleri PAXDATA_ prefix'i ile tanımlanır.

    Örnek .env:
        PAXDATA_DEBUG=true
        PAXDATA_LOG_LEVEL=DEBUG
        PAXDATA_DATABASE_PATH=/data/paxdata.db
        PAXDATA_ANTHROPIC_API_KEY=sk-ant-...
    """

    model_config = SettingsConfigDict(
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        env_prefix="PAXDATA_",
        extra="ignore",
        populate_by_name=True,
        # Secrets dosyasından da okuyabilir (Docker secret mounting için)
        secrets_dir="/run/secrets" if Path("/run/secrets").exists() else None,
    )

    # ── Genel ────────────────────────────────────────────────────────────
    app_name: str = Field(default="PAXDATA", frozen=True)
    version: str = Field(default="6.0.0", frozen=True)
    debug: bool = Field(default=False)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    environment: str = Field(default="production")  # production | staging | test
    cors_allowed_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:5176",
            "http://127.0.0.1:5176",
        ],
        description="CORS allowed origins. Use specific origins in production, never use ['*']",
    )

    # ── Veritabanı ────────────────────────────────────────────────────────
    database_mode: DatabaseMode = Field(default=DatabaseMode.SQLITE)
    database_url: str | None = Field(default=None)
    database_path: Path = Field(default=Path("paxdata.db"))
    redis_url: str = Field(default="redis://localhost:6379/0")
    alembic_ini_path: Path = Field(default=Path("alembic.ini"))
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_pool_timeout: int = Field(default=30, ge=5, le=300)
    database_replica_url: str | None = Field(
        default=None,
        description="PostgreSQL read replica URL for analytics queries",
    )
    meilisearch_url: str = Field(default="http://localhost:7700")
    meilisearch_master_key: str = Field(
        default="", description="Master key for Meilisearch (required in production)"
    )
    metrics_token: str = Field(
        default="", description="Token required to access /metrics endpoint"
    )
    jwt_secret_key: str = Field(
        default="dev-secret-change-in-production",
        description="JWT secret key for authentication (must be changed in production)",
    )

    # ── OpenTelemetry Tracing ─────────────────────────────────────────────
    otel_enabled: bool = Field(default=False)
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4317")
    otel_service_name: str = Field(default="bb-paxdata")

    # ── Sentry Error Tracking ─────────────────────────────────────────────
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking")
    sentry_traces_sample_rate: float = Field(
        default=1.0, description="Sentry traces sample rate"
    )

    # ── APM Integration ───────────────────────────────────────────────────
    apm_provider: str = Field(
        default="none", description="APM provider: none, newrelic, datadog"
    )
    newrelic_license_key: str = Field(default="", description="New Relic license key")
    newrelic_app_name: str = Field(
        default="bb-paxdata", description="New Relic app name"
    )
    newrelic_enabled: bool = Field(default=False, description="Enable New Relic APM")
    datadog_api_key: str = Field(default="", description="Datadog API key")
    datadog_service_name: str = Field(
        default="bb-paxdata", description="Datadog service name"
    )
    datadog_enabled: bool = Field(default=False, description="Enable Datadog APM")
    datadog_host: str = Field(default="localhost", description="Datadog agent host")
    datadog_port: int = Field(default=8126, description="Datadog agent port")

    # ── Log Shipping ─────────────────────────────────────────────────────
    loki_url: str = Field(default="", description="Grafana Loki URL")
    loki_enabled: bool = Field(default=False, description="Enable Loki log shipping")
    elk_url: str = Field(default="", description="Elasticsearch URL")
    elk_enabled: bool = Field(default=False, description="Enable ELK log shipping")
    elk_index: str = Field(
        default="bb-paxdata-logs", description="Elasticsearch index name"
    )

    # ── AI / LLM ─────────────────────────────────────────────────────────

    ai_provider: AIProvider = Field(default=AIProvider.OLLAMA)
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    gemini_api_key: SecretStr = Field(default=SecretStr(""))
    groq_api_key: SecretStr = Field(default=SecretStr(""))
    deepseek_api_key: SecretStr = Field(default=SecretStr(""))
    ollama_base_url: str = Field(default="http://localhost:11434")
    ai_model: str = Field(default="claude-3-5-sonnet-20241022")
    ai_timeout: int = Field(default=120, ge=1, le=600)
    ai_max_retries: int = Field(default=3, ge=0, le=10)

    # ── İş Akışı ─────────────────────────────────────────────────────────
    batch_size: int = Field(default=10, ge=1, le=500)
    json_recovery_level: int = Field(default=6, ge=0, le=6)

    # ── DualGate Konfigürasyonu ──────────────────────────────────────────
    anomaly_context_window: int = Field(
        default=5, description="AIAnomalyController'a verilecek bağlam cümle sayısı"
    )
    anomaly_controller_enabled: bool = Field(
        default=True,
        description="AIAnomalyController'ı devre dışı bırakmak için False yap",
    )
    anomaly_soft_log_only: bool = Field(
        default=True, description="SOFT_ANOMALY'leri sadece logla, HITL'e gönderme"
    )

    # ── Metodoloji ve Eşikler ─────────────────────────────────────────────
    risk_ai_weight: float = Field(default=0.6, description="Risk Hesaplama AI Ağırlığı")
    risk_anomaly_weight: float = Field(
        default=0.4, description="Risk Hesaplama Anomali Ağırlığı"
    )
    formula_tolerance: float = Field(
        default=0.01, description="Formula validation tolerance threshold"
    )
    risk_threshold: float = Field(
        default=70.0, description="Kullanıcı kontrollü risk uyarı eşik değeri (0-100)"
    )
    risk_fallback_anomaly_weight: float = Field(
        default=1.0, description="AI devredışıyken anomali ağırlığı"
    )

    # ── Presupposition Extraction (TASK-A06) ───────────────────────────────
    presupposition: PresuppositionConfig = Field(
        default_factory=PresuppositionConfig,
        description="Presupposition extraction configuration",
    )

    # ── Data Retention Policy (TASK-1.3.1) ────────────────────────────────
    retention_policy: RetentionPolicyConfig = Field(
        default_factory=RetentionPolicyConfig,
        description="Data retention policy configuration",
    )

    # ── Archive Configuration (TASK-1.3.2) ────────────────────────────────
    archive: ArchiveConfig = Field(
        default_factory=ArchiveConfig,
        description="Archive pipeline configuration",
    )

    # ── PII Anonymization (TASK-1.3.3) ─────────────────────────────────────
    pii_anonymization: PIIAnonymizationConfig = Field(
        default_factory=PIIAnonymizationConfig,
        description="PII detection and anonymization configuration",
    )

    # ── Comparison Engine (TASK-E01) ────────────────────────────────────────
    comparison_narrative_enabled: bool = Field(
        default=True,
        description="Enable LLM narrative generation for session comparisons",
    )
    comparison_narrative_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for comparison narrative generation",
    )
    comparison_narrative_max_tokens: int = Field(
        default=1000,
        ge=100,
        le=4000,
        description="Max tokens for comparison narrative generation",
    )

    # ── ColBERT RAG (TASK-E03) ───────────────────────────────────────────────
    use_colbert: bool = Field(
        default=False,
        description="Feature flag: enables ColBERT PLAID late-interaction retrieval. Requires colbert_index_path to contain a pre-built PLAID index.",
    )
    colbert_index_path: Path = Field(
        default=Path(".colbert_index"),
        description="Filesystem path to the ragatouille PLAID index directory.",
    )
    colbert_index_name: str = Field(
        default="bb_paxdata_rag",
        description="Subdirectory name of the active PLAID index within colbert_index_path.",
    )

    # ── SRL Model Settings ────────────────────────────────────────────────
    srl_model_name: str = Field(
        default="dannashao/bert-base-uncased-finetuned-srl_arg",
        validation_alias=AliasChoices("PAXDATA_SRL_MODEL_NAME", "SRL_MODEL_NAME"),
        description="HuggingFace model identifier for SRL",
    )
    srl_device: Literal["auto", "cpu", "cuda", "mps"] = Field(
        default="auto",
        validation_alias=AliasChoices("PAXDATA_SRL_DEVICE", "SRL_DEVICE"),
        description="Compute device selection for SRL",
    )
    srl_batch_size: int = Field(
        default=32,
        ge=1,
        le=128,
        validation_alias=AliasChoices("PAXDATA_SRL_BATCH_SIZE", "SRL_BATCH_SIZE"),
        description="Batch size for SRL inference",
    )
    srl_enable_cache: bool = Field(
        default=True,
        validation_alias=AliasChoices("PAXDATA_SRL_ENABLE_CACHE", "SRL_ENABLE_CACHE"),
        description="Enable LRU caching of SRL predictions",
    )
    srl_use_quantization: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "PAXDATA_SRL_USE_QUANTIZATION", "SRL_USE_QUANTIZATION"
        ),
        description="Enable INT8 quantization for SRL",
    )

    # ── Argument Mining Settings ──────────────────────────────────────────
    argmining_claim_threshold: float = Field(
        default=0.78,
        ge=0.5,
        le=0.99,
        validation_alias=AliasChoices(
            "PAXDATA_ARGMINING_CLAIM_THRESHOLD", "ARGMINING_CLAIM_THRESHOLD"
        ),
        description="Minimum confidence to classify segment as CLAIM",
    )
    argmining_use_srl: bool = Field(
        default=True,
        validation_alias=AliasChoices("PAXDATA_ARGMINING_USE_SRL", "ARGMINING_USE_SRL"),
        description="Use SRL ARG1 spans as additional features for claim detection",
    )
    argmining_rel_threshold: float = Field(
        default=0.65,
        ge=0.4,
        le=0.99,
        validation_alias=AliasChoices(
            "PAXDATA_ARGMINING_REL_THRESHOLD", "ARGMINING_REL_THRESHOLD"
        ),
        description="Minimum confidence to accept relation prediction",
    )
    argmining_edu_method: Literal["rst", "spacy", "hybrid"] = Field(
        default="hybrid",
        validation_alias=AliasChoices(
            "PAXDATA_ARGMINING_EDU_METHOD", "ARGMINING_EDU_METHOD"
        ),
        description="Segmentation strategy",
    )
    argmining_device: Literal["auto", "cpu", "cuda", "mps"] = Field(
        default="auto",
        validation_alias=AliasChoices("PAXDATA_ARGMINING_DEVICE", "ARGMINING_DEVICE"),
        description="Compute device for argument mining",
    )
    argmining_cache: bool = Field(
        default=True,
        validation_alias=AliasChoices("PAXDATA_ARGMINING_CACHE", "ARGMINING_CACHE"),
        description="Enable argument mining result caching",
    )
    argmining_validate_dag: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "PAXDATA_ARGMINING_VALIDATE_DAG", "ARGMINING_VALIDATE_DAG"
        ),
        description="Enforce acyclic graph constraint",
    )

    # ── Appraisal Settings ────────────────────────────────────────────────
    appraisal_classifier_model_name: str = Field(
        default="cross-encoder/nli-deberta-v3-base",
        validation_alias=AliasChoices(
            "PAXDATA_APPRAISAL_CLASSIFIER_MODEL", "APPRAISAL_CLASSIFIER_MODEL"
        ),
        description="Zero-shot NLI classifier model name for appraisal",
    )
    appraisal_use_classifier: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "PAXDATA_APPRAISAL_USE_CLASSIFIER", "APPRAISAL_USE_CLASSIFIER"
        ),
        description="Whether to use classifier mode for appraisal",
    )
    appraisal_fine_tuned_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PAXDATA_APPRAISAL_FINE_TUNED_PATH", "APPRAISAL_FINE_TUNED_PATH"
        ),
        description="Path to fine-tuned appraisal model",
    )
    appraisal_srl_argm_mod_graduation_boost: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices(
            "PAXDATA_APPRAISAL_SRL_BOOST", "APPRAISAL_SRL_BOOST"
        ),
        description="Boost applied to graduation force when SRL modal verb exists",
    )
    appraisal_cache_max_entries: int = Field(
        default=5000,
        ge=10,
        le=100000,
        validation_alias=AliasChoices(
            "PAXDATA_APPRAISAL_CACHE_MAX", "APPRAISAL_CACHE_MAX"
        ),
        description="Maximum LRU cache entries for AppraisalService",
    )

    # ── OpenAI API Key ───────────────────────────────────────────────────
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("PAXDATA_OPENAI_API_KEY", "OPENAI_API_KEY"),
        description="OpenAI API Key for evaluations",
    )

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("database_url", mode="before")
    @classmethod
    def _build_database_url(cls, v: str | None, info: Any) -> str | None:
        """SQLite için URL otomatik üretir; dışarıdan verilmişse dokunmaz."""
        if v is not None:
            return v
        mode = info.data.get("database_mode", DatabaseMode.SQLITE)
        if mode == DatabaseMode.SQLITE:
            path = info.data.get("database_path", Path("paxdata.db"))
            abs_path = Path(path).expanduser().resolve()
            return f"sqlite+aiosqlite:///{abs_path}"
        return None  # PostgreSQL URL zorunlu; model_validator kontrol eder

    @field_validator("database_path", mode="after")
    @classmethod
    def _resolve_paths(cls, v: Path | None) -> Path | None:
        if v is None:
            return None
        return v.expanduser().resolve()

    @model_validator(mode="after")
    def _validate_postgresql_url(self) -> Settings:
        """PostgreSQL seçilmişse URL'in tanımlı olduğunu doğrula."""
        if self.database_mode == DatabaseMode.POSTGRESQL and not self.database_url:
            raise ValueError(
                "DATABASE_MODE=postgresql için PAXDATA_DATABASE_URL zorunludur.\n"
                "Örnek: postgresql+asyncpg://user:pass@localhost/paxdata"
            )
        return self

    @model_validator(mode="after")
    def _validate_ai_key_present(self) -> Settings:
        """AI provider seçilmişse ilgili API key'in tanımlı olduğunu kontrol eder."""
        key_map = {
            AIProvider.ANTHROPIC: self.anthropic_api_key,
            AIProvider.GEMINI: self.gemini_api_key,
            AIProvider.GROQ: self.groq_api_key,
            AIProvider.DEEPSEEK: self.deepseek_api_key,
        }
        if self.ai_provider in key_map:
            secret = key_map[self.ai_provider]
            if not secret.get_secret_value():
                import warnings

                warnings.warn(
                    f"AI provider '{self.ai_provider.value}' seçildi fakat API key boş.",
                    stacklevel=2,
                )
        return self

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> Settings:
        """Production'da JWT secret key'in güvenli olduğunu doğrular."""
        if (
            self.environment == "production"
            and self.jwt_secret_key == "dev-secret-change-in-production"
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be set in production environment. "
                "Current value is the insecure default."
            )
        return self

    @model_validator(mode="after")
    def _validate_meilisearch_key(self) -> Settings:
        """Production'da Meilisearch master key'in tanımlı olduğunu doğrular."""
        if self.environment == "production" and not self.meilisearch_master_key:
            raise ValueError(
                "MEILISERCH_MASTER_KEY must be set in production environment. "
                "This is required to secure Meilisearch access."
            )
        return self

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_async_db(self) -> bool:
        if self.database_url is None:
            return False
        return "aiosqlite" in self.database_url or "asyncpg" in self.database_url

    @property
    def ai_backend(self) -> str:
        """Seçili provider'ı factory'ye uygun string'e dönüştürür."""
        provider_map = {
            AIProvider.OLLAMA: "local",
            AIProvider.ANTHROPIC: "api",
            AIProvider.GEMINI: "gemini",
            AIProvider.GROQ: "groq",
            AIProvider.DEEPSEEK: "deepseek",
        }
        return provider_map.get(self.ai_provider, "local")

    @property
    def active_ai_api_key(self) -> str:
        """Seçili provider'ın API key'ini döndürür."""
        key_map = {
            AIProvider.ANTHROPIC: self.anthropic_api_key,
            AIProvider.GEMINI: self.gemini_api_key,
            AIProvider.GROQ: self.groq_api_key,
            AIProvider.DEEPSEEK: self.deepseek_api_key,
        }
        secret = key_map.get(self.ai_provider)
        return secret.get_secret_value() if secret else ""

    @property
    def is_test_environment(self) -> bool:
        return self.environment == "test"

    @property
    def srl(self) -> Any:
        from bb_paxdata.infrastructure.nlp.srl_config import SRLModelConfig

        return SRLModelConfig(
            model_name=self.srl_model_name,
            device=self.srl_device,
            batch_size=self.srl_batch_size,
            enable_cache=self.srl_enable_cache,
            use_quantization=self.srl_use_quantization,
        )

    @property
    def argmining(self) -> Any:
        from bb_paxdata.infrastructure.nlp.argmining_config import (
            ArgumentMiningPipelineConfig,
            ClaimDetectionConfig,
            EDUSegmentationConfig,
            RelationClassificationConfig,
        )

        return ArgumentMiningPipelineConfig(
            claim_detection=ClaimDetectionConfig(
                confidence_threshold=self.argmining_claim_threshold,
                use_srl_guidance=self.argmining_use_srl,
            ),
            relation_classification=RelationClassificationConfig(
                confidence_threshold=self.argmining_rel_threshold,
            ),
            edu_segmentation=EDUSegmentationConfig(
                method=self.argmining_edu_method,
            ),
            device=self.argmining_device,
            enable_cache=self.argmining_cache,
            validate_dag_on_build=self.argmining_validate_dag,
        )

    @property
    def appraisal(self) -> Any:
        from bb_paxdata.application.domain.lexicon.appraisal_config import (
            AppraisalPipelineConfig,
        )

        return AppraisalPipelineConfig(
            classifier_model_name=self.appraisal_classifier_model_name,
            use_classifier=self.appraisal_use_classifier,
            fine_tuned_path=self.appraisal_fine_tuned_path,
            srl_argm_mod_graduation_boost=self.appraisal_srl_argm_mod_graduation_boost,
            cache_max_entries=self.appraisal_cache_max_entries,
        )


# ── Singleton Yönetimi ────────────────────────────────────────────────────

_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Global settings singleton.
    Test ortamında `reset_settings()` ile temizlenebilir.
    CI/CD'de PAXDATA_ENVIRONMENT=test ile test moduna alınır.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        # Override with custom settings if exists
        custom_path = Path("data/system_settings.json")
        if custom_path.exists():
            try:
                import json

                with open(custom_path, encoding="utf-8") as f:
                    custom_data = json.load(f)
                for field, value in custom_data.items():
                    if hasattr(_settings, field):
                        setattr(_settings, field, value)
            except Exception:
                pass
    return _settings


def reset_settings() -> None:
    """Test teardown ve hot-reload için singleton'ı temizle."""
    global _settings
    _settings = None


def override_settings(**kwargs: Any) -> Settings:
    """
    Test yardımcısı: belirli alanları ezerek geçici Settings oluşturur.

    Kullanım:
        s = override_settings(debug=True, batch_size=1)
    """
    global _settings
    base = get_settings().model_dump()
    base.update(kwargs)
    _settings = Settings(**base)
    return _settings
