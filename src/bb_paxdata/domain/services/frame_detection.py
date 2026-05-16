# src/bb_paxdata/domain/services/frame_detection.py
from typing import Protocol, runtime_checkable

from bb_paxdata.domain.models.frame_annotation import (
    FiveWOneH,
    FrameAnnotation,
    ResolvedEntity,
)
from bb_paxdata.domain.models.segment import Segment


@runtime_checkable
class ConceptExtractorProtocol(Protocol):
    """Protocol for target concept extraction following Hamborg (2023)."""

    async def extract_concepts(self, segment: Segment) -> list[str]: ...


@runtime_checkable
class CoreferenceResolverProtocol(Protocol):
    """Protocol for coreference resolution following Hamborg (2023)."""

    async def resolve(self, segment: Segment) -> list[ResolvedEntity]: ...


@runtime_checkable
class EmbeddingFrameMatcherProtocol(Protocol):
    """Protocol for embedding-based frame matching following Hamborg (2023)."""

    async def match_frames(
        self,
        segment: Segment,
        concepts: list[str],
        frame_embeddings: dict[str, list[float]],
    ) -> list[FrameAnnotation]: ...


@runtime_checkable
class FiveWOneHExtractorProtocol(Protocol):
    """Protocol for 5W1H extraction following Hamborg (2023)."""

    async def extract(self, segment: Segment) -> FiveWOneH: ...
