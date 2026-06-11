"""DEPRECATED — SpacyPipeline moved to infrastructure layer.

Import from: bb_paxdata.infrastructure.nlp.spacy_pipeline_service

TODO(MİMARİ-5): Remove after all import sites are migrated.
"""

from __future__ import annotations

import warnings

from bb_paxdata.infrastructure.nlp.spacy_pipeline_service import (
    SpacyPipeline,
    SpacyPipelineService,
)

warnings.warn(
    "Importing SpacyPipeline from application.domain.services is deprecated. "
    "Use bb_paxdata.infrastructure.nlp.spacy_pipeline_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["SpacyPipeline", "SpacyPipelineService"]
