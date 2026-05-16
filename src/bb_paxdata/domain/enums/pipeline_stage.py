from __future__ import annotations

from enum import StrEnum


class PipelineStage(StrEnum):
    """BB-PAXDATA analiz pipeline aşamaları."""

    COLLECT = "collect"
    ASSEMBLE = "assemble"
    DETECT = "detect"
    FINALIZE = "finalize"
