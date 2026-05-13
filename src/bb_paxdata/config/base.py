"""
Base configuration for BB-PAXDATA.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Global settings for BB-PAXDATA.
    """

    model_config = SettingsConfigDict(env_prefix="BB_")

    # SpaCy configuration
    USE_SPACY: bool = True
    SPACY_BATCH_SIZE: int = 50

    # AI Backend configuration
    ai_backend: str = "local"
    ai_model: str | None = None
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
