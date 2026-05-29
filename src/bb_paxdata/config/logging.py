"""
Structlog configuration for BB-PAXDATA.

JSON ve pretty konsol çıktısı desteği ile yapılandırılmış logging.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer
from structlog.types import Processor

# Global flag to prevent multiple configurations
_configured = False


def setup_logging(
    level: str = "INFO",  # "DEBUG" | "INFO" | "WARNING" | "ERROR"
    pretty: bool = True,  # True = renkli konsol, False = JSON satırı
    log_file: Path | None = None,  # Dosyaya da yazmak için
    session_id: str | None = None,  # Her log satırına eklenecek sabit alan
) -> None:
    """
    Tüm uygulama için structlog yapılandırır.
    main() veya CLI entry point'inin en başında bir kez çağrılır.
    """
    global _configured

    if _configured:
        return

    # Ortak processor'lar
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # contextvars entegrasyonu
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Structlog yapılandırması
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Console Handler (pretty / colored or raw JSON)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=ConsoleRenderer(colors=True) if pretty else JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )

    handlers: list[logging.Handler] = [console_handler]

    # File Handler (JSON format)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=JSONRenderer(),
                foreign_pre_chain=shared_processors,
            )
        )
        handlers.append(file_handler)

    # Configure root logger with handlers
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    for h in handlers:
        root_logger.addHandler(h)

    # Set logging level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Session_id context'e ekle
    if session_id:
        structlog.contextvars.bind_contextvars(session_id=session_id)

    _configured = True


def get_logger(name: str, **initial_context: Any) -> Any:
    """
    Modüllerin `structlog.get_logger(__name__)` yerine kullanabileceği
    kısa yol. initial_context varsa bind eder.

    Kullanım:
        logger = get_logger(__name__, component="batch")
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


def is_configured() -> bool:
    """Logging yapılandırıldı mı kontrol et."""
    return _configured


def reset_configuration() -> None:
    """Test için yapılandırmayı sıfırla."""
    global _configured
    _configured = False
