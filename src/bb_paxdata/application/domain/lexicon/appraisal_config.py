from __future__ import annotations

import os

from pydantic import BaseModel, Field


class AppraisalPipelineConfig(BaseModel):
    """Configuration for the Appraisal Theory Vector service."""

    classifier_model_name: str = Field(
        default="cross-encoder/nli-deberta-v3-base",
        description="Zero-shot NLI classifier model name",
    )
    use_classifier: bool = Field(
        default=False, description="Whether to use classifier mode"
    )
    fine_tuned_path: str | None = Field(
        default=None, description="Path to fine-tuned appraisal model"
    )
    srl_argm_mod_graduation_boost: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Boost applied to graduation force when SRL modal verb exists",
    )
    cache_max_entries: int = Field(
        default=5000,
        ge=10,
        le=100000,
        description="Maximum LRU cache entries for AppraisalService",
    )

    @classmethod
    def from_env(cls) -> AppraisalPipelineConfig:
        return cls(
            classifier_model_name=os.getenv(
                "APPRAISAL_CLASSIFIER_MODEL", "cross-encoder/nli-deberta-v3-base"
            ),
            use_classifier=os.getenv("APPRAISAL_USE_CLASSIFIER", "false").lower()
            == "true",
            fine_tuned_path=os.getenv("APPRAISAL_FINE_TUNED_PATH", None),
            srl_argm_mod_graduation_boost=float(
                os.getenv("APPRAISAL_SRL_BOOST", "0.2")
            ),
            cache_max_entries=int(os.getenv("APPRAISAL_CACHE_MAX", "5000")),
        )


_config_instance: AppraisalPipelineConfig | None = None


def get_appraisal_config() -> AppraisalPipelineConfig:
    global _config_instance
    if _config_instance is None:
        from bb_paxdata.config.settings import get_settings

        _config_instance = get_settings().appraisal
    return _config_instance
