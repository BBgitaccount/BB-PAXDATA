from __future__ import annotations

from pathlib import Path

import pytest
from bb_paxdata.config.settings import (
    Settings,
    get_settings,
    override_settings,
    reset_settings,
)
from bb_paxdata.domain.enums import AIProvider, DatabaseMode, LogLevel


class TestDefaultValues:
    def test_app_name_frozen(self) -> None:
        s = Settings()
        with pytest.raises(Exception):  # ValidationError veya AttributeError
            s.app_name = "HACKED"  # type: ignore[misc]

    def test_sqlite_url_auto_generated(self) -> None:
        s = Settings(database_path=Path("test.db"))
        assert s.database_url is not None
        assert "aiosqlite" in s.database_url
        assert s.is_async_db is True

    def test_default_ai_provider_is_ollama(self) -> None:
        s = Settings()
        assert s.ai_provider == AIProvider.OLLAMA


class TestPathResolution:
    def test_tilde_expanded(self) -> None:
        s = Settings(legacy_db_path=Path("~/legacy.db"))
        assert s.legacy_db_path is not None
        assert not str(s.legacy_db_path).startswith("~")
        assert s.legacy_db_path.is_absolute()

    def test_relative_database_path_resolved(self) -> None:
        s = Settings(database_path=Path("data/db.sqlite"))
        assert s.database_path.is_absolute()


class TestEnvOverride:
    def test_env_variables_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BBPAX_DEBUG", "true")
        monkeypatch.setenv("BBPAX_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("BBPAX_BATCH_SIZE", "50")
        reset_settings()
        s = get_settings()
        assert s.debug is True
        assert s.log_level == LogLevel.DEBUG
        assert s.batch_size == 50

    def teardown_method(self) -> None:
        reset_settings()


class TestValidation:
    def test_postgresql_without_url_raises(self) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL zorunludur"):
            Settings(database_mode=DatabaseMode.POSTGRESQL, database_url=None)

    def test_batch_size_bounds(self) -> None:
        with pytest.raises(Exception):
            Settings(batch_size=0)
        with pytest.raises(Exception):
            Settings(batch_size=501)


class TestSingleton:
    def setup_method(self) -> None:
        reset_settings()

    def teardown_method(self) -> None:
        reset_settings()

    def test_same_instance_returned(self) -> None:
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_override_settings_replaces_singleton(self) -> None:
        overridden = override_settings(debug=True, batch_size=1)
        assert overridden.debug is True
        assert get_settings() is overridden
