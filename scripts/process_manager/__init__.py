"""
Process Manager Package - Docker alternative for BB-PAXDATA service orchestration.
"""

from .config import SERVICES, ServiceConfig, get_service_config, get_startup_order
from .log_manager import LogManager
from .process_manager import ProcessInstance, ProcessManager

__all__ = [
    "SERVICES",
    "LogManager",
    "ProcessInstance",
    "ProcessManager",
    "ServiceConfig",
    "get_service_config",
    "get_startup_order",
]

__version__ = "1.0.0"
