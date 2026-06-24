"""APM integration for New Relic and Datadog.

Provides distributed tracing, slow query detection, and error tracking
through APM providers.
"""

from __future__ import annotations

from typing import Any


class APMProvider:
    """Base class for APM providers."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def initialize(self, service_name: str, **kwargs: Any) -> None:
        """Initialize the APM provider."""
        pass

    def record_transaction(self, name: str, duration: float, **attributes: Any) -> None:
        """Record a transaction."""
        pass

    def record_error(self, error: Exception, **attributes: Any) -> None:
        """Record an error."""
        pass

    def shutdown(self) -> None:
        """Shutdown the APM provider."""
        pass


class NewRelicAPM(APMProvider):
    """New Relic APM integration."""

    def __init__(
        self, license_key: str = "", app_name: str = "bb-paxdata", enabled: bool = False
    ) -> None:
        super().__init__(enabled)
        self._license_key = license_key
        self._app_name = app_name
        self._agent = None

    def initialize(self, service_name: str, **kwargs: Any) -> None:
        """Initialize New Relic agent."""
        if not self._enabled or not self._license_key:
            return

        try:
            # New Relic Python agent initialization
            # Note: Requires newrelic package to be installed
            import newrelic.agent

            newrelic.agent.initialize(
                license_key=self._license_key,
                app_name=self._app_name,
                environment=kwargs.get("environment", "production"),
            )
            self._agent = newrelic.agent
        except ImportError:
            # newrelic package not installed, skip silently
            pass
        except Exception:
            # Initialization failed, skip silently
            pass

    def record_transaction(self, name: str, duration: float, **attributes: Any) -> None:
        """Record a transaction in New Relic."""
        if not self._enabled or not self._agent:
            return

        try:
            self._agent.record_custom_event(name, attributes)
        except Exception:
            pass

    def record_error(self, error: Exception, **attributes: Any) -> None:
        """Record an error in New Relic."""
        if not self._enabled or not self._agent:
            return

        try:
            self._agent.notice_error(error, attributes)
        except Exception:
            pass

    def shutdown(self) -> None:
        """Shutdown New Relic agent."""
        if self._agent:
            try:
                self._agent.shutdown_agent()
            except Exception:
                pass


class DatadogAPM(APMProvider):
    """Datadog APM integration."""

    def __init__(
        self, api_key: str = "", service_name: str = "bb-paxdata", enabled: bool = False
    ) -> None:
        super().__init__(enabled)
        self._api_key = api_key
        self._service_name = service_name
        self._tracer = None

    def initialize(self, service_name: str, **kwargs: Any) -> None:
        """Initialize Datadog tracer."""
        if not self._enabled or not self._api_key:
            return

        try:
            from ddtrace import tracer
            from ddtrace.contrib.fastapi import patch as patch_fastapi
            from ddtrace.contrib.sqlalchemy import patch as patch_sqlalchemy

            # Configure Datadog tracer
            tracer.configure(
                hostname=kwargs.get("datadog_host", "localhost"),
                port=kwargs.get("datadog_port", 8126),
                service=self._service_name,
                env=kwargs.get("environment", "production"),
            )

            # Patch common libraries
            patch_fastapi()
            patch_sqlalchemy()

            self._tracer = tracer
        except ImportError:
            # ddtrace package not installed, skip silently
            pass
        except Exception:
            # Initialization failed, skip silently
            pass

    def record_transaction(self, name: str, duration: float, **attributes: Any) -> None:
        """Record a transaction in Datadog."""
        if not self._enabled or not self._tracer:
            return

        try:
            with self._tracer.trace(name) as span:
                for key, value in attributes.items():
                    span.set_tag(key, value)
        except Exception:
            pass

    def record_error(self, error: Exception, **attributes: Any) -> None:
        """Record an error in Datadog."""
        if not self._enabled or not self._tracer:
            return

        try:
            span = self._tracer.current_span()
            if span:
                span.set_tag("error", True)
                span.set_tag("error.message", str(error))
                for key, value in attributes.items():
                    span.set_tag(key, value)
        except Exception:
            pass

    def shutdown(self) -> None:
        """Shutdown Datadog tracer."""
        if self._tracer:
            try:
                self._tracer.shutdown()
            except Exception:
                pass


def setup_apm(
    provider: str = "none",
    **config: Any,
) -> APMProvider:
    """Setup APM provider based on configuration.

    Args:
        provider: APM provider name ("newrelic", "datadog", or "none")
        **config: Provider-specific configuration

    Returns:
        Configured APM provider instance
    """
    if provider == "newrelic":
        return NewRelicAPM(
            license_key=config.get("license_key", ""),
            app_name=config.get("app_name", "bb-paxdata"),
            enabled=config.get("enabled", False),
        )
    elif provider == "datadog":
        return DatadogAPM(
            api_key=config.get("api_key", ""),
            service_name=config.get("service_name", "bb-paxdata"),
            enabled=config.get("enabled", False),
        )
    else:
        return APMProvider(enabled=False)


def get_apm_config_from_settings() -> dict[str, Any]:
    """Get APM configuration from application settings."""
    try:
        from bb_paxdata.config.settings import get_settings

        settings = get_settings()
        return {
            "provider": getattr(settings, "apm_provider", "none"),
            "newrelic_license_key": getattr(settings, "newrelic_license_key", ""),
            "newrelic_app_name": getattr(settings, "newrelic_app_name", "bb-paxdata"),
            "newrelic_enabled": getattr(settings, "newrelic_enabled", False),
            "datadog_api_key": getattr(settings, "datadog_api_key", ""),
            "datadog_service_name": getattr(
                settings, "datadog_service_name", "bb-paxdata"
            ),
            "datadog_enabled": getattr(settings, "datadog_enabled", False),
            "datadog_host": getattr(settings, "datadog_host", "localhost"),
            "datadog_port": getattr(settings, "datadog_port", 8126),
        }
    except Exception:
        return {
            "provider": "none",
            "newrelic_license_key": "",
            "newrelic_app_name": "bb-paxdata",
            "newrelic_enabled": False,
            "datadog_api_key": "",
            "datadog_service_name": "bb-paxdata",
            "datadog_enabled": False,
            "datadog_host": "localhost",
            "datadog_port": 8126,
        }


# Global APM instance
_apm_instance: APMProvider | None = None


def get_apm() -> APMProvider:
    """Get global APM instance."""
    global _apm_instance
    if _apm_instance is None:
        config = get_apm_config_from_settings()
        _apm_instance = setup_apm(**config)
        _apm_instance.initialize("bb-paxdata", **config)
    return _apm_instance
