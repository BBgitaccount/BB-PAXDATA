# src/bb_paxdata/application/pipeline/configurator.py
"""Pipeline Stage Configurator.

Provides loading and resolving pipeline configurations from YAML/JSON files,
supporting dynamic variants for A/B testing and A/B test parameter overrides.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "variants": {
        "default": {
            "stages": [
                "pre_process",
                "collect",
                "assemble",
                "detect",
                "dual_gate",
                "finalize",
            ],
            "collect": {
                "lazy_ai_risk_threshold": 0.5,
                "lazy_ai_risk_formula": "max",
                "services": [
                    "ner",
                    "tokenizer",
                    "ai_analyst",
                    "country_collector",
                    "negation_detector",
                    "risk_detector",
                    "power_calculator",
                    "topic_modeling",
                    "frame_pipeline",
                    "lexicon_service",
                    "episodic_classifier",
                    "stance_calculator",
                    "engagement_scorer",
                    "llm_position_estimator",
                    "semantic_shift_calculator",
                ],
            },
            "detect": {"fail_fast_on_missing_ai": False},
            "dual_gate": {"context_window_size": 5},
        },
        "fast_mode": {
            "stages": ["pre_process", "collect", "assemble", "detect", "finalize"],
            "collect": {
                "lazy_ai_risk_threshold": 0.3,
                "lazy_ai_risk_formula": "max",
                "services": [
                    "ner",
                    "tokenizer",
                    "ai_analyst",
                    "country_collector",
                    "negation_detector",
                    "risk_detector",
                    "power_calculator",
                ],
            },
            "detect": {"fail_fast_on_missing_ai": True},
            "dual_gate": {"context_window_size": 0},
        },
        "no_ai_mode": {
            "stages": ["pre_process", "collect", "assemble", "detect", "finalize"],
            "collect": {
                "lazy_ai_risk_threshold": 2.0,
                "lazy_ai_risk_formula": "max",
                "services": [
                    "ner",
                    "tokenizer",
                    "country_collector",
                    "negation_detector",
                    "risk_detector",
                    "power_calculator",
                    "lexicon_service",
                    "episodic_classifier",
                    "stance_calculator",
                    "engagement_scorer",
                ],
            },
            "detect": {"fail_fast_on_missing_ai": False},
            "dual_gate": {"context_window_size": 0},
        },
    }
}


class PipelineConfigurator:
    """Manages loading and resolving pipeline stage and service configurations."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._raw_config = DEFAULT_CONFIG.copy()

        # Determine path
        if config_path is None:
            # Fallback path under project config directory
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = (
                project_root / "src" / "bb_paxdata" / "config" / "pipeline_config.yaml"
            )

        self.config_path = Path(config_path)
        self.load_config()

    def load_config(self) -> None:
        """Load pipeline configuration from YAML/JSON file if exists, fallback to default."""
        if not self.config_path.exists():
            logger.info(
                f"Configuration file not found at {self.config_path}. Using fallback default configuration."
            )
            return

        try:
            content = self.config_path.read_text(encoding="utf-8")
            if self.config_path.suffix in (".yaml", ".yml"):
                loaded = yaml.safe_load(content)
            else:
                loaded = json.loads(content)

            if not isinstance(loaded, dict) or "variants" not in loaded:
                raise ValueError(
                    "Invalid configuration format. Must contain 'variants' key."
                )

            self._raw_config = loaded
            logger.info(f"Loaded pipeline configuration from {self.config_path}")
        except Exception as e:
            logger.error(
                f"Failed to load pipeline configuration from {self.config_path}: {e}. Fallback to defaults."
            )

    def get_config(self, variant: str = "default") -> dict[str, Any]:
        """Retrieve resolved configuration dict for the specified variant."""
        variants = self._raw_config.get("variants", {})
        if variant not in variants:
            logger.warning(
                f"Requested pipeline configuration variant '{variant}' not found. Falling back to 'default'."
            )
            return dict(variants.get("default", DEFAULT_CONFIG["variants"]["default"]))

        return dict(variants[variant])
