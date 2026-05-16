from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.domain.enums.pipeline_stage import PipelineStage

if TYPE_CHECKING:
    pass


class PromptVersion(BaseModel):
    """Versiyonlanmış prompt kaydı.

    Her promptun SHA256 hash'i ve akademik referansı audit trail
    içinde saklanır. `frozen=True` ile immutable garantisi verir.

    Reference:
        - CONTEXT.md Bölüm 4.C: Prompt Registry & Audit Trail
        - ACADEMIC_FOUNDATIONS.md Bölüm 11: Master Map
    """

    model_config = ConfigDict(frozen=True)

    version_id: str = Field(..., description="Örn: 'diplomatic@v2.1'")
    content: str = Field(..., description="Prompt şablonunun ham içeriği")
    content_hash: str = Field(..., description="SHA256(content) hex digest")
    academic_ref: str | None = Field(
        default=None,
        description="ACADEMIC_FOUNDATIONS.md citation key. Örn: 'Entman1993'",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def compute_hash(cls, content: str) -> str:
        """Deterministic SHA256 hash üretimi."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class AcademicRefTrace(BaseModel):
    """Bir analizde kullanılan promptların akademik soy ağacı (lineage).

    Faz 0'da bu model tanımlanır; pipeline entegrasyonu Faz 1+'da
    `AnalysisPipeline` finalize aşamasında otomatik doldurulur.
    """

    model_config = ConfigDict(frozen=True)

    analysis_id: UUID
    prompt_version_id: str
    prompt_content_hash: str
    academic_ref: str | None
    pipeline_stage: PipelineStage


class PromptRegistry(Protocol):
    """Prompt versiyonlama ve akademik referans izleme arayüzü.

    Somut implementasyonlar (örn. `SQLitePromptRegistry`) Faz 1'de
    `infrastructure/repositories/` altında yazılacaktır.
    """

    async def register(
        self,
        name: str,
        content: str,
        academic_ref: str | None = None,
    ) -> PromptVersion:
        """Yeni bir prompt kaydeder."""
        ...

    async def get(
        self,
        name: str,
        version: str | None = None,
    ) -> PromptVersion | None:
        """Prompt'u döndürür. version=None ise en sonuncuyu döner."""
        ...

    async def list_versions(self, name: str) -> list[PromptVersion]:
        """Bir promptun tüm versiyonlarını listeler."""
        ...

    async def get_academic_lineage(
        self,
        analysis_id: UUID,
    ) -> list[AcademicRefTrace]:
        """Bir analizde kullanılan tüm promptların akademik referanslarını döner."""
        ...

    def get_version_string(self, name: str, version: str | None = None) -> str | None:
        """Prompt'un versiyon string'ini (vX.Y) döner."""
        ...


ALLOWED_ACADEMIC_REFS: frozenset[str] = frozenset(
    {
        "Grimmer2013",
        "SalagerMeyer1997",
        "Hyland1998",
        "Iyengar1991",
        "Entman1993",
    }
)


# Faz 0'da somut implementasyon olarak mevcut mantığı koruyup yeni modellere adapte ediyoruz.
class InMemoryPromptRegistry:
    """Bellek içi PromptRegistry implementasyonu."""

    def __init__(self) -> None:
        self._prompts: dict[str, dict[str, PromptVersion]] = {}

    async def register(
        self,
        name: str,
        content: str,
        academic_ref: str | None = None,
    ) -> PromptVersion:
        if name not in self._prompts:
            self._prompts[name] = {}

        # Versiyonlama mantığı: Eğer hiç yoksa v1.0, varsa increment (basit tutulmuştur)
        version_num = len(self._prompts[name]) + 1
        version_id = f"{name}@v{version_num}.0"

        content_hash = PromptVersion.compute_hash(content)

        version = PromptVersion(
            version_id=version_id,
            content=content,
            content_hash=content_hash,
            academic_ref=academic_ref,
        )
        self._prompts[name][version_id] = version
        return version

    async def get(
        self,
        name: str,
        version: str | None = None,
    ) -> PromptVersion | None:
        if name not in self._prompts:
            return None

        if version is None:
            # En son versiyonu al
            sorted_versions = sorted(self._prompts[name].keys())
            if not sorted_versions:
                return None
            version = sorted_versions[-1]

        return self._prompts[name].get(version)

    async def list_versions(self, name: str) -> list[PromptVersion]:
        if name not in self._prompts:
            return []
        return list(self._prompts[name].values())

    async def get_academic_lineage(
        self,
        analysis_id: UUID,
    ) -> list[AcademicRefTrace]:
        # Faz 0'da bu metod için somut bir veri kaynağı yok, boş liste döner.
        return []

    def get_version_string(self, name: str, version: str | None = None) -> str | None:
        if name not in self._prompts:
            return None

        if version is None:
            sorted_versions = sorted(self._prompts[name].keys())
            if not sorted_versions:
                return None
            return sorted_versions[-1]

        pv = self._prompts[name].get(version)
        return pv.version_id if pv else None


_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    """PromptRegistry singleton'ını döndürür."""
    global _registry
    if _registry is None:
        registry = InMemoryPromptRegistry()
        # Not: Faz 0'da register_defaults asenkron olduğu için burada
        # bir sorun olabilir. Ancak bu bir singleton init olduğu için
        # ve Faz 0'da her şey mock olduğu için basit tutuyoruz.
        # Gerçek uygulamada bu init süreci uygulama başlangıcında yapılır.
        _registry = registry
    return _registry


async def register_defaults(registry: PromptRegistry) -> None:
    """BB-PAXDATA varsayılan promptlarını kaydeder."""
    await registry.register(
        name="sentence_analysis",
        content="Cümle bazlı diplomatik analiz template",
        academic_ref="Entman1993",
    )
    await registry.register(
        name="segment_insight",
        content="Segment özet ve içgörü template",
        academic_ref="Grimmer2013",
    )
