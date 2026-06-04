# src/bb_paxdata/sdk/protocols.py
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, field_validator


class PluginMetadata(BaseModel):
    name: str
    version: str  # SemVer: "1.0.0"
    author: str
    min_paxdata_version: str = "5.8.0"  # Uyumluluk alt sınırı
    description: str = ""

    @field_validator("version", "min_paxdata_version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Invalid SemVer: {v}")
        return v


class EvaluationResult(BaseModel):
    anomaly_detected: bool
    confidence: float  # [0.0, 1.0]
    anomaly_type: str | None  # "framing", "hedging", "escalation" vb.
    explanation: str
    metadata: dict = {}


@runtime_checkable
class AnomalyRulePlugin(Protocol):
    metadata: PluginMetadata

    def evaluate(self, text: str, context: dict) -> EvaluationResult:
        """Giriş metnini değerlendirip anomali analiz raporu döner."""
        ...

    def on_load(self) -> None:
        """Plugin yüklendiğinde çağrılır. Kaynak tahsisi burada yapılır."""
        ...

    def on_unload(self) -> None:
        """Plugin kaldırılmadan önce çağrılır. Temizlik burada yapılır."""
        ...
