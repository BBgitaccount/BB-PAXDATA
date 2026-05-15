"""
Configuration module for BB-PAXDATA.

Contains logging configuration and other setup utilities.
"""

from .logging import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]
