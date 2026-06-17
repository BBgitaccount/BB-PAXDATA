"""
SRL Pipeline Configuration
Centralized configuration with environment variable support and validation.
"""

from __future__ import annotations

import os
from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator


class SRLModelConfig(BaseModel):
    """
    Transformer-based SRL model configuration.
    Supports multiple backends and hardware acceleration.
    """

    # Model Selection
    # Primary: bert-base-uncased fine-tuned on Universal PropBank (English SRL, ARG0/ARG1/V BIO tags)
    # Alt-1  : yeomtong/srl_bert_model — BERT tabanlı SRL, token-classification
    # Alt-2  : sapienzanlp/srl-bert-b-semeval2012 — SemEval-2012 OntoNotes SRL
    model_name: str = Field(
        default="dannashao/bert-base-uncased-finetuned-srl_arg",
        description="HuggingFace model identifier for SRL (token-classification, PropBank BIO tags)",
    )
    alternative_models: list[str] = Field(
        default=[
            "yeomtong/srl_bert_model",
            "sapienzanlp/srl-bert-b-semeval2012",
        ],
        description="Fallback models if primary fails",
    )

    # Hardware Acceleration
    device: Literal["auto", "cpu", "cuda", "mps"] = Field(
        default="auto", description="Compute device selection"
    )
    torch_dtype: str = Field(
        default="float32",
        description="PyTorch precision (float16 for faster inference)",
    )
    use_quantization: bool = Field(
        default=False,
        description="Enable INT8 quantization for memory reduction (~50%)",
    )

    # Performance Tuning
    batch_size: int = Field(
        default=32,
        ge=1,
        le=128,
        description="Batch size for inference (higher = faster but more memory)",
    )
    max_sequence_length: int = Field(
        default=512, ge=128, le=2048, description="Maximum token sequence length"
    )

    # Caching Strategy
    enable_cache: bool = Field(
        default=True, description="Enable LRU caching of predictions"
    )
    cache_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        ge=3600,
        le=604800,
        description="Cache time-to-live in seconds",
    )
    cache_max_size: int = Field(
        default=10000, ge=100, le=100000, description="Maximum cached predictions"
    )

    # Reliability
    max_retries: int = Field(
        default=3, ge=1, le=10, description="Max retry attempts on transient failures"
    )
    retry_backoff_base: float = Field(
        default=1.0, ge=0.1, description="Exponential backoff base (seconds)"
    )
    timeout_seconds: float = Field(
        default=120.0,
        ge=5.0,
        le=300.0,
        description="Per-sentence inference timeout (increased for first-time model download)",
    )

    # Quality Thresholds
    min_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to accept a prediction",
    )
    circuit_breaker_threshold: float = Field(
        default=0.2,
        ge=0.05,
        le=0.5,
        description="Failure rate to trigger circuit breaker",
    )
    circuit_breaker_window: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Observation window for circuit breaker",
    )

    @field_validator("device")
    @classmethod
    def resolve_device(cls, v: str) -> str:
        """Auto-detect best available device."""
        if v == "auto":
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
                elif (
                    hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                ):
                    return "mps"
                return "cpu"
            except ImportError:
                return "cpu"
        return v

    @classmethod
    def from_env(cls) -> SRLModelConfig:
        """Load configuration from environment variables with defaults."""
        return cls(
            model_name=os.getenv(
                "SRL_MODEL_NAME", "dannashao/bert-base-uncased-finetuned-srl_arg"
            ),
            device=cast(
                Literal["auto", "cpu", "cuda", "mps"],
                os.getenv("SRL_DEVICE", "auto"),
            ),
            batch_size=int(os.getenv("SRL_BATCH_SIZE", "32")),
            enable_cache=os.getenv("SRL_ENABLE_CACHE", "true").lower() == "true",
            use_quantization=(
                os.getenv("SRL_USE_QUANTIZATION", "false").lower() == "true"
            ),
        )


# Global singleton instance
_config_instance: SRLModelConfig | None = None


def get_srl_config() -> SRLModelConfig:
    """Get or create global SRL configuration instance."""
    global _config_instance
    if _config_instance is None:
        from bb_paxdata.config.settings import get_settings

        _config_instance = get_settings().srl
    return _config_instance
