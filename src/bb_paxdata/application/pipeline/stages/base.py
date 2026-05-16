# src/bb_paxdata/application/pipeline/stages/base.py
from __future__ import annotations

from typing import Any

from bb_paxdata.domain.models.analysis import Analysis


class AssemblyStage:
    """Base class for pipeline ASSEMBLE stages."""

    async def process(self, analysis: Analysis) -> Analysis:
        raise NotImplementedError


class FinalizeStage:
    """Base class for pipeline FINALIZE stages."""

    async def process(self, session: Any, analysis: Analysis) -> Analysis:
        raise NotImplementedError
