"""DEPRECATED — GATEmbeddingService moved to infrastructure layer.

Import from: bb_paxdata.infrastructure.nlp.gat_embedding_service

TODO(MİMARİ-5): Remove after all import sites are migrated.
"""

from __future__ import annotations

import warnings

from bb_paxdata.infrastructure.nlp.gat_embedding_service import (
    GATContrastiveTrainer,
    GATEmbeddingService,
    GATNetwork,
)

warnings.warn(
    "Importing GATEmbeddingService from application.domain.services is deprecated. "
    "Use bb_paxdata.infrastructure.nlp.gat_embedding_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["GATContrastiveTrainer", "GATEmbeddingService", "GATNetwork"]
