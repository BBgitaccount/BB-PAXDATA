from __future__ import annotations

import enum


class LogLevel(enum.StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseMode(enum.StrEnum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class AIProvider(enum.StrEnum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"
