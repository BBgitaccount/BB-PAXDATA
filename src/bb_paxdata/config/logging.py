"""
Structlog configuration for BB-PAXDATA.

JSON ve pretty konsol çıktısı desteği ile yapılandırılmış logging.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

try:
    import structlog
    from structlog.dev import ConsoleRenderer
    from structlog.processors import JSONRenderer

    STRUCTLOG_AVAILABLE = True
except ImportError:
    structlog = None
    JSONRenderer = None
    ConsoleRenderer = None
    STRUCTLOG_AVAILABLE = False


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

    if not STRUCTLOG_AVAILABLE:
        # Fallback to standard logging
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )
        _configured = True
        return

    # Log seviyesini belirle
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Ortak processor'lar
    shared_processors = [
        structlog.contextvars.merge_contextvars,  # contextvars entegrasyonu
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Renderer seçimi
    if pretty:
        renderer = ConsoleRenderer(colors=True)
    else:
        renderer = JSONRenderer()

    # Structlog yapılandırması
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # stdlib logging'i de structlog'a yönlendir
    # (httpx, sqlalchemy gibi üçüncü parti logları da yakalanır)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Session_id context'e ekle
    if session_id:
        structlog.contextvars.bind_contextvars(session_id=session_id)

    # Dosyaya yazma
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Dosyaya her zaman JSON yaz (pretty bağımsız)
        file_formatter = logging.Formatter("%(message)s")
        file_handler.setFormatter(file_formatter)

        logging.getLogger().addHandler(file_handler)

    _configured = True


def get_logger(name: str, **initial_context: Any) -> Any:
    """
    Modüllerin `structlog.get_logger(__name__)` yerine kullanabileceği
    kısa yol. initial_context varsa bind eder.

    Kullanım:
        logger = get_logger(__name__, component="batch")
    """
    if not STRUCTLOG_AVAILABLE:
        # Fallback to standard logging
        return logging.getLogger(name)

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
