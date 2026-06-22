from __future__ import annotations

from pathlib import Path

import pytest

from bb_paxdata.application.domain.enums import AIProvider, DatabaseMode, LogLevel
from bb_paxdata.config.settings import (
    Settings,
    get_settings,
    override_settings,
    reset_settings,
)


class TestDefaultValues:
    def test_app_name_frozen(self) -> None:
        s = Settings(_env_file=None)
        with pytest.raises(Exception):  # ValidationError veya AttributeError
            setattr(s, "app_name", "HACKED")

    def test_sqlite_url_auto_generated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PAXDATA_DATABASE_URL", raising=False)
        monkeypatch.delenv("PAXDATA_DATABASE_MODE", raising=False)
        s = Settings(database_path=Path("test.db"), _env_file=None)
        assert s.database_url is not None
        assert "aiosqlite" in s.database_url
        assert s.is_async_db is True

    def test_default_ai_provider_is_ollama(self) -> None:
        s = Settings(_env_file=None)
        assert s.ai_provider == AIProvider.OLLAMA


class TestPathResolution:
    def test_tilde_expanded(self) -> None:
        s = Settings(database_path=Path("~/test_paxdata.db"), _env_file=None)
        assert s.database_path is not None
        assert not str(s.database_path).startswith("~")
        assert s.database_path.is_absolute()

    def test_relative_database_path_resolved(self) -> None:
        s = Settings(database_path=Path("data/db.sqlite"), _env_file=None)
        assert s.database_path.is_absolute()


class TestEnvOverride:
    def test_env_variables_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PAXDATA_DEBUG", "true")
        monkeypatch.setenv("PAXDATA_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PAXDATA_BATCH_SIZE", "50")
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
        invalid_low: int = 0
        invalid_high: int = 501
        with pytest.raises(Exception):
            Settings(batch_size=invalid_low)
        with pytest.raises(Exception):
            Settings(batch_size=invalid_high)


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


class TestCentralizedNLPConfigs:
    def setup_method(self) -> None:
        reset_settings()

    def teardown_method(self) -> None:
        reset_settings()

    def test_alias_loading_with_paxdata_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAXDATA_SRL_MODEL_NAME", "custom-srl-model")
        monkeypatch.setenv("PAXDATA_ARGMINING_CLAIM_THRESHOLD", "0.85")
        monkeypatch.setenv("PAXDATA_APPRAISAL_USE_CLASSIFIER", "true")
        monkeypatch.setenv("PAXDATA_OPENAI_API_KEY", "test-key-paxdata")

        s = Settings(_env_file=None)
        assert s.srl_model_name == "custom-srl-model"
        assert s.argmining_claim_threshold == 0.85
        assert s.appraisal_use_classifier is True
        assert s.openai_api_key.get_secret_value() == "test-key-paxdata"

    def test_alias_loading_without_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SRL_MODEL_NAME", "custom-srl-flat")
        monkeypatch.setenv("ARGMINING_CLAIM_THRESHOLD", "0.91")
        monkeypatch.setenv("APPRAISAL_USE_CLASSIFIER", "true")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-flat")

        s = Settings(_env_file=None)
        assert s.srl_model_name == "custom-srl-flat"
        assert s.argmining_claim_threshold == 0.91
        assert s.appraisal_use_classifier is True
        assert s.openai_api_key.get_secret_value() == "test-key-flat"

    def test_validation_bounds(self) -> None:
        # SRL Batch size range is [1, 128]
        with pytest.raises(Exception):
            Settings(srl_batch_size=0)
        with pytest.raises(Exception):
            Settings(srl_batch_size=129)

        # Claim threshold range is [0.5, 0.99]
        with pytest.raises(Exception):
            Settings(argmining_claim_threshold=0.4)
        with pytest.raises(Exception):
            Settings(argmining_claim_threshold=1.0)

    def test_sub_config_properties(self) -> None:
        s = Settings(
            srl_model_name="test-srl",
            argmining_claim_threshold=0.88,
            appraisal_srl_argm_mod_graduation_boost=0.3,
            _env_file=None,
        )

        # Verify SRL config properties
        srl_config = s.srl
        assert srl_config.model_name == "test-srl"

        # Verify Argument Mining config properties
        argmining_config = s.argmining
        assert argmining_config.claim_detection.confidence_threshold == 0.88

        # Verify Appraisal config properties
        appraisal_config = s.appraisal
        assert appraisal_config.srl_argm_mod_graduation_boost == 0.3
