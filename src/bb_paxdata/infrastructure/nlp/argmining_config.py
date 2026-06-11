"""
Argument Mining Pipeline Configuration
Centralized settings with environment variable support and validation.
"""

from __future__ import annotations

import os
from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator


class ClaimDetectionConfig(BaseModel):
    """Configuration for claim identification classifier."""

    model_name: str = Field(
        default="microsoft/deberta-v3-base",
        description="Transformer model for binary claim/non-claim classification",
    )
    fine_tuned_path: str | None = Field(
        default=None,
        description="Path to fine-tuned model weights (overrides base model)",
    )
    confidence_threshold: float = Field(
        default=0.78,
        ge=0.5,
        le=0.99,
        description="Minimum confidence to classify segment as CLAIM",
    )
    max_tokens: int = Field(
        default=512,
        ge=128,
        le=2048,
        description="Maximum sequence length for tokenizer",
    )
    use_srl_guidance: bool = Field(
        default=True,
        description="Use SRL ARG1 spans as additional features for claim detection",
    )


class RelationClassificationConfig(BaseModel):
    """Configuration for pairwise relation classifier."""

    model_name: str = Field(
        default="microsoft/deberta-v3-base",
        description="Model for SUPPORT/ATTACK/REBUTTAL classification",
    )
    confidence_threshold: float = Field(
        default=0.65,
        ge=0.4,
        le=0.99,
        description="Minimum confidence to accept relation prediction",
    )
    neutral_threshold: float = Field(
        default=0.55, description="Below this, classify as NEUTRAL (no edge created)"
    )
    max_pairs_per_claim: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Limit candidate pairs to prevent quadratic blowup",
    )
    use_attention_pooling: bool = Field(
        default=True, description="Use attention mechanism for pair representation"
    )


class EDUSegmentationConfig(BaseModel):
    """Configuration for Elementary Discourse Unit segmentation."""

    method: Literal["rst", "spacy", "hybrid"] = Field(
        default="hybrid", description="Segmentation strategy"
    )
    rst_parser_endpoint: str | None = Field(
        default=None, description="URL for RST parser service (if external)"
    )
    min_segment_length: int = Field(
        default=10, ge=3, description="Minimum characters for valid EDU"
    )
    max_segment_length: int = Field(
        default=500, le=2000, description="Maximum characters before forced split"
    )
    merge_short_segments: bool = Field(
        default=True, description="Merge segments shorter than minimum into neighbors"
    )


class ArgumentMiningPipelineConfig(BaseModel):
    """Top-level configuration aggregating all sub-components."""

    # Sub-configurations
    claim_detection: ClaimDetectionConfig = Field(default_factory=ClaimDetectionConfig)
    relation_classification: RelationClassificationConfig = Field(
        default_factory=RelationClassificationConfig
    )
    edu_segmentation: EDUSegmentationConfig = Field(
        default_factory=EDUSegmentationConfig
    )

    # Infrastructure
    device: Literal["auto", "cpu", "cuda", "mps"] = Field(
        default="auto", description="Compute device"
    )
    batch_size: int = Field(default=16, ge=1, le=64, description="Inference batch size")
    enable_cache: bool = Field(default=True, description="Enable result caching")
    cache_ttl_hours: int = Field(
        default=48, ge=1, le=168, description="Cache time-to-live"
    )

    # Reliability
    timeout_seconds: float = Field(
        default=30.0, ge=5.0, le=120.0, description="Per-document processing timeout"
    )
    max_retries: int = Field(
        default=2, ge=0, le=5, description="Retry count for transient failures"
    )

    # Quality Control
    require_srl_for_claims: bool = Field(
        default=False, description="If True, skip claim detection when SRL unavailable"
    )
    validate_dag_on_build: bool = Field(
        default=True,
        description="Enforce acyclic graph constraint (removes weak edges if needed)",
    )
    max_graph_nodes: int = Field(
        default=10000,
        ge=100,
        le=50000,
        description="Maximum nodes before truncation warning",
    )

    @field_validator("device")
    @classmethod
    def resolve_device(cls, v: str) -> str:
        """Auto-detect best device."""
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
    def from_env(cls) -> ArgumentMiningPipelineConfig:
        """Load from environment variables."""
        return cls(
            claim_detection=ClaimDetectionConfig(
                confidence_threshold=float(
                    os.getenv("ARGMINING_CLAIM_THRESHOLD", "0.78")
                ),
                use_srl_guidance=os.getenv("ARGMINING_USE_SRL", "true").lower()
                == "true",
            ),
            relation_classification=RelationClassificationConfig(
                confidence_threshold=float(os.getenv("ARGMINING_REL_THRESHOLD", "0.65"))
            ),
            edu_segmentation=EDUSegmentationConfig(
                method=cast(
                    Literal["rst", "spacy", "hybrid"],
                    os.getenv("ARGMINING_EDU_METHOD", "hybrid"),
                )
            ),
            device=cast(
                Literal["auto", "cpu", "cuda", "mps"],
                os.getenv("ARGMINING_DEVICE", "auto"),
            ),
            enable_cache=os.getenv("ARGMINING_CACHE", "true").lower() == "true",
            validate_dag_on_build=os.getenv("ARGMINING_VALIDATE_DAG", "true").lower()
            == "true",
        )


# Global singleton
_config_instance: ArgumentMiningPipelineConfig | None = None


def get_argmining_config() -> ArgumentMiningPipelineConfig:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ArgumentMiningPipelineConfig.from_env()
    return _config_instance
