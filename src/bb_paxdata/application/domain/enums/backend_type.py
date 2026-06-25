from enum import StrEnum


class BackendType(StrEnum):
    LOCAL = "local"
    API = "api"
    GEMINI = "gemini"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
