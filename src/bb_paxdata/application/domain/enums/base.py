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
    DEEPSEEK = "deepseek"
