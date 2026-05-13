from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bb_paxdata.domain.enums import AIProvider, DatabaseMode, LogLevel


class Settings(BaseSettings):
    """
    Uygulama çapındaki yapılandırma.
    Tüm env değişkenleri BBPAX_ prefix'i ile tanımlanır.

    Örnek .env:
        BBPAX_DEBUG=true
        BBPAX_LOG_LEVEL=DEBUG
        BBPAX_DATABASE_PATH=/data/bb-paxdata.db
        BBPAX_ANTHROPIC_API_KEY=sk-ant-...
        BBPAX_LEGACY_DB_PATH=/old/data/legacy.db
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BBPAX_",
        extra="ignore",
        # Secrets dosyasından da okuyabilir (Docker secret mounting için)
        secrets_dir="/run/secrets" if Path("/run/secrets").exists() else None,
    )

    # ── Genel ────────────────────────────────────────────────────────────
    app_name: str = Field(default="BB-PAXDATA", frozen=True)
    version: str = Field(default="6.0.0", frozen=True)
    debug: bool = Field(default=False)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    environment: str = Field(default="production")  # production | staging | test

    # ── Veritabanı ────────────────────────────────────────────────────────
    database_mode: DatabaseMode = Field(default=DatabaseMode.SQLITE)
    database_url: str | None = Field(default=None)
    database_path: Path = Field(default=Path("bb-paxdata.db"))
    alembic_ini_path: Path = Field(default=Path("alembic.ini"))
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_pool_timeout: int = Field(default=30, ge=5, le=300)

    # ── AI / LLM ─────────────────────────────────────────────────────────
    ai_provider: AIProvider = Field(default=AIProvider.OLLAMA)
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    gemini_api_key: SecretStr = Field(default=SecretStr(""))
    groq_api_key: SecretStr = Field(default=SecretStr(""))
    ollama_base_url: str = Field(default="http://localhost:11434")
    ai_model: str = Field(default="claude-3-5-sonnet-20241022")
    ai_timeout: int = Field(default=120, ge=1, le=600)
    ai_max_retries: int = Field(default=3, ge=0, le=10)

    # ── İş Akışı ─────────────────────────────────────────────────────────
    batch_size: int = Field(default=10, ge=1, le=500)
    json_recovery_level: int = Field(default=6, ge=0, le=6)

    # ── Eski Sistem (Migration için kritik) ───────────────────────────────
    legacy_db_path: Path | None = Field(default=None)
    legacy_data_root: Path | None = Field(default=None)
    legacy_schema_version: str = Field(default="5.8")  # Esneklik için

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("database_url", mode="before")
    @classmethod
    def _build_database_url(cls, v: str | None, info: Any) -> str | None:
        """SQLite için URL otomatik üretir; dışarıdan verilmişse dokunmaz."""
        if v is not None:
            return v
        mode = info.data.get("database_mode", DatabaseMode.SQLITE)
        if mode == DatabaseMode.SQLITE:
            path = info.data.get("database_path", Path("bb-paxdata.db"))
            abs_path = Path(path).expanduser().resolve()
            return f"sqlite+aiosqlite:///{abs_path}"
        return None  # PostgreSQL URL zorunlu; model_validator kontrol eder

    @field_validator(
        "legacy_db_path", "legacy_data_root", "database_path", mode="after"
    )
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
                "DATABASE_MODE=postgresql için BBPAX_DATABASE_URL zorunludur.\n"
                "Örnek: postgresql+asyncpg://user:pass@localhost/bbpaxdata"
            )
        return self

    @model_validator(mode="after")
    def _validate_ai_key_present(self) -> Settings:
        """AI provider seçilmişse ilgili API key'in tanımlı olduğunu kontrol eder."""
        key_map = {
            AIProvider.ANTHROPIC: self.anthropic_api_key,
            AIProvider.GEMINI: self.gemini_api_key,
            AIProvider.GROQ: self.groq_api_key,
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

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_async_db(self) -> bool:
        if self.database_url is None:
            return False
        return "aiosqlite" in self.database_url or "asyncpg" in self.database_url

    @property
    def has_legacy_config(self) -> bool:
        return self.legacy_db_path is not None and self.legacy_db_path.exists()

    @property
    def active_ai_api_key(self) -> str:
        """Seçili provider'ın API key'ini döndürür."""
        key_map = {
            AIProvider.ANTHROPIC: self.anthropic_api_key,
            AIProvider.GEMINI: self.gemini_api_key,
            AIProvider.GROQ: self.groq_api_key,
        }
        secret = key_map.get(self.ai_provider)
        return secret.get_secret_value() if secret else ""

    @property
    def is_test_environment(self) -> bool:
        return self.environment == "test"


# ── Singleton Yönetimi ────────────────────────────────────────────────────

_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Global settings singleton.
    Test ortamında `reset_settings()` ile temizlenebilir.
    CI/CD'de BBPAX_ENVIRONMENT=test ile test moduna alınır.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
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
