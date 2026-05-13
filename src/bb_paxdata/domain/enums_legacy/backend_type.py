from enum import Enum


class BackendType(str, Enum):
    LOCAL = "local"
    API = "api"
    GEMINI = "gemini"
    GROQ = "groq"
