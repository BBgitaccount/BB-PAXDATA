"""
BB-PAXDATA için prompt versiyonlama ve hash sistemi.
"""

import difflib
import hashlib
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class PromptEntry:
    """Registry'deki tek bir prompt kaydı."""

    name: str
    version: str
    template: str
    hash: str
    description: str
    created_at: datetime
    tags: tuple[str, ...]
    prompt_version: str


class PromptRegistry:
    """
    BB-PAXDATA için prompt versiyonlama ve hash sistemi.

    Kullanım:
        registry = PromptRegistry()
        registry.register(
            name="sentence_analysis",
            version="v1.0",
            template=SENTENCE_ANALYSIS_PROMPT,
            description="Cümle bazlı diplomatik analiz — 28 alan",
            tags=("sentence", "diplomatic", "turkish"),
        )
        entry = registry.get("sentence_analysis")
        print(entry.prompt_version)  # "sentence_analysis:v1.0:a3f9b2c1e8d47f20"
    """

    def __init__(self) -> None:
        """Registry'yi başlatır."""
        self._lock = threading.RLock()
        self._entries: dict[str, dict[str, PromptEntry]] = {}
        self._latest_versions: dict[str, str] = {}

    def register(
        self,
        name: str,
        version: str,
        template: str,
        description: str = "",
        tags: tuple[str, ...] = (),
    ) -> PromptEntry:
        """Yeni bir prompt kaydeder.
        Aynı name+version zaten varsa ValueError fırlatır.
        """
        with self._lock:
            if name in self._entries and version in self._entries[name]:
                raise ValueError(
                    f"Prompt '{name}' version '{version}' is already registered."
                )

            hash_val = hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]
            prompt_version = f"{name}:{version}:{hash_val}"
            created_at = datetime.now(UTC)

            entry = PromptEntry(
                name=name,
                version=version,
                template=template,
                hash=hash_val,
                description=description,
                created_at=created_at,
                tags=tags,
                prompt_version=prompt_version,
            )

            if name not in self._entries:
                self._entries[name] = {}

            self._entries[name][version] = entry
            self._latest_versions[name] = version

            return entry

    def get(self, name: str, version: str | None = None) -> PromptEntry:
        """
        Prompt'u döndürür.
        version=None ise en son version'ı döndürür.
        Bulunamazsa KeyError fırlatır.
        """
        with self._lock:
            if name not in self._entries:
                raise KeyError(f"Prompt '{name}' not found in registry.")

            if version is None:
                if name not in self._latest_versions:
                    raise KeyError(f"No versions available for prompt '{name}'.")
                version = self._latest_versions[name]

            if version not in self._entries[name]:
                raise KeyError(f"Prompt '{name}' version '{version}' not found.")

            return self._entries[name][version]

    def get_version_string(self, name: str, version: str | None = None) -> str:
        """
        Sadece prompt_version string'ini döndürür.
        DB kayıtlarına eklemek için kullanılır.
        Örnek dönüş: "sentence_analysis:v1.0:a3f9b2c1e8d47f20"
        """
        return self.get(name, version).prompt_version

    def list_all(self) -> list[PromptEntry]:
        """Tüm kayıtlı prompt'ları listeler (name'e göre sıralı)."""
        with self._lock:
            all_entries = []
            for name in sorted(self._entries.keys()):
                for version in sorted(self._entries[name].keys()):
                    all_entries.append(self._entries[name][version])
            return all_entries

    def list_versions(self, name: str) -> list[PromptEntry]:
        """Belirli bir prompt'un tüm versiyonlarını listeler (en yeniden en eskiye)."""
        with self._lock:
            if name not in self._entries:
                return []

            sorted_versions = sorted(self._entries[name].keys(), reverse=True)
            return [self._entries[name][v] for v in sorted_versions]

    def diff(self, name: str, version_a: str, version_b: str) -> dict[str, str]:
        """
        İki versiyon arasındaki farkı döndürür.
        Dönüş: {"version_a": "...", "version_b": "...", "diff": "..."}
        """
        entry_a = self.get(name, version_a)
        entry_b = self.get(name, version_b)

        diff_lines = list(
            difflib.unified_diff(
                entry_a.template.splitlines(keepends=True),
                entry_b.template.splitlines(keepends=True),
                fromfile=f"{name}:{version_a}",
                tofile=f"{name}:{version_b}",
                n=3,
            )
        )

        return {
            "version_a": entry_a.version,
            "version_b": entry_b.version,
            "hash_a": entry_a.hash,
            "hash_b": entry_b.hash,
            "diff": "".join(diff_lines),
        }

    def export_manifest(self) -> dict[str, Any]:
        """
        Tüm prompt'ların versiyonlarını JSON-serializable dict olarak döndürür.
        CI/CD'de prompt drift tespiti için kullanılır.
        """
        with self._lock:
            manifest: dict[str, Any] = {
                "exported_at": datetime.now(UTC).isoformat(),
                "prompts": {},
            }

            for name in sorted(self._entries.keys()):
                manifest["prompts"][name] = []
                for version in sorted(self._entries[name].keys()):
                    entry = self._entries[name][version]
                    manifest["prompts"][name].append(
                        {
                            "version": entry.version,
                            "hash": entry.hash,
                            "prompt_version": entry.prompt_version,
                        }
                    )

            return manifest


_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    """Global PromptRegistry singleton döndürür."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
        _register_defaults(_registry)
    return _registry


def _register_defaults(registry: PromptRegistry) -> None:
    """
    BB-PAXDATA'nın 5 temel prompt tipini placeholder template ile kaydet.
    Gerçek template metinleri FAZ 7'de application/commands/ katmanına taşındığında
    buradaki placeholder'lar güncellenecek.
    """
    registry.register(
        name="sentence_analysis",
        version="v1.0",
        template=(
            "Sen BB-PAXDATA diplomatik söylem analiz sisteminin AI motorusun.\n"
            "Verilen cümleyi {context} bağlamında analiz et ve JSON döndür.\n"
            "# [PLACEHOLDER — FAZ7'de tam template buraya gelecek]"
        ),
        description="Cümle bazlı diplomatik analiz — 28 alan, negasyon-farkındalıklı",
        tags=("sentence", "diplomatic", "turkish", "json-output"),
    )
    registry.register(
        name="segment_insight",
        version="v1.0",
        template=(
            "Segment özetini ve içgörülerini üret.\n"
            "{segment_text}\n"
            "# [PLACEHOLDER — FAZ7'de tam template buraya gelecek]"
        ),
        description="Segment özet ve içgörü — SBI/DKI dahil",
        tags=("segment", "summary", "diplomatic"),
    )
    registry.register(
        name="demand_analysis",
        version="v1.0",
        template=(
            "Talep analizi: {demand_verb} — {full_sentence}\n"
            "# [PLACEHOLDER — FAZ7'de tam template buraya gelecek]"
        ),
        description="Talep gelecek risk ve alt metin analizi",
        tags=("demand", "future-risk", "subtext"),
    )
    registry.register(
        name="panel_synthesis",
        version="v1.0",
        template=(
            "Panel {panel_id} için sentez üret.\n"
            "# [PLACEHOLDER — FAZ7'de tam template buraya gelecek]"
        ),
        description="Panel düzeyi AI sentezi (G-04)",
        tags=("panel", "synthesis"),
    )
    registry.register(
        name="fail_check",
        version="v1.0",
        template=(
            "Logic FAIL analizi: {check_type} — {sent_id}\n"
            "# [PLACEHOLDER — FAZ7'de tam template buraya gelecek]"
        ),
        description="Logic FAIL derin analiz ve formül-AI uyumsuzluk açıklaması",
        tags=("fail", "validation", "negation"),
    )
