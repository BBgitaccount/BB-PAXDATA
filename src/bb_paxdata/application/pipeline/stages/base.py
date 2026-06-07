# src/bb_paxdata/application/pipeline/stages/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from bb_paxdata.application.domain.models.analysis import Analysis

if TYPE_CHECKING:
    from bb_paxdata.application.pipeline.models.collect_result import CollectResult
    from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult


class BaseAssemblyStage(ABC):
    """Base class for pipeline ASSEMBLE stages."""

    @abstractmethod
    async def process(self, analysis: Analysis) -> Analysis:
        raise NotImplementedError


class BaseFinalizeStage(ABC):
    """Base class for pipeline FINALIZE stages."""

    @abstractmethod
    async def process(self, session: Any, analysis: Analysis) -> Analysis:
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        analysis: Analysis,
        collect_result: CollectResult,
        success: bool,
        errors: list[str],
        session: Any = None,
    ) -> PipelineResult:
        raise NotImplementedError
