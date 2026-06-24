"""Log shipping configuration for ELK/Loki integration.

Provides configuration for shipping logs to centralized log aggregation systems.
"""

from __future__ import annotations

import json
from typing import Any


class LogShipper:
    """Base class for log shippers."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def ship(self, log_dict: dict[str, Any]) -> None:
        """Ship a log entry to the destination."""
        if not self._enabled:
            return


class LokiLogShipper(LogShipper):
    """Log shipper for Grafana Loki."""

    def __init__(
        self,
        loki_url: str = "http://localhost:3100",
        enabled: bool = False,
        labels: dict[str, str] | None = None,
    ) -> None:
        super().__init__(enabled)
        self._loki_url = loki_url
        self._labels = labels or {"app": "bb-paxdata"}
        self._session = None

    async def ship(self, log_dict: dict[str, Any]) -> None:
        """Ship log to Loki via HTTP API."""
        if not self._enabled:
            return

        try:
            import httpx

            if self._session is None:
                self._session = httpx.AsyncClient(timeout=5.0)

            # Format for Loki push API
            stream = {
                **self._labels,
                "level": log_dict.get("level", "info"),
                "logger": log_dict.get("logger", ""),
            }

            # Add correlation_id if present
            if "correlation_id" in log_dict:
                stream["correlation_id"] = log_dict["correlation_id"]

            # Add trace_id if present
            if "trace_id" in log_dict:
                stream["trace_id"] = log_dict["trace_id"]

            payload = {
                "streams": [
                    {
                        "stream": stream,
                        "values": [
                            [
                                str(int(__import__("time").time() * 1e9)),
                                json.dumps(log_dict),
                            ]
                        ],
                    }
                ]
            }

            await self._session.post(
                f"{self._loki_url}/loki/api/v1/push",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            # Fail silently to avoid breaking application
            pass

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.aclose()


class ELKLogShipper(LogShipper):
    """Log shipper for Elasticsearch/Logstash/Kibana (ELK) stack."""

    def __init__(
        self,
        elasticsearch_url: str = "http://localhost:9200",
        index_name: str = "bb-paxdata-logs",
        enabled: bool = False,
    ) -> None:
        super().__init__(enabled)
        self._elasticsearch_url = elasticsearch_url
        self._index_name = index_name
        self._session = None

    async def ship(self, log_dict: dict[str, Any]) -> None:
        """Ship log to Elasticsearch via HTTP API."""
        if not self._enabled:
            return

        try:
            import httpx

            if self._session is None:
                self._session = httpx.AsyncClient(timeout=5.0)

            # Use daily index pattern
            from datetime import datetime

            index = f"{self._index_name}-{datetime.now().strftime('%Y.%m.%d')}"

            await self._session.post(
                f"{self._elasticsearch_url}/{index}/_doc",
                json=log_dict,
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            # Fail silently to avoid breaking application
            pass

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.aclose()


class StructlogLogShipperProcessor:
    """Structlog processor that ships logs to configured destinations."""

    def __init__(self, shippers: list[LogShipper]) -> None:
        self._shippers = shippers
        self._tasks: set[Any] = set()

    def __call__(
        self, logger: Any, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Process log event and ship to configured destinations."""
        for shipper in self._shippers:
            if shipper.is_enabled():
                # Ship asynchronously without blocking
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    task = loop.create_task(shipper.ship(event_dict.copy()))
                    # Store task reference to prevent garbage collection
                    self._tasks.add(task)
                    # Clean up completed tasks periodically
                    self._tasks = {t for t in self._tasks if not t.done()}
                except RuntimeError:
                    # No event loop running, skip shipping
                    pass
        return event_dict


def setup_log_shipping(
    loki_url: str | None = None,
    loki_enabled: bool = False,
    elk_url: str | None = None,
    elk_enabled: bool = False,
    elk_index: str = "bb-paxdata-logs",
) -> StructlogLogShipperProcessor:
    """Configure log shipping for ELK/Loki.

    Args:
        loki_url: Grafana Loki URL
        loki_enabled: Enable Loki shipping
        elk_url: Elasticsearch URL
        elk_enabled: Enable ELK shipping
        elk_index: Elasticsearch index name prefix

    Returns:
        Structlog processor for log shipping
    """
    shippers: list[LogShipper] = []

    if loki_enabled and loki_url:
        shippers.append(LokiLogShipper(loki_url=loki_url, enabled=True))

    if elk_enabled and elk_url:
        shippers.append(
            ELKLogShipper(elasticsearch_url=elk_url, enabled=True, index_name=elk_index)
        )

    return StructlogLogShipperProcessor(shippers)


def get_log_shipping_config_from_settings() -> dict[str, Any]:
    """Get log shipping configuration from application settings."""
    try:
        from bb_paxdata.config.settings import get_settings

        settings = get_settings()
        return {
            "loki_url": getattr(settings, "loki_url", None),
            "loki_enabled": getattr(settings, "loki_enabled", False),
            "elk_url": getattr(settings, "elk_url", None),
            "elk_enabled": getattr(settings, "elk_enabled", False),
            "elk_index": getattr(settings, "elk_index", "bb-paxdata-logs"),
        }
    except Exception:
        return {
            "loki_url": None,
            "loki_enabled": False,
            "elk_url": None,
            "elk_enabled": False,
            "elk_index": "bb-paxdata-logs",
        }
