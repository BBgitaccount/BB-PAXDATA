# ============================================================
# DOSYA: src/bb_paxdata/domain/services/prompt_registry.py
# AÇIKLAMA: Prompt versiyon yaşam döngüsü yönetimi
# ============================================================

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """Tek bir prompt versiyonunun tanımı ve yaşam döngüsü bilgisi."""

    prompt_id: str  # ör: "diplomatic_analysis"
    version: str  # ör: "v2.1"
    template: str  # Prompt şablon metni ({text} placeholder içermeli)
    description: str  # Bu versiyondaki değişikliklerin özeti
    is_active: bool = True
    model_name: str = "gpt-4o"
    created_at: str = ""
    language: str = "any"  # "tr", "en", "any" — dil bazlı seçim için
    academic_ref: str | None = None  # Örn: "Grootendorst2022"

    # OTOMATİK HESAPLANAN ALAN
    template_hash: str = field(init=False, default="")

    def __post_init__(self) -> None:
        """Şablon metninin SHA-256 hash'ini otomatik üretir."""
        self.template_hash = self._compute_hash(self.template)

    @staticmethod
    def _compute_hash(text: str) -> str:
        """SHA-256 hash hesaplar."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[
            :16
        ]  # İlk 16 karakter yeterlidir

    def verify_integrity(self, provided_hash: str) -> bool:
        """Dışarıdan gelen hash'in bu şablonla eşleşip eşleşmediğini kontrol eder."""
        return self.template_hash == provided_hash

    @property
    def hash(self) -> str:
        """Geriye uyumluluk için alias."""
        return self.template_hash

    @property
    def full_version_id(self) -> str:
        """prompt_id@version formatı — Analysis modeline damgalanır."""
        return f"{self.prompt_id}@{self.version}"


class PromptRegistry:
    """
    Prompt versiyon yaşam döngüsü yöneticisi.

    Özellikler:
    - Prompt ekleme ve çakışma denetimi
    - Aktif versiyon sorgulama (dil bazlı)
    - Versiyon geçmişi izleme
    - A/B testi için çoklu aktif versiyon desteği
    - Rollback mekanizması
    """

    def __init__(self) -> None:
        # prompt_id → [PromptVersion listesi]
        self._registry: dict[str, list[PromptVersion]] = {}

    def register(self, prompt: PromptVersion) -> None:
        """Yeni prompt versiyonunu kaydeder. Aynı id+version çakışmasını engeller."""
        if prompt.prompt_id not in self._registry:
            self._registry[prompt.prompt_id] = []

        existing_versions = [p.version for p in self._registry[prompt.prompt_id]]
        if prompt.version in existing_versions:
            raise ValueError(
                f"Prompt '{prompt.prompt_id}' için '{prompt.version}' versiyonu zaten kayıtlı."
            )

        # Tek aktif versiyon politikası (A/B testi için kaldırılabilir)
        if prompt.is_active:
            for existing in self._registry[prompt.prompt_id]:
                if existing.language == prompt.language:
                    existing.is_active = False

        self._registry[prompt.prompt_id].append(prompt)
        logger.info(
            f"Prompt kaydedildi: {prompt.full_version_id} (active={prompt.is_active})"
        )

    def get_active(self, prompt_id: str, language: str = "any") -> PromptVersion | None:
        """
        Belirtilen dil için aktif prompt versiyonunu döner.
        Dil eşleşmesi yoksa "any" ile etiketlenmiş aktif versiyona düşer.
        """
        versions = self._registry.get(prompt_id, [])

        # Önce dil eşleşmesini dene
        for pv in versions:
            if pv.is_active and pv.language == language:
                return pv

        # "any" versiyona düş
        for pv in versions:
            if pv.is_active and pv.language == "any":
                return pv

        logger.warning(f"Aktif prompt bulunamadı: {prompt_id} (language={language})")
        return None

    def get_version_string(self, prompt_id: str, language: str = "any") -> str | None:
        """Aktif versiyonun version string'ini (vX.Y) döner."""
        pv = self.get_active(prompt_id, language)
        return pv.version if pv else None

    def get_version(self, prompt_id: str, version: str) -> PromptVersion | None:
        """Belirli bir versiyonu döner."""
        for pv in self._registry.get(prompt_id, []):
            if pv.version == version:
                return pv
        return None

    async def get(self, name: str, version: str | None = None) -> PromptVersion | None:
        """
        Infrastructure katmanı uyumluluğu için async wrapper.
        version verilmezse aktifi döner.
        """
        if version:
            return self.get_version(name, version)
        return self.get_active(name)

    def get_history(self, prompt_id: str) -> list[PromptVersion]:
        """Bir prompt'un tüm versiyon geçmişini döner (en yeniden en eskiye)."""
        return list(reversed(self._registry.get(prompt_id, [])))

    def activate(self, prompt_id: str, version: str) -> bool:
        """Rollback: belirli bir versiyonu aktif eder, diğerlerini deaktif eder."""
        versions = self._registry.get(prompt_id, [])
        found = False
        for pv in versions:
            if pv.version == version:
                pv.is_active = True
                found = True
            else:
                pv.is_active = False
        if found:
            logger.info(f"Prompt aktif edildi (rollback): {prompt_id}@{version}")
        return found

    def list_prompts(self) -> dict[str, list[str]]:
        """Tüm kayıtlı prompt ID'lerini ve versiyonlarını listeler."""
        return {
            pid: [pv.version for pv in versions]
            for pid, versions in self._registry.items()
        }


def build_default_registry() -> PromptRegistry:
    """
    Production prompt kayıt defterini oluşturur.
    v1.0 (İngilizce temel) → v2.0 (Türkçe yapılandırılmış) → v2.1 (Aktif, gelişmiş)
    """
    registry = PromptRegistry()

    registry.register(
        PromptVersion(
            prompt_id="diplomatic_analysis",
            version="v1.0",
            template=(
                "Analyze the following diplomatic text. Provide:\n"
                "1. Sentiment score (-1.0 to 1.0)\n"
                "2. Risk score (0.0 to 1.0)\n"
                "3. Risk factors (list)\n"
                "4. Brief summary\n\n"
                "RESPONSE FORMAT: valid JSON only.\n"
                "Text: {text}"
            ),
            description="İlk sürüm — temel İngilizce analiz",
            is_active=False,
            model_name="gpt-4o",
            language="en",
        )
    )

    registry.register(
        PromptVersion(
            prompt_id="diplomatic_analysis",
            version="v2.0",
            template=(
                "Sen, diplomatik metin analizinde uzman bir analistsin.\n"
                "Aşağıdaki metni analiz et ve YALNIZCA geçerli JSON formatında yanıt ver:\n\n"
                '{{"sentiment_score": <float -1.0 ile 1.0>, '
                '"risk_score": <float 0.0 ile 1.0>, '
                '"sentiment_label": "<positive|negative|neutral|mixed>", '
                '"risk_factors": [<string>], '
                '"summary": "<string>", '
                '"key_claims": [<string>]}}\n\n'
                "Metin: {text}"
            ),
            description="Türkçe sistem prompt'u + yapılandırılmış JSON çıktı",
            is_active=False,
            model_name="gpt-4o",
            language="tr",
        )
    )

    registry.register(
        PromptVersion(
            prompt_id="diplomatic_analysis",
            version="v2.1",
            template=(
                "Sen, uluslararası diplomasi ve jeopolitik analizde uzman bir yapay zeka asistanısın.\n"
                "Aşağıdaki metni çok katmanlı olarak analiz et.\n\n"
                "İnceleme kriterleri:\n"
                "- Siyasi risk düzeyi (gerginlik esnekliği, retorik şiddeti, sözde diplomasi tespiti)\n"
                "- Duygusal ton (matematiksel olarak: -1.0 = aşırı negatif, +1.0 = aşırı pozitif)\n"
                "- Ana iddialar ve bunların diplomatik doğruluk riski\n\n"
                "YANIT FORMATI (sadece geçerli JSON, markdown veya açıklama olmadan):\n"
                '{{"sentiment_score": <float>, "risk_score": <float>, '
                '"sentiment_label": "<positive|negative|neutral|mixed>", '
                '"risk_factors": [<string>], "summary": "<string>", '
                '"key_claims": [<string>]}}\n\n'
                "Metin: {text}"
            ),
            description="Gelişmiş jeopolitik bağlam, doğruluk riski, katmanlı analiz — AKTİF VERSİYON",
            is_active=True,
            model_name="gpt-4o",
            language="any",  # Hem TR hem EN metinleri karşılar
        )
    )

    registry.register(
        PromptVersion(
            prompt_id="Grootendorst2022",
            version="v1.0",
            template="BERTopic Analysis Stub",
            description="Academic reference for BERTopic",
            academic_ref="Grootendorst, M. (2022). BERTopic: Neural Topic Modeling.",
        )
    )
    return registry
