from __future__ import annotations

import enum


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseMode(str, enum.Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class AIProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"


class MigrationStatus(str, enum.Enum):
    """Migration process state machine."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some batches failed
