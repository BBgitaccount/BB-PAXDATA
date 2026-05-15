# ============================================================
# DOSYA: src/bb_paxdata/domain/services/protocols.py
# AÇIKLAMA: Servis arayüzleri — structural typing (Protocol)
# ============================================================

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..enums import RiskLevel
from ..models.ai_analysis import AIAnalysisResult
from ..models.analysis import Analysis


@dataclass(frozen=True)
class AnomalyResult:
    """CrossAnomalyService.detect() metodunun dönüş tipi."""

    score: float  # [0.0, 1.0]
    flags: list[str]  # Tetiklenen kural mesajları
    risk_level: RiskLevel
    triggered_count: int = 0


@runtime_checkable
class NERServiceProtocol(Protocol):
    async def extract(self, text: str, language: str | None = None) -> dict[str, Any]:
        """{"entities": [...], "language": str} döner."""
        ...


@runtime_checkable
class TokenizerProtocol(Protocol):
    async def tokenize(self, text: str, language: str | None = None) -> dict[str, Any]:
        """{"tokens": [...], "sentences": [...], "sentence_count": int, "language": str} döner."""
        ...


@runtime_checkable
class AIAnalystProtocol(Protocol):
    async def analyze(
        self,
        text: str,
        prompt_id: str | None = None,
        forced_version: str | None = None,
        language: str | None = None,
    ) -> AIAnalysisResult: ...


@runtime_checkable
class AnomalyServiceProtocol(Protocol):
    async def detect(self, analysis: Analysis) -> AnomalyResult: ...
