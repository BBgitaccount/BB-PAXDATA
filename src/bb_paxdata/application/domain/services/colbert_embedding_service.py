"""DEPRECATED — ColBERT service moved to infrastructure layer.

This module is kept as a re-export shim for backward compatibility.
All new code must import from:
    bb_paxdata.infrastructure.nlp.colbert_service

TODO(MİMARİ-5): Remove this file after all import sites are migrated.
"""

from __future__ import annotations

import warnings

from bb_paxdata.infrastructure.nlp.colbert_service import RAGatoulleColBERTService

warnings.warn(
    "Importing RAGatoulleColBERTService from application.domain.services is deprecated. "
    "Use bb_paxdata.infrastructure.nlp.colbert_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["RAGatoulleColBERTService"]
