# ============================================================
# DOSYA: src/bb_paxdata/domain/services/prompt_registry.py
# AÇIKLAMA: Prompt versiyon yaşam döngüsü yönetimi
# ============================================================

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


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
        """SHA-256 hash hesaplar (tam 64 karakter)."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def verify_integrity(self, provided_hash: str) -> bool:
        """Dışarıdan gelen hash'in bu şablonla eşleşip eşleşmediğini kontrol eder."""
        return self.template_hash == provided_hash

    @property
    def hash(self) -> str:
        """Geriye uyumluluk için alias."""
        return self.template_hash

    @property
    def content(self) -> str:
        """Alias for template for compatibility."""
        return self.template

    @property
    def content_hash(self) -> str:
        """Alias for template_hash for compatibility."""
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
    - Database-backed storage with migration support
    """

    def __init__(self, db_session: Session | None = None) -> None:
        # prompt_id → [PromptVersion listesi]
        self._registry: dict[str, list[PromptVersion]] = {}
        self._db_session = db_session
        if db_session is not None:
            self._load_from_database()

    def _load_from_database(self) -> None:
        """Load prompts from database if session is available."""
        if self._db_session is None:
            return

        try:
            from bb_paxdata.infrastructure.db.models import (
                PromptVersion as PromptVersionORM,
            )

            orm_versions = self._db_session.query(PromptVersionORM).all()
            for orm in orm_versions:
                prompt = PromptVersion(
                    prompt_id=orm.prompt_id,
                    version=orm.version,
                    template=orm.template,
                    description=orm.description or "",
                    is_active=orm.is_active,
                    model_name=orm.model_name,
                    created_at=orm.created_at.isoformat() if orm.created_at else "",
                    language=orm.language,
                    academic_ref=orm.academic_ref,
                )
                # Verify hash matches
                if prompt.template_hash != orm.template_hash:
                    logger.warning(
                        f"Hash mismatch for {prompt.full_version_id}: "
                        f"DB={orm.template_hash}, computed={prompt.template_hash}"
                    )
                self._add_to_registry(prompt)
            logger.info(f"Loaded {len(orm_versions)} prompt versions from database")
        except Exception as e:
            logger.error(f"Failed to load prompts from database: {e}")
            # Fall back to empty registry

    def _add_to_registry(self, prompt: PromptVersion) -> None:
        """Internal method to add prompt without validation."""
        if prompt.prompt_id not in self._registry:
            self._registry[prompt.prompt_id] = []
        self._registry[prompt.prompt_id].append(prompt)

    def sync_to_database(self) -> None:
        """Sync current registry to database."""
        if self._db_session is None:
            logger.warning("No database session available, skipping sync")
            return

        try:
            from bb_paxdata.infrastructure.db.models import (
                PromptVersion as PromptVersionORM,
            )

            for prompt_id, versions in self._registry.items():
                for prompt in versions:
                    existing = (
                        self._db_session.query(PromptVersionORM)
                        .filter(
                            PromptVersionORM.prompt_id == prompt.prompt_id,
                            PromptVersionORM.version == prompt.version,
                        )
                        .first()
                    )
                    if existing:
                        # Update existing
                        existing.template = prompt.template
                        existing.description = prompt.description
                        existing.is_active = prompt.is_active
                        existing.model_name = prompt.model_name
                        existing.language = prompt.language
                        existing.academic_ref = prompt.academic_ref
                        existing.template_hash = prompt.template_hash
                    else:
                        # Insert new
                        orm = PromptVersionORM(
                            prompt_id=prompt.prompt_id,
                            version=prompt.version,
                            template=prompt.template,
                            description=prompt.description,
                            is_active=prompt.is_active,
                            model_name=prompt.model_name,
                            language=prompt.language,
                            academic_ref=prompt.academic_ref,
                            template_hash=prompt.template_hash,
                        )
                        self._db_session.add(orm)
            self._db_session.commit()
            logger.info("Synced prompt registry to database")
        except Exception as e:
            logger.error(f"Failed to sync prompts to database: {e}")
            if self._db_session:
                self._db_session.rollback()

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

        # Sync to database if session is available
        if self._db_session is not None:
            try:
                from bb_paxdata.infrastructure.db.models import (
                    PromptVersion as PromptVersionORM,
                )

                orm = PromptVersionORM(
                    prompt_id=prompt.prompt_id,
                    version=prompt.version,
                    template=prompt.template,
                    description=prompt.description,
                    is_active=prompt.is_active,
                    model_name=prompt.model_name,
                    language=prompt.language,
                    academic_ref=prompt.academic_ref,
                    template_hash=prompt.template_hash,
                )
                self._db_session.add(orm)
                self._db_session.commit()
            except Exception as e:
                logger.error(f"Failed to sync new prompt to database: {e}")
                if self._db_session:
                    self._db_session.rollback()

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
        if "@" in name and version is None:
            name, version = name.split("@", 1)
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


def build_default_registry(db_session: Session | None = None) -> PromptRegistry:
    """
    Production prompt kayıt defterini oluşturur.
    v1.0 (İngilizce temel) → v2.0 (Türkçe yapılandırılmış) → v2.1 (Aktif, gelişmiş)

    Args:
        db_session: Optional database session. If provided, loads prompts from database.
                   If database is empty, falls back to hardcoded prompts.
    """
    registry = PromptRegistry(db_session=db_session)

    # Only register hardcoded prompts if database is empty or no session provided
    if db_session is None or len(registry.list_prompts()) == 0:
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

        ANOMALY_VALIDATION_PROMPT_TEXT = """You are an expert in diplomatic discourse analysis acting as an anomaly validation judge.

## CONTEXT (last {self._max_ctx} sentences):
{ctx_block}

## SENTENCE UNDER ANALYSIS:
"{sentence.text}"

## DETERMINISTIC ANOMALY ENGINE RESULT:
{anomaly_block}

## YOUR TASK:
Analyze the sentence in its diplomatic context and validate or challenge the deterministic result.
Consider:
- Is this genuine contradiction or strategic irony/rhetoric?
- Does the speaker use diplomatic subtext that rules cannot capture?
- Are there hidden coercive signals or tone shifts the rules missed?

Respond ONLY with a valid JSON object:
{{
  "decision": "<CONFIRMED|DISMISSED|ESCALATED|AI_ONLY|INCONCLUSIVE>",
  "coherence_score": <0.0-1.0, where 1.0=fully coherent/no anomaly>,
  "reasoning": "<concise explanation in the same language as the sentence>",
  "detected_subtype": "<irony|rhetorical_strategy|coercive_signal|tone_drift|null>",
  "confidence": <0.0-1.0>
}}"""

        # We skip hashing here because PromptVersion computes it in __post_init__ automatically
        registry.register(
            PromptVersion(
                prompt_id="anomaly_validation",
                version="v1.0",
                template=ANOMALY_VALIDATION_PROMPT_TEXT,
                description="LLM-as-a-Judge semantic anomaly validation",
                is_active=True,
                model_name="gpt-4o",
                language="any",
                academic_ref="Tsytsarau et al. (2017) | LLM-as-a-Judge (Zheng et al. 2023)",
            )
        )

        registry.register(
            PromptVersion(
                prompt_id="rag_synthesis",
                version="v2.0",
                template=(
                    "You are an expert AI Diplomatic Analyst. Use the following retrieved context sentences (total: {source_count}) to answer the user query.\n"
                    "If the retrieved context does not contain enough information to answer the query, prioritize the retrieved context but you may use general diplomatic knowledge to bridge the gaps, clearly indicating what is sourced from the context and what is inferred.\n\n"
                    "Retrieved Context:\n"
                    "{context}\n\n"
                    "User Query: {query}\n\n"
                    "Synthesized Diplomatic Analysis:"
                ),
                description="RAG synthesis prompt with source count and context",
                is_active=True,
                model_name="gpt-4o",
                language="any",
            )
        )

        registry.register(
            PromptVersion(
                prompt_id="frame_analysis",
                version="v2.1",
                template=(
                    "Analyze the following sentence in the context of international relations and determine its primary discourse frame (e.g. conflict, cooperation, trade, security).\n"
                    'Sentence: "{text}"\n'
                    'Response format: JSON with "frame" and "explanation".'
                ),
                description="Frame analysis prompt",
                is_active=True,
                model_name="gpt-4o",
                language="any",
            )
        )

        registry.register(
            PromptVersion(
                prompt_id="dki_judge",
                version="v2.1",
                template=(
                    "## ROLE & MISSION:\n"
                    "You are an expert AI Diplomatic Analyst acting as a quality judge for the BB-PAXDATA pipeline.\n"
                    "Evaluate the current statement analysis against the historical baseline metrics for the actor.\n\n"
                    "## TARGET TRANSCRIPT CONTENT:\n"
                    "Actor: {speaker_name} ({country})\n"
                    'Target Sentence: "{sentence_text}"\n\n'
                    "## PIPELINE ANALYSIS OUTPUT:\n"
                    "Assigned Sentiment: {pipeline_sentiment}\n"
                    "Assigned Risk Score: {pipeline_risk_score} (0-10)\n"
                    "Assigned Discourse Frame: {pipeline_frame}\n\n"
                    "## HISTORICAL BASELINE METRICS:\n"
                    "Baseline Sentiment Average: {historical_sentiment_avg}\n"
                    "Baseline Risk Average: {historical_risk_avg}\n"
                    "Primary Historical Frame: {historical_frame}\n\n"
                    "## EVALUATION CRITERIA:\n"
                    "1. Semantic Shift Check: Does the target statement represent an uncalibrated jump in stance?\n"
                    "2. Frame Consistency: Is the shift in frame logically supported by the sentence semantics?\n\n"
                    "## JSON OUTPUT FORMAT:\n"
                    "Provide the evaluation strictly in JSON format:\n"
                    "{{\n"
                    '  "semantic_shift_score": float (0.0 to 1.0),\n'
                    '  "is_consistent": boolean,\n'
                    '  "calibration_drift": float (-1.0 to 1.0),\n'
                    '  "reasoning": "Detailed textual explanation"\n'
                    "}}"
                ),
                description="LLM-as-a-Judge v2.1 prompt template",
                is_active=True,
                model_name="gpt-4o",
                language="any",
            )
        )

        # === TASK-A06 Presupposition Verification Prompt ===
        registry.register(
            PromptVersion(
                prompt_id="presupposition_verification_v1",
                version="v1.0",
                template=(
                    "You are an expert in linguistic presupposition analysis (Lewis 1979, Beaver & Geurts 2014).\n\n"
                    "Analyze the following diplomatic utterance and determine if the presupposition candidate is valid.\n\n"
                    "## UTTERANCE:\n"
                    "Speaker: {speaker}\n"
                    'Text: "{segment_text}"\n\n'
                    "## PRESUPPOSITION CANDIDATE:\n"
                    'Trigger word: "{trigger_word}"\n'
                    "Trigger type: {trigger_type}\n"
                    'Presupposed content: "{presupposed_content}"\n'
                    "Rule-based confidence: {confidence:.2f}\n\n"
                    "## YOUR TASK:\n"
                    "Determine if this is a genuine presupposition (content taken for granted by the speaker) or a false positive.\n"
                    "Consider:\n"
                    "- Does the trigger word actually induce a presupposition in this context?\n"
                    "- Is the presupposed content indeed taken for granted?\n"
                    "- Is this a genuine commitment or merely rhetorical?\n\n"
                    "Respond ONLY with valid JSON:\n"
                    "{{\n"
                    '  "is_valid": <boolean>,\n'
                    '  "confidence": <float 0.0-1.0>,\n'
                    '  "refined_content": "<string - refined presupposed content if valid, otherwise null>",\n'
                    '  "reasoning": "<brief explanation>"\n'
                    "}}"
                ),
                description="LLM verification prompt for presupposition candidates (TASK-A06)",
                is_active=True,
                model_name="gpt-4o",
                language="any",
                academic_ref="Beaver & Geurts (2014) — Presupposition, Stanford Encyclopedia; Lewis (1979) — Scorekeeping in a language game",
            )
        )

        # === TASK-E04 Event Coreference Verification Prompt ===
        # CORRECTED (E04-M-04): LLM verification prompt with threshold window
        registry.register(
            PromptVersion(
                prompt_id="event_coreference_verify",
                version="1",
                template=(
                    "Do these two event descriptions refer to the same real-world event?\n"
                    "Event A: {event_a_description} (date: {event_a_date}, actors: {event_a_actors})\n"
                    "Event B: {event_b_description} (date: {event_b_date}, actors: {event_b_actors})\n"
                    "Answer YES or NO with a confidence score between 0.0 and 1.0.\n"
                    'Format: {{"answer": "YES"|"NO", "confidence": float}}'
                ),
                description="LLM verification for event coreference pairs near threshold (TASK-E04)",
                is_active=True,
                model_name="gpt-4o",
                language="any",
                academic_ref="Cybulska & Vossen (2014) ECB+, Bejan & Harabagiu (2010) NAACL",
            )
        )

    return registry
