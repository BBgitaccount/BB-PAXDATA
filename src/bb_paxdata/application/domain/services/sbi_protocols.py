from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np

    from ..models.sbi_models import SBIResult, SpeakerPosition, WordfishParams


@runtime_checkable
class WordfishProtocol(Protocol):
    """Protocol for latent position scaling via Wordfish EM."""

    @abstractmethod
    async def fit_transform(
        self,
        doc_term_matrix: np.ndarray,  # shape: (n_docs, n_terms)
        document_ids: list[str],
        params: WordfishParams | None = None,
    ) -> dict[str, float]:
        """Return mapping of document_id → θᵢ (latent position)."""
        ...


@runtime_checkable
class WordscoresProtocol(Protocol):
    """Protocol for a-priori calibrated text scaling."""

    @abstractmethod
    async def calibrate(
        self,
        doc_term_matrix: np.ndarray,
        reference_scores: dict[str, float],  # document_id → a_priori score
        target_ids: list[str],
        all_document_ids: list[str],
    ) -> dict[str, float]:
        """Return mapping of target_id → T_k (calibrated position)."""
        ...


@runtime_checkable
class StanceDensityProtocol(Protocol):
    """Protocol for Biber-style stance marker density."""

    @abstractmethod
    async def calculate(self, tokens: list[str], speaker_id: str) -> float:
        """Return stance density score ∈ [0, ∞)."""
        ...


@runtime_checkable
class EngagementScorerProtocol(Protocol):
    """Protocol for Martin & White Appraisal Theory engagement analysis."""

    @abstractmethod
    async def score(self, sentences: list[str], speaker_id: str) -> float:
        """Return engagement score ∈ [0, 1]."""
        ...


@runtime_checkable
class SBICalculatorProtocol(Protocol):
    """Protocol for composite SBI calculation."""

    @abstractmethod
    async def compute(
        self,
        speaker_data: list[SpeakerPosition],
        weights: tuple[float, float, float] = (0.6, 0.25, 0.15),
    ) -> SBIResult:
        """Compute the composite Speaker-Based Index."""
        ...
