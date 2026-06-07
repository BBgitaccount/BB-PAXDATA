# TASK-E01 · Contrastive Analysis Engine — Delta Mode
## Geliştirme Raporu (AI Agent İçin Hazırlanmış)

---

### EXECUTIVE SUMMARY

**Görev Tanımı:** Mevcut PaxData sistemi her session'ı bağımsız analiz eder. "İki session arasında ne değişti?" sorusunu otomatik olarak cevaplayan bir mod yoktur. Bu görev tüm analiz çıktılarını karşılaştıran bir output layer'dır — yeni model gerektirmez, mevcut modellerin çıktılarını birbirine bağlar.

**Kategori:** Mühendislik | **Zorluk:** M | **Öncelik:** P1

**Temel Çıktı:**
- `AnalysisDelta` modeli: İki session arasındaki tüm metriklerin delta değerlerini içerir
- `ContrastReport` modeli: Delta verilerini özetleyen ve LLM tarafından üretilen narrative içeren rapor
- `CompareSessionsUseCase`: Karşılaştırma iş mantığını içeren use case
- API endpoint: `POST /sessions/compare`
- Frontend component: Session karşılaştırma paneli

**Başarı Kriterleri:**
- İki session arası delta hesabı < 2 saniye
- Significant change tespiti precision ≥ 0.85 (manuel doğrulama)
- LLM özetinin coherence skoru (LLM-as-judge ile) ≥ 4/5

---

### 1. MEVCUT SİSTEM ANALİZİ

#### 1.1. Veri Modeli Yapısı

**Session/Panel Tanımı:**
- Sistemde "panel_id" ve "session_id" kavramları birlikte kullanılır
- `File` modeli (infrastructure/db/models.py): `file_id` (primary key), `panel_number`, `date_str`
- `SpeakerPositionTable` (sbi_table.py): `session_id`, `speaker_id` kombinasyonu ile pozisyonları saklar
- `DKIResultModel` (dki_table.py): `session_id`, `speaker_id`, `analysis_id` ile DKI sonuçlarını saklar

**Mevcut Analiz Çıktıları:**

1. **SBI (Speaker-Based Index):**
   - Model: `SpeakerPosition` (domain/models/sbi_models.py)
   - Alanlar: `speaker_id`, `session_id`, `wordfish_theta`, `stance_density`, `engagement_score`, `sbi`
   - Persistence: `SpeakerPositionTable` (infrastructure/db/sbi_table.py)
   - Repository: Mevcut repository pattern'ı takip eder (base repository)

2. **DKI (Discourse-Kinetic Index):**
   - Model: `DKIResult` (domain/models/dki.py)
   - Alanlar: `speaker_id`, `session_id`, `dki_score`, `velocity`, `semantic_shift`, `debate_loading`
   - Persistence: `DKIResultModel` (infrastructure/db/dki_table.py)
   - Repository: `DKIRepository` (infrastructure/db/repositories/dki_repository.py)

3. **Bilateral Sentiment:**
   - Model: `BilateralSentiment` (domain/models/bilateral_sentiment.py)
   - Alanlar: `panel_id`, `from_country`, `to_country`, `affinity_score`, `avg_sentiment`
   - Repository: `BilateralSentimentRepository` (infrastructure/db/repositories/country_repository.py)
   - Use Case: `AggregateBilateralSentimentUseCase` (application/use_cases/aggregate_bilateral_sentiment.py)

4. **Risk Score:**
   - Model: `Analysis` (domain/models/analysis.py)
   - Alanlar: `ai_risk_score`, `risk_level`, `risk_trajectory`, `future_risk_tier`
   - Persistence: `AISentenceAnalysis` (infrastructure/db/models.py - line 1993+)

5. **Hedging:**
   - Model: `HedgingResult` (application/protocols.py)
   - Alanlar: `score`, `categories`, `confidence`
   - Service: `HedgingService` (domain/services/hedging_service.py)
   - Integration: `Analysis.hedging_result` alanı

6. **Speech Act:**
   - Model: `SpeechActClassification` (domain/models/speech_act.py)
   - Service: `SpeechActClassifier` (domain/services/speech_act_classifier.py)
   - Integration: `Analysis.speech_act` alanı

7. **Narrative:**
   - Model: `DiscourseFlow` (domain/models/discourse_flow.py)
   - Alanlar: `narrative_layer`, `narrative_target_actor`, `narrative_salience`
   - Repository: `DiscourseFlowRepository` (infrastructure/db/repositories/country_repository.py)

#### 1.2. Mevcut Use Case Pattern

**Pattern Analizi (aggregate_bilateral_sentiment.py referansı):**

```python
@dataclass(frozen=True)
class AggregateBilateralSentimentInput:
    panel_id: str

@dataclass(frozen=True)
class AggregateBilateralSentimentOutput:
    panel_id: str
    created_count: int
    updated_count: int
    total_pairs: int
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return len(self.errors) == 0

class AggregateBilateralSentimentUseCase:
    def __init__(
        self,
        ref_repo: ICountryReferenceRepository,
        sentiment_repo: IBilateralSentimentRepository,
    ) -> None:
        self._ref_repo = ref_repo
        self._sentiment_repo = sentiment_repo

    async def execute(
        self, input_data: AggregateBilateralSentimentInput
    ) -> AggregateBilateralSentimentOutput:
        # Implementation
```

**Pattern Özellikleri:**
- Frozen dataclass input/output
- `succeeded` property for error checking
- Repository injection via constructor
- Async execute method
- Structured logging with structlog

#### 1.3. Mevcut Repository Pattern

**BaseRepository (infrastructure/db/repositories/base.py):**
```python
class BaseRepository(Generic[ModelT]):
    model_class: type[ModelT]
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def get_by_id(self, id: int) -> ModelT | None: ...
    async def get_all(self) -> list[ModelT]: ...
    async def save(self, entity: ModelT) -> ModelT: ...
    async def delete(self, id: int) -> bool: ...
```

**Repository Protocols (domain/services/country_repositories.py):**
- Protocol-based interfaces
- Async methods
- Domain model return types
- Session management handled by infrastructure layer

#### 1.4. Mevcut API Structure

**API Layer (interfaces/api/routers/v1/):**
- FastAPI router pattern
- Dependency injection for database sessions
- Permission checking via `PermissionChecker`
- Response models in `interfaces/api/schemas.py`

**Örnek Endpoint Pattern (discourse.py):**
```python
@router.get("", response_model=DiscourseNetworkResponse)
async def get_discourse_network(
    session_id: str | None = Query(None, description="Filter edges by session/run ID"),
    min_weight: float = Query(0.0, description="Minimum edge weight threshold"),
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("view")),
):
    # Implementation
```

---

### 2. TEKNİK TASARIM

#### 2.1. Domain Models

**2.1.1. AnalysisDelta Model**

```python
# domain/models/analysis_delta.py (YENİ DOSYA)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class MetricDelta:
    """Single metric delta calculation result."""
    
    metric_name: str
    value_a: float | None
    value_b: float | None
    delta: float | None
    delta_normalized: float | None
    is_significant: bool
    threshold: float


@dataclass(frozen=True)
class SpeechActDistributionDelta:
    """Speech act type distribution change."""
    
    speaker_id: str
    distribution_a: dict[str, float]  # speech_act_type -> count/percentage
    distribution_b: dict[str, float]
    delta_distribution: dict[str, float]  # type -> delta
    most_changed_type: str | None
    change_magnitude: float


@dataclass(frozen=True)
class NarrativeLayerDelta:
    """Narrative layer weight changes."""
    
    speaker_id: str
    layer_weights_a: dict[str, float]  # layer -> weight
    layer_weights_b: dict[str, float]
    delta_weights: dict[str, float]
    dominant_layer_change: tuple[str, float] | None  # (layer, delta)


class AnalysisDelta(BaseModel):
    """
    Complete delta analysis between two sessions/panels.
    
    Contains all metric deltas, significance flags, and change summaries.
    """
    
    # Identification
    session_a_id: str = Field(..., description="First session/panel ID")
    session_b_id: str = Field(..., description="Second session/panel ID")
    comparison_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When comparison was performed"
    )
    
    # SBI Deltas (per speaker)
    delta_sbi: dict[str, float] = Field(
        default_factory=dict,
        description="Speaker ID -> ΔSBI (value_b - value_a)"
    )
    delta_sbi_normalized: dict[str, float] = Field(
        default_factory=dict,
        description="Speaker ID -> ΔSBI normalized to baseline"
    )
    delta_sbi_significant: dict[str, bool] = Field(
        default_factory=dict,
        description="Speaker ID -> whether ΔSBI exceeds threshold"
    )
    
    # DKI Deltas (per speaker)
    delta_dki: dict[str, float] = Field(
        default_factory=dict,
        description="Speaker ID -> ΔDKI"
    )
    delta_dki_normalized: dict[str, float] = Field(
        default_factory=dict,
        description="Speaker ID -> ΔDKI normalized"
    )
    delta_dki_significant: dict[str, bool] = Field(
        default_factory=dict,
        description="Speaker ID -> whether ΔDKI exceeds threshold"
    )
    
    # Risk Score Delta (aggregate)
    delta_risk: float | None = Field(
        default=None,
        description="Aggregate risk score change (value_b - value_a)"
    )
    delta_risk_normalized: float | None = Field(
        default=None,
        description="Risk delta normalized to baseline"
    )
    delta_risk_significant: bool = Field(
        default=False,
        description="Whether risk delta exceeds threshold"
    )
    
    # Hedging Rate Deltas (per speaker)
    delta_hedging: dict[str, float] = Field(
        default_factory=dict,
        description="Speaker ID -> ΔHedging rate"
    )
    delta_hedging_normalized: dict[str, float] = Field(
        default_factory=dict,
        description="Speaker ID -> ΔHedging normalized"
    )
    delta_hedging_significant: dict[str, bool] = Field(
        default_factory=dict,
        description="Speaker ID -> whether hedging delta exceeds threshold"
    )
    
    # Speech Act Distribution Deltas (per speaker)
    delta_speech_act: dict[str, SpeechActDistributionDelta] = Field(
        default_factory=dict,
        description="Speaker ID -> speech act distribution delta"
    )
    
    # Narrative Layer Deltas (per speaker)
    delta_narrative: dict[str, NarrativeLayerDelta] = Field(
        default_factory=dict,
        description="Speaker ID -> narrative layer weight delta"
    )
    
    # Significant Changes Summary
    significant_changes: list[str] = Field(
        default_factory=list,
        description="List of all significant changes detected"
    )
    
    # Metadata
    speakers_in_a: set[str] = Field(
        default_factory=set,
        description="Speakers present in session A"
    )
    speakers_in_b: set[str] = Field(
        default_factory=set,
        description="Speakers present in session B"
    )
    common_speakers: set[str] = Field(
        default_factory=set,
        description="Speakers present in both sessions"
    )
    speakers_only_in_a: set[str] = Field(
        default_factory=set,
        description="Speakers only in session A"
    )
    speakers_only_in_b: set[str] = Field(
        default_factory=set,
        description="Speakers only in session B"
    )
    
    # Computed Fields
    @property
    def most_drifted_speaker(self) -> str | None:
        """Speaker with highest aggregate drift magnitude."""
        if not self.common_speakers:
            return None
        
        drift_scores: dict[str, float] = {}
        for speaker in self.common_speakers:
            score = 0.0
            if speaker in self.delta_sbi:
                score += abs(self.delta_sbi_normalized.get(speaker, 0.0))
            if speaker in self.delta_dki:
                score += abs(self.delta_dki_normalized.get(speaker, 0.0))
            if speaker in self.delta_hedging:
                score += abs(self.delta_hedging_normalized.get(speaker, 0.0))
            drift_scores[speaker] = score
        
        if not drift_scores:
            return None
        
        return max(drift_scores, key=drift_scores.get)
    
    @property
    def most_drifted_dimension(self) -> str:
        """Dimension with highest aggregate drift."""
        dimension_drifts = {
            "SBI": sum(abs(v) for v in self.delta_sbi_normalized.values()),
            "DKI": sum(abs(v) for v in self.delta_dki_normalized.values()),
            "Risk": abs(self.delta_risk_normalized or 0.0),
            "Hedging": sum(abs(v) for v in self.delta_hedging_normalized.values()),
        }
        return max(dimension_drifts, key=dimension_drifts.get)
    
    @property
    def total_significant_changes(self) -> int:
        """Total count of significant changes across all metrics."""
        count = 0
        count += sum(1 for v in self.delta_sbi_significant.values() if v)
        count += sum(1 for v in self.delta_dki_significant.values() if v)
        count += 1 if self.delta_risk_significant else 0
        count += sum(1 for v in self.delta_hedging_significant.values() if v)
        return count
```

**2.1.2. ContrastReport Model**

```python
# domain/models/contrast_report.py (YENİ DOSYA)

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .analysis_delta import AnalysisDelta


class ContrastReport(BaseModel):
    """
    Complete contrast report with narrative summary.
    
    Wraps AnalysisDelta with LLM-generated narrative and metadata.
    """
    
    # Core Delta Data
    delta: AnalysisDelta = Field(..., description="Complete delta analysis")
    
    # Narrative Summary (LLM-generated)
    narrative_summary: str = Field(
        ...,
        description="Natural language summary of changes generated by LLM"
    )
    narrative_summary_model: str = Field(
        default="",
        description="LLM model used for summary generation"
    )
    narrative_summary_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When narrative summary was generated"
    )
    
    # Computed Highlights
    most_drifted_speaker: str | None = Field(
        default=None,
        description="Speaker with highest aggregate drift"
    )
    most_drifted_dimension: str = Field(
        default="",
        description="Dimension with highest aggregate drift"
    )
    
    # Key Insights
    key_insights: list[str] = Field(
        default_factory=list,
        description="Top-N key insights extracted from delta analysis"
    )
    
    # Risk Assessment
    risk_assessment: str | None = Field(
        default=None,
        description="Risk assessment based on delta analysis"
    )
    risk_level_changed: bool = Field(
        default=False,
        description="Whether overall risk level changed significantly"
    )
    
    # Recommendation
    recommendation: str | None = Field(
        default=None,
        description="Actionable recommendation based on comparison"
    )
    
    # Metadata
    report_id: str = Field(
        default="",
        description="Unique identifier for this contrast report"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When report was generated"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
```

#### 2.2. Use Case Design

**2.2.1. CompareSessionsUseCase**

```python
# application/use_cases/compare_sessions.py (YENİ DOSYA)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from bb_paxdata.domain.models.analysis_delta import (
    AnalysisDelta,
    NarrativeLayerDelta,
    SpeechActDistributionDelta,
)
from bb_paxdata.domain.models.contrast_report import ContrastReport
from bb_paxdata.domain.models.sbi_models import SpeakerPosition
from bb_paxdata.domain.models.dki import DKIResult
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment

if TYPE_CHECKING:
    from bb_paxdata.application.protocols import LLMServiceProtocol

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CompareSessionsInput:
    """Input for session comparison use case."""
    
    session_a_id: str
    session_b_id: str
    sbi_threshold: float = 0.15
    dki_threshold: float = 0.15
    risk_threshold: float = 0.10
    hedging_threshold: float = 0.10
    include_narrative: bool = True
    narrative_language: str = "en"


@dataclass(frozen=True)
class CompareSessionsOutput:
    """Output from session comparison use case."""
    
    success: bool
    contrast_report: ContrastReport | None = None
    analysis_delta: AnalysisDelta | None = None
    errors: tuple[str, ...] = ()
    
    @property
    def succeeded(self) -> bool:
        return self.success and len(self.errors) == 0


class CompareSessionsUseCase:
    """
    Use case for comparing two sessions/panels.
    
    Calculates deltas for all metrics and generates narrative summary.
    """
    
    # Significance thresholds (configurable)
    DEFAULT_SBI_THRESHOLD = 0.15
    DEFAULT_DKI_THRESHOLD = 0.15
    DEFAULT_RISK_THRESHOLD = 0.10
    DEFAULT_HEDGING_THRESHOLD = 0.10
    
    def __init__(
        self,
        sbi_repository: Any,  # ISBIRepository protocol
        dki_repository: Any,  # IDKIRepository protocol
        analysis_repository: Any,  # IAnalysisRepository protocol
        bilateral_repository: Any,  # IBilateralSentimentRepository protocol
        llm_service: LLMServiceProtocol | None = None,
    ) -> None:
        self._sbi_repo = sbi_repository
        self._dki_repo = dki_repository
        self._analysis_repo = analysis_repository
        self._bilateral_repo = bilateral_repository
        self._llm_service = llm_service
    
    async def execute(
        self, input_data: CompareSessionsInput
    ) -> CompareSessionsOutput:
        """Execute session comparison."""
        
        session_a = input_data.session_a_id
        session_b = input_data.session_b_id
        
        logger.info(
            "compare_sessions.started",
            session_a=session_a,
            session_b=session_b,
        )
        
        errors: list[str] = []
        
        # Step 1: Fetch data for both sessions
        try:
            sbi_a = await self._fetch_sbi_data(session_a)
            sbi_b = await self._fetch_sbi_data(session_b)
        except Exception as exc:
            errors.append(f"SBI data fetch failed: {exc}")
            sbi_a, sbi_b = {}, {}
        
        try:
            dki_a = await self._fetch_dki_data(session_a)
            dki_b = await self._fetch_dki_data(session_b)
        except Exception as exc:
            errors.append(f"DKI data fetch failed: {exc}")
            dki_a, dki_b = {}, {}
        
        try:
            risk_a = await self._fetch_risk_data(session_a)
            risk_b = await self._fetch_risk_data(session_b)
        except Exception as exc:
            errors.append(f"Risk data fetch failed: {exc}")
            risk_a, risk_b = None, None
        
        try:
            hedging_a = await self._fetch_hedging_data(session_a)
            hedging_b = await self._fetch_hedging_data(session_b)
        except Exception as exc:
            errors.append(f"Hedging data fetch failed: {exc}")
            hedging_a, hedging_b = {}, {}
        
        try:
            speech_act_a = await self._fetch_speech_act_data(session_a)
            speech_act_b = await self._fetch_speech_act_data(session_b)
        except Exception as exc:
            errors.append(f"Speech act data fetch failed: {exc}")
            speech_act_a, speech_act_b = {}, {}
        
        try:
            narrative_a = await self._fetch_narrative_data(session_a)
            narrative_b = await self._fetch_narrative_data(session_b)
        except Exception as exc:
            errors.append(f"Narrative data fetch failed: {exc}")
            narrative_a, narrative_b = {}, {}
        
        # Step 2: Calculate AnalysisDelta
        try:
            delta = self._calculate_delta(
                session_a=session_a,
                session_b=session_b,
                sbi_a=sbi_a,
                sbi_b=sbi_b,
                dki_a=dki_a,
                dki_b=dki_b,
                risk_a=risk_a,
                risk_b=risk_b,
                hedging_a=hedging_a,
                hedging_b=hedging_b,
                speech_act_a=speech_act_a,
                speech_act_b=speech_act_b,
                narrative_a=narrative_a,
                narrative_b=narrative_b,
                sbi_threshold=input_data.sbi_threshold,
                dki_threshold=input_data.dki_threshold,
                risk_threshold=input_data.risk_threshold,
                hedging_threshold=input_data.hedging_threshold,
            )
        except Exception as exc:
            errors.append(f"Delta calculation failed: {exc}")
            return CompareSessionsOutput(
                success=False,
                errors=tuple(errors),
            )
        
        # Step 3: Generate narrative summary if requested
        narrative_summary = ""
        if input_data.include_narrative and self._llm_service:
            try:
                narrative_summary = await self._generate_narrative(
                    delta=delta,
                    language=input_data.narrative_language,
                )
            except Exception as exc:
                errors.append(f"Narrative generation failed: {exc}")
                narrative_summary = "Narrative generation failed. See errors for details."
        
        # Step 4: Build ContrastReport
        try:
            contrast_report = ContrastReport(
                delta=delta,
                narrative_summary=narrative_summary,
                narrative_summary_model=getattr(self._llm_service, "model_name", "unknown"),
                most_drifted_speaker=delta.most_drifted_speaker,
                most_drifted_dimension=delta.most_drifted_dimension,
                key_insights=self._extract_key_insights(delta),
                risk_assessment=self._assess_risk(delta),
                risk_level_changed=delta.delta_risk_significant,
                recommendation=self._generate_recommendation(delta),
                report_id=f"contrast-{session_a}-{session_b}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            )
        except Exception as exc:
            errors.append(f"Contrast report generation failed: {exc}")
            return CompareSessionsOutput(
                success=False,
                analysis_delta=delta,
                errors=tuple(errors),
            )
        
        logger.info(
            "compare_sessions.completed",
            session_a=session_a,
            session_b=session_b,
            significant_changes=delta.total_significant_changes,
            most_drifted_speaker=delta.most_drifted_speaker,
        )
        
        return CompareSessionsOutput(
            success=True,
            contrast_report=contrast_report,
            analysis_delta=delta,
            errors=tuple(errors),
        )
    
    async def _fetch_sbi_data(self, session_id: str) -> dict[str, SpeakerPosition]:
        """Fetch SBI data for a session."""
        # Implementation depends on repository interface
        # Expected: dict[speaker_id, SpeakerPosition]
        positions = await self._sbi_repo.get_by_session(session_id)
        return {p.speaker_id: p for p in positions}
    
    async def _fetch_dki_data(self, session_id: str) -> dict[str, DKIResult]:
        """Fetch DKI data for a session."""
        results = await self._dki_repo.get_by_session(session_id)
        return {r.speaker_id: r for r in results}
    
    async def _fetch_risk_data(self, session_id: str) -> float | None:
        """Fetch aggregate risk score for a session."""
        # Calculate average risk across all analyses in session
        analyses = await self._analysis_repo.get_by_session(session_id)
        if not analyses:
            return None
        
        risk_scores = [a.ai_risk_score for a in analyses if a.ai_risk_score is not None]
        if not risk_scores:
            return None
        
        return sum(risk_scores) / len(risk_scores)
    
    async def _fetch_hedging_data(self, session_id: str) -> dict[str, float]:
        """Fetch average hedging rate per speaker for a session."""
        analyses = await self._analysis_repo.get_by_session(session_id)
        
        speaker_hedging: dict[str, list[float]] = {}
        for analysis in analyses:
            if analysis.hedging_result and analysis.speaker_id:
                speaker_hedging.setdefault(analysis.speaker_id, []).append(
                    analysis.hedging_result.score
                )
        
        # Calculate average per speaker
        return {
            speaker: sum(scores) / len(scores)
            for speaker, scores in speaker_hedging.items()
        }
    
    async def _fetch_speech_act_data(
        self, session_id: str
    ) -> dict[str, dict[str, float]]:
        """Fetch speech act distribution per speaker for a session."""
        analyses = await self._analysis_repo.get_by_session(session_id)
        
        speaker_distributions: dict[str, dict[str, float]] = {}
        for analysis in analyses:
            if analysis.speech_act and analysis.speaker_id:
                dist = speaker_distributions.setdefault(analysis.speaker_id, {})
                act_type = analysis.speech_act.primary_type.value
                dist[act_type] = dist.get(act_type, 0.0) + 1.0
        
        # Normalize to percentages
        for speaker in speaker_distributions:
            total = sum(speaker_distributions[speaker].values())
            if total > 0:
                speaker_distributions[speaker] = {
                    k: v / total for k, v in speaker_distributions[speaker].items()
                }
        
        return speaker_distributions
    
    async def _fetch_narrative_data(
        self, session_id: str
    ) -> dict[str, dict[str, float]]:
        """Fetch narrative layer weights per speaker for a session."""
        # This depends on narrative salience tracker implementation
        # Placeholder implementation
        return {}
    
    def _calculate_delta(
        self,
        session_a: str,
        session_b: str,
        sbi_a: dict[str, SpeakerPosition],
        sbi_b: dict[str, SpeakerPosition],
        dki_a: dict[str, DKIResult],
        dki_b: dict[str, DKIResult],
        risk_a: float | None,
        risk_b: float | None,
        hedging_a: dict[str, float],
        hedging_b: dict[str, float],
        speech_act_a: dict[str, dict[str, float]],
        speech_act_b: dict[str, dict[str, float]],
        narrative_a: dict[str, dict[str, float]],
        narrative_b: dict[str, dict[str, float]],
        sbi_threshold: float,
        dki_threshold: float,
        risk_threshold: float,
        hedging_threshold: float,
    ) -> AnalysisDelta:
        """Calculate complete delta between two sessions."""
        
        # Calculate speaker sets
        speakers_a = set(sbi_a.keys()) | set(dki_a.keys()) | set(hedging_a.keys())
        speakers_b = set(sbi_b.keys()) | set(dki_b.keys()) | set(hedging_b.keys())
        common_speakers = speakers_a & speakers_b
        speakers_only_in_a = speakers_a - speakers_b
        speakers_only_in_b = speakers_b - speakers_a
        
        # Calculate SBI deltas
        delta_sbi: dict[str, float] = {}
        delta_sbi_normalized: dict[str, float] = {}
        delta_sbi_significant: dict[str, bool] = {}
        
        for speaker in common_speakers:
            pos_a = sbi_a.get(speaker)
            pos_b = sbi_b.get(speaker)
            
            if pos_a and pos_b:
                delta = pos_b.sbi - pos_a.sbi
                normalized = delta / (abs(pos_a.sbi) + 1e-6)
                significant = abs(normalized) >= sbi_threshold
                
                delta_sbi[speaker] = delta
                delta_sbi_normalized[speaker] = normalized
                delta_sbi_significant[speaker] = significant
        
        # Calculate DKI deltas
        delta_dki: dict[str, float] = {}
        delta_dki_normalized: dict[str, float] = {}
        delta_dki_significant: dict[str, bool] = {}
        
        for speaker in common_speakers:
            res_a = dki_a.get(speaker)
            res_b = dki_b.get(speaker)
            
            if res_a and res_b:
                delta = res_b.dki_score - res_a.dki_score
                normalized = delta / (abs(res_a.dki_score) + 1e-6)
                significant = abs(normalized) >= dki_threshold
                
                delta_dki[speaker] = delta
                delta_dki_normalized[speaker] = normalized
                delta_dki_significant[speaker] = significant
        
        # Calculate risk delta
        delta_risk: float | None = None
        delta_risk_normalized: float | None = None
        delta_risk_significant = False
        
        if risk_a is not None and risk_b is not None:
            delta_risk = risk_b - risk_a
            delta_risk_normalized = delta_risk / (abs(risk_a) + 1e-6)
            delta_risk_significant = abs(delta_risk_normalized) >= risk_threshold
        
        # Calculate hedging deltas
        delta_hedging: dict[str, float] = {}
        delta_hedging_normalized: dict[str, float] = {}
        delta_hedging_significant: dict[str, bool] = {}
        
        for speaker in common_speakers:
            rate_a = hedging_a.get(speaker, 0.0)
            rate_b = hedging_b.get(speaker, 0.0)
            
            delta = rate_b - rate_a
            normalized = delta / (abs(rate_a) + 1e-6)
            significant = abs(normalized) >= hedging_threshold
            
            delta_hedging[speaker] = delta
            delta_hedging_normalized[speaker] = normalized
            delta_hedging_significant[speaker] = significant
        
        # Calculate speech act distribution deltas
        delta_speech_act: dict[str, SpeechActDistributionDelta] = {}
        
        for speaker in common_speakers:
            dist_a = speech_act_a.get(speaker, {})
            dist_b = speech_act_b.get(speaker, {})
            
            all_types = set(dist_a.keys()) | set(dist_b.keys())
            delta_dist: dict[str, float] = {}
            
            for act_type in all_types:
                delta_dist[act_type] = dist_b.get(act_type, 0.0) - dist_a.get(act_type, 0.0)
            
            # Find most changed type
            most_changed = max(delta_dist, key=delta_dist.get) if delta_dist else None
            change_mag = abs(delta_dist[most_changed]) if most_changed else 0.0
            
            delta_speech_act[speaker] = SpeechActDistributionDelta(
                speaker_id=speaker,
                distribution_a=dist_a,
                distribution_b=dist_b,
                delta_distribution=delta_dist,
                most_changed_type=most_changed,
                change_magnitude=change_mag,
            )
        
        # Calculate narrative layer deltas
        delta_narrative: dict[str, NarrativeLayerDelta] = {}
        
        for speaker in common_speakers:
            weights_a = narrative_a.get(speaker, {})
            weights_b = narrative_b.get(speaker, {})
            
            all_layers = set(weights_a.keys()) | set(weights_b.keys())
            delta_weights: dict[str, float] = {}
            
            for layer in all_layers:
                delta_weights[layer] = weights_b.get(layer, 0.0) - weights_a.get(layer, 0.0)
            
            # Find dominant layer change
            dominant_change = None
            if delta_weights:
                max_layer = max(delta_weights, key=delta_weights.get)
                dominant_change = (max_layer, delta_weights[max_layer])
            
            delta_narrative[speaker] = NarrativeLayerDelta(
                speaker_id=speaker,
                layer_weights_a=weights_a,
                layer_weights_b=weights_b,
                delta_weights=delta_weights,
                dominant_layer_change=dominant_change,
            )
        
        # Build significant changes list
        significant_changes: list[str] = []
        
        for speaker, is_sig in delta_sbi_significant.items():
            if is_sig:
                significant_changes.append(
                    f"SBI: {speaker} ({delta_sbi[speaker]:.3f}, normalized: {delta_sbi_normalized[speaker]:.3f})"
                )
        
        for speaker, is_sig in delta_dki_significant.items():
            if is_sig:
                significant_changes.append(
                    f"DKI: {speaker} ({delta_dki[speaker]:.3f}, normalized: {delta_dki_normalized[speaker]:.3f})"
                )
        
        if delta_risk_significant:
            significant_changes.append(
                f"Risk: {delta_risk:.3f} (normalized: {delta_risk_normalized:.3f})"
            )
        
        for speaker, is_sig in delta_hedging_significant.items():
            if is_sig:
                significant_changes.append(
                    f"Hedging: {speaker} ({delta_hedging[speaker]:.3f}, normalized: {delta_hedging_normalized[speaker]:.3f})"
                )
        
        return AnalysisDelta(
            session_a_id=session_a,
            session_b_id=session_b,
            delta_sbi=delta_sbi,
            delta_sbi_normalized=delta_sbi_normalized,
            delta_sbi_significant=delta_sbi_significant,
            delta_dki=delta_dki,
            delta_dki_normalized=delta_dki_normalized,
            delta_dki_significant=delta_dki_significant,
            delta_risk=delta_risk,
            delta_risk_normalized=delta_risk_normalized,
            delta_risk_significant=delta_risk_significant,
            delta_hedging=delta_hedging,
            delta_hedging_normalized=delta_hedging_normalized,
            delta_hedging_significant=delta_hedging_significant,
            delta_speech_act=delta_speech_act,
            delta_narrative=delta_narrative,
            significant_changes=significant_changes,
            speakers_in_a=speakers_a,
            speakers_in_b=speakers_b,
            common_speakers=common_speakers,
            speakers_only_in_a=speakers_only_in_a,
            speakers_only_in_b=speakers_only_in_b,
        )
    
    async def _generate_narrative(self, delta: AnalysisDelta, language: str) -> str:
        """Generate LLM narrative summary of delta analysis."""
        
        prompt = self._build_narrative_prompt(delta, language)
        
        response = await self._llm_service.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1000,
        )
        
        return response.strip()
    
    def _build_narrative_prompt(self, delta: AnalysisDelta, language: str) -> str:
        """Build prompt for LLM narrative generation."""
        
        base_prompt = f"""You are an expert diplomatic analyst. Compare two diplomatic sessions and summarize the key changes.

Session A ID: {delta.session_a_id}
Session B ID: {delta.session_b_id}

"""
        
        if delta.common_speakers:
            base_prompt += f"Common Speakers: {', '.join(sorted(delta.common_speakers))}\n"
        
        if delta.speakers_only_in_a:
            base_prompt += f"Speakers only in Session A: {', '.join(sorted(delta.speakers_only_in_a))}\n"
        
        if delta.speakers_only_in_b:
            base_prompt += f"Speakers only in Session B: {', '.join(sorted(delta.speakers_only_in_b))}\n"
        
        base_prompt += "\n=== SIGNIFICANT CHANGES ===\n"
        
        if delta.significant_changes:
            for change in delta.significant_changes:
                base_prompt += f"- {change}\n"
        else:
            base_prompt += "No significant changes detected.\n"
        
        base_prompt += f"\nMost Drifted Speaker: {delta.most_drifted_speaker or 'N/A'}\n"
        base_prompt += f"Most Drifted Dimension: {delta.most_drifted_dimension}\n"
        
        base_prompt += """
Provide a concise 3-4 paragraph summary in {language} that:
1. Highlights the most important changes
2. Identifies which speaker(s) shifted the most
3. Explains what dimensions changed most significantly
4. Provides context on whether these changes represent escalation or de-escalation

Focus on actionable insights for diplomatic analysts.
"""
        
        return base_prompt
    
    def _extract_key_insights(self, delta: AnalysisDelta) -> list[str]:
        """Extract top-N key insights from delta analysis."""
        insights: list[str] = []
        
        # Insight 1: Most drifted speaker
        if delta.most_drifted_speaker:
            insights.append(
                f"Speaker '{delta.most_drifted_speaker}' shows the highest aggregate drift"
            )
        
        # Insight 2: Most drifted dimension
        insights.append(
            f"'{delta.most_drifted_dimension}' dimension shows the highest aggregate change"
        )
        
        # Insight 3: Risk change
        if delta.delta_risk_significant:
            direction = "increased" if delta.delta_risk and delta.delta_risk > 0 else "decreased"
            insights.append(f"Overall risk score {direction} significantly")
        
        # Insight 4: Speaker additions/removals
        if delta.speakers_only_in_a:
            insights.append(
                f"Speakers exited: {', '.join(sorted(delta.speakers_only_in_a))}"
            )
        if delta.speakers_only_in_b:
            insights.append(
                f"Speakers entered: {', '.join(sorted(delta.speakers_only_in_b))}"
            )
        
        # Insight 5: Top individual SBI changes
        sbi_changes = [
            (speaker, delta.delta_sbi_normalized[speaker])
            for speaker, is_sig in delta.delta_sbi_significant.items()
            if is_sig
        ]
        sbi_changes.sort(key=lambda x: abs(x[1]), reverse=True)
        
        if sbi_changes:
            top_sbi = sbi_changes[0]
            insights.append(
                f"Largest SBI shift: {top_sbi[0]} ({top_sbi[1]:.3f} normalized)"
            )
        
        return insights[:5]  # Return top 5 insights
    
    def _assess_risk(self, delta: AnalysisDelta) -> str:
        """Assess risk based on delta analysis."""
        
        if delta.delta_risk_significant:
            if delta.delta_risk and delta.delta_risk > 0:
                return "HIGH_RISK_ESCALATION"
            else:
                return "RISK_DEESCALATION"
        
        if delta.total_significant_changes > 5:
            return "MODERATE_CONCERN"
        
        return "STABLE"
    
    def _generate_recommendation(self, delta: AnalysisDelta) -> str:
        """Generate actionable recommendation based on delta analysis."""
        
        if delta.delta_risk_significant and delta.delta_risk and delta.delta_risk > 0:
            return "Monitor closely for escalation signals. Consider immediate diplomatic engagement."
        
        if delta.total_significant_changes == 0:
            return "No immediate action required. Continue routine monitoring."
        
        if delta.most_drifted_speaker:
            return f"Focus diplomatic attention on {delta.most_drifted_speaker} due to significant position shift."
        
        return "Review detailed delta metrics for specific areas of concern."
```

#### 2.3. Repository Protocols

**2.3.1. New Repository Protocols**

```python
# domain/services/compare_sessions_protocols.py (YENİ DOSYA)

from typing import Protocol

from bb_paxdata.domain.models.sbi_models import SpeakerPosition
from bb_paxdata.domain.models.dki import DKIResult


class ISBIRepository(Protocol):
    """Protocol for SBI data access."""
    
    async def get_by_session(self, session_id: str) -> list[SpeakerPosition]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[SpeakerPosition]: ...
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> SpeakerPosition | None: ...


class IDKIRepository(Protocol):
    """Protocol for DKI data access."""
    
    async def get_by_session(self, session_id: str) -> list[DKIResult]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[DKIResult]: ...
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> DKIResult | None: ...


class IAnalysisRepository(Protocol):
    """Protocol for Analysis data access."""
    
    async def get_by_session(self, session_id: str) -> list[Analysis]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[Analysis]: ...
```

**2.3.2. Repository Implementations**

```python
# infrastructure/db/repositories/sbi_repository.py (YENİ DOSYA)

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bb_paxdata.domain.services.compare_sessions_protocols import ISBIRepository
from bb_paxdata.domain.models.sbi_models import SpeakerPosition
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository
from bb_paxdata.infrastructure.db.sbi_table import SpeakerPositionTable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SBIRepository(BaseRepository[SpeakerPositionTable], ISBIRepository):
    """Repository for SBI data access."""
    
    model_class = SpeakerPositionTable
    
    async def get_by_session(self, session_id: str) -> list[SpeakerPosition]:
        """Get all speaker positions for a session."""
        stmt = select(self.model_class).where(
            self.model_class.session_id == session_id
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [row.to_domain() for row in rows]
    
    async def get_by_speaker(self, speaker_id: str) -> list[SpeakerPosition]:
        """Get all speaker positions for a speaker across sessions."""
        stmt = select(self.model_class).where(
            self.model_class.speaker_id == speaker_id
        ).order_by(self.model_class.computed_at)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [row.to_domain() for row in rows]
    
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> SpeakerPosition | None:
        """Get speaker position for a specific session and speaker."""
        stmt = select(self.model_class).where(
            self.model_class.session_id == session_id,
            self.model_class.speaker_id == speaker_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.to_domain() if row else None


# infrastructure/db/repositories/dki_repository.py (GÜNCELLEME - mevcut dosya)

# Mevcut DKIRepository'ye protocol implementasyonu eklenmeli
# get_by_session metodu zaten varsa, protocol'e uyumlu hale getirilmeli
```

#### 2.4. API Layer Design

**2.4.1. Request/Response Schemas**

```python
# interfaces/api/schemas.py (GÜNCELLEME)

from pydantic import BaseModel, Field
from typing import Optional


class CompareSessionsRequest(BaseModel):
    """Request schema for session comparison."""
    
    session_a_id: str = Field(..., description="First session/panel ID")
    session_b_id: str = Field(..., description="Second session/panel ID")
    sbi_threshold: float = Field(0.15, ge=0.0, le=1.0, description="SBI significance threshold")
    dki_threshold: float = Field(0.15, ge=0.0, le=1.0, description="DKI significance threshold")
    risk_threshold: float = Field(0.10, ge=0.0, le=1.0, description="Risk significance threshold")
    hedging_threshold: float = Field(0.10, ge=0.0, le=1.0, description="Hedging significance threshold")
    include_narrative: bool = Field(True, description="Include LLM-generated narrative summary")
    narrative_language: str = Field("en", description="Language for narrative summary")


class MetricDeltaResponse(BaseModel):
    """Response schema for single metric delta."""
    
    speaker_id: Optional[str] = Field(None, description="Speaker ID (None for aggregate metrics)")
    value_a: Optional[float] = Field(None, description="Value in session A")
    value_b: Optional[float] = Field(None, description="Value in session B")
    delta: Optional[float] = Field(None, description="Raw delta (B - A)")
    delta_normalized: Optional[float] = Field(None, description="Normalized delta")
    is_significant: bool = Field(False, description="Whether change exceeds threshold")


class SpeechActDeltaResponse(BaseModel):
    """Response schema for speech act distribution delta."""
    
    speaker_id: str
    distribution_a: dict[str, float]
    distribution_b: dict[str, float]
    delta_distribution: dict[str, float]
    most_changed_type: Optional[str]
    change_magnitude: float


class NarrativeLayerDeltaResponse(BaseModel):
    """Response schema for narrative layer delta."""
    
    speaker_id: str
    layer_weights_a: dict[str, float]
    layer_weights_b: dict[str, float]
    delta_weights: dict[str, float]
    dominant_layer_change: Optional[tuple[str, float]]


class AnalysisDeltaResponse(BaseModel):
    """Response schema for complete analysis delta."""
    
    session_a_id: str
    session_b_id: str
    comparison_timestamp: str
    
    delta_sbi: dict[str, float]
    delta_sbi_normalized: dict[str, float]
    delta_sbi_significant: dict[str, bool]
    
    delta_dki: dict[str, float]
    delta_dki_normalized: dict[str, float]
    delta_dki_significant: dict[str, bool]
    
    delta_risk: Optional[float]
    delta_risk_normalized: Optional[float]
    delta_risk_significant: bool
    
    delta_hedging: dict[str, float]
    delta_hedging_normalized: dict[str, float]
    delta_hedging_significant: dict[str, bool]
    
    delta_speech_act: dict[str, SpeechActDeltaResponse]
    delta_narrative: dict[str, NarrativeLayerDeltaResponse]
    
    significant_changes: list[str]
    
    speakers_in_a: set[str]
    speakers_in_b: set[str]
    common_speakers: set[str]
    speakers_only_in_a: set[str]
    speakers_only_in_b: set[str]
    
    most_drifted_speaker: Optional[str]
    most_drifted_dimension: str
    total_significant_changes: int


class ContrastReportResponse(BaseModel):
    """Response schema for complete contrast report."""
    
    report_id: str
    delta: AnalysisDeltaResponse
    
    narrative_summary: str
    narrative_summary_model: str
    narrative_summary_timestamp: str
    
    most_drifted_speaker: Optional[str]
    most_drifted_dimension: str
    
    key_insights: list[str]
    risk_assessment: Optional[str]
    risk_level_changed: bool
    recommendation: Optional[str]
    
    generated_at: str


class CompareSessionsResponse(BaseModel):
    """Response schema for session comparison endpoint."""
    
    success: bool
    contrast_report: Optional[ContrastReportResponse] = None
    analysis_delta: Optional[AnalysisDeltaResponse] = None
    errors: list[str] = Field(default_factory=list)
```

**2.4.2. API Endpoint**

```python
# interfaces/api/routers/v1/compare.py (YENİ DOSYA)

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.session import get_db
from bb_paxdata.interfaces.api.schemas import (
    CompareSessionsRequest,
    CompareSessionsResponse,
)
from bb_paxdata.application.use_cases.compare_sessions import (
    CompareSessionsUseCase,
    CompareSessionsInput,
)

router = APIRouter(prefix="/compare", tags=["comparison"])


@router.post("/sessions", response_model=CompareSessionsResponse)
async def compare_sessions(
    request: CompareSessionsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two sessions/panels and generate contrast report.
    
    Calculates deltas for all metrics (SBI, DKI, Risk, Hedging, Speech Act, Narrative)
    and generates an LLM-powered narrative summary of changes.
    """
    # Initialize repositories (dependency injection pattern)
    from bb_paxdata.infrastructure.db.repositories.sbi_repository import SBIRepository
    from bb_paxdata.infrastructure.db.repositories.dki_repository import DKIRepository
    from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository
    from bb_paxdata.infrastructure.db.repositories.country_repository import (
        BilateralSentimentRepository,
    )
    from bb_paxdata.domain.services.ai_analyst import AIAnalyst  # For LLM service
    
    sbi_repo = SBIRepository(db)
    dki_repo = DKIRepository(db)
    analysis_repo = AnalysisRepository(db)
    bilateral_repo = BilateralSentimentRepository(db)
    
    # LLM service (optional - can be None if narrative not requested)
    llm_service = AIAnalyst() if request.include_narrative else None
    
    # Initialize use case
    use_case = CompareSessionsUseCase(
        sbi_repository=sbi_repo,
        dki_repository=dki_repo,
        analysis_repository=analysis_repo,
        bilateral_repository=bilateral_repo,
        llm_service=llm_service,
    )
    
    # Execute comparison
    input_data = CompareSessionsInput(
        session_a_id=request.session_a_id,
        session_b_id=request.session_b_id,
        sbi_threshold=request.sbi_threshold,
        dki_threshold=request.dki_threshold,
        risk_threshold=request.risk_threshold,
        hedging_threshold=request.hedging_threshold,
        include_narrative=request.include_narrative,
        narrative_language=request.narrative_language,
    )
    
    output = await use_case.execute(input_data)
    
    if not output.succeeded:
        raise HTTPException(
            status_code=500,
            detail=f"Session comparison failed: {', '.join(output.errors)}"
        )
    
    # Convert domain models to response schemas
    from bb_paxdata.interfaces.api.schemas import (
        AnalysisDeltaResponse,
        ContrastReportResponse,
    )
    
    delta_response = None
    if output.analysis_delta:
        delta_response = AnalysisDeltaResponse(
            session_a_id=output.analysis_delta.session_a_id,
            session_b_id=output.analysis_delta.session_b_id,
            comparison_timestamp=output.analysis_delta.comparison_timestamp.isoformat(),
            delta_sbi=output.analysis_delta.delta_sbi,
            delta_sbi_normalized=output.analysis_delta.delta_sbi_normalized,
            delta_sbi_significant=output.analysis_delta.delta_sbi_significant,
            delta_dki=output.analysis_delta.delta_dki,
            delta_dki_normalized=output.analysis_delta.delta_dki_normalized,
            delta_dki_significant=output.analysis_delta.delta_dki_significant,
            delta_risk=output.analysis_delta.delta_risk,
            delta_risk_normalized=output.analysis_delta.delta_risk_normalized,
            delta_risk_significant=output.analysis_delta.delta_risk_significant,
            delta_hedging=output.analysis_delta.delta_hedging,
            delta_hedging_normalized=output.analysis_delta.delta_hedging_normalized,
            delta_hedging_significant=output.analysis_delta.delta_hedging_significant,
            delta_speech_act={},  # Convert SpeechActDistributionDelta
            delta_narrative={},  # Convert NarrativeLayerDelta
            significant_changes=output.analysis_delta.significant_changes,
            speakers_in_a=output.analysis_delta.speakers_in_a,
            speakers_in_b=output.analysis_delta.speakers_in_b,
            common_speakers=output.analysis_delta.common_speakers,
            speakers_only_in_a=output.analysis_delta.speakers_only_in_a,
            speakers_only_in_b=output.analysis_delta.speakers_only_in_b,
            most_drifted_speaker=output.analysis_delta.most_drifted_speaker,
            most_drifted_dimension=output.analysis_delta.most_drifted_dimension,
            total_significant_changes=output.analysis_delta.total_significant_changes,
        )
    
    contrast_response = None
    if output.contrast_report:
        contrast_response = ContrastReportResponse(
            report_id=output.contrast_report.report_id,
            delta=delta_response,  # Use converted delta
            narrative_summary=output.contrast_report.narrative_summary,
            narrative_summary_model=output.contrast_report.narrative_summary_model,
            narrative_summary_timestamp=output.contrast_report.narrative_summary_timestamp.isoformat(),
            most_drifted_speaker=output.contrast_report.most_drifted_speaker,
            most_drifted_dimension=output.contrast_report.most_drifted_dimension,
            key_insights=output.contrast_report.key_insights,
            risk_assessment=output.contrast_report.risk_assessment,
            risk_level_changed=output.contrast_report.risk_level_changed,
            recommendation=output.contrast_report.recommendation,
            generated_at=output.contrast_report.generated_at.isoformat(),
        )
    
    return CompareSessionsResponse(
        success=output.success,
        contrast_report=contrast_response,
        analysis_delta=delta_response,
        errors=list(output.errors),
    )


@router.get("/sessions/available")
async def list_available_sessions(
    db: AsyncSession = Depends(get_db),
):
    """
    List all available session/panel IDs for comparison.
    """
    from bb_paxdata.infrastructure.db.repositories.sbi_repository import SBIRepository
    from sqlalchemy import select, func
    
    sbi_repo = SBIRepository(db)
    
    # Get unique session IDs from SBI table
    stmt = select(func.distinct(sbi_repo.model_class.session_id))
    result = await db.execute(stmt)
    session_ids = sorted([row[0] for row in result.all()])
    
    return {"session_ids": session_ids}
```

#### 2.5. Frontend Integration (High-Level)

**2.5.1. Component Structure**

```
frontend/
├── src/
│   ├── components/
│   │   ├── comparison/
│   │   │   ├── SessionSelector.tsx
│   │   │   ├── DeltaVisualization.tsx
│   │   │   ├── MetricDeltaCard.tsx
│   │   │   ├── NarrativeSummary.tsx
│   │   │   └── ComparisonReport.tsx
│   ├── pages/
│   │   └── CompareSessions.tsx
│   └── services/
│       └── comparisonApi.ts
```

**2.5.2. Key Components (Pseudocode)**

```typescript
// services/comparisonApi.ts
export const comparisonApi = {
  compareSessions: async (sessionA: string, sessionB: string, options: CompareOptions) => {
    const response = await fetch('/api/v1/compare/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_a_id: sessionA,
        session_b_id: sessionB,
        ...options,
      }),
    });
    return response.json();
  },
  
  listAvailableSessions: async () => {
    const response = await fetch('/api/v1/compare/sessions/available');
    return response.json();
  },
};

// components/comparison/SessionSelector.tsx
interface SessionSelectorProps {
  onSessionsSelected: (sessionA: string, sessionB: string) => void;
}

// components/comparison/MetricDeltaCard.tsx
interface MetricDeltaCardProps {
  metricName: string;
  delta: number;
  normalizedDelta: number;
  isSignificant: boolean;
  speakerId?: string;
}

// components/comparison/NarrativeSummary.tsx
interface NarrativeSummaryProps {
  summary: string;
  model: string;
  timestamp: string;
}

// pages/CompareSessions.tsx
export const CompareSessionsPage = () => {
  const [sessionA, setSessionA] = useState<string>('');
  const [sessionB, setSessionB] = useState<string>('');
  const [report, setReport] = useState<ContrastReport | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleCompare = async () => {
    setLoading(true);
    const result = await comparisonApi.compareSessions(sessionA, sessionB, {
      include_narrative: true,
      narrative_language: 'en',
    });
    setReport(result.contrast_report);
    setLoading(false);
  };
  
  return (
    <div>
      <SessionSelector onSessionsSelected={(a, b) => { setSessionA(a); setSessionB(b); }} />
      <Button onClick={handleCompare} disabled={loading}>
        Compare Sessions
      </Button>
      {report && <ComparisonReport report={report} />}
    </div>
  );
};
```

---

### 3. IMPLEMENTATION ROADMAP

#### 3.1. Phase 1: Core Models (1-2 gün)

**Tasks:**
1. Create `domain/models/analysis_delta.py`
   - Implement `AnalysisDelta` class
   - Implement `MetricDelta`, `SpeechActDistributionDelta`, `NarrativeLayerDelta` dataclasses
   - Add computed properties (`most_drifted_speaker`, `most_drifted_dimension`, `total_significant_changes`)
   - Write unit tests for delta calculations

2. Create `domain/models/contrast_report.py`
   - Implement `ContrastReport` class
   - Add field validations
   - Write unit tests

3. Update `domain/models/__init__.py`
   - Export new models

**Success Criteria:**
- All models pass Pydantic validation
- Unit tests achieve >90% coverage
- Models are properly exported

#### 3.2. Phase 2: Repository Layer (1-2 gün)

**Tasks:**
1. Create `domain/services/compare_sessions_protocols.py`
   - Define `ISBIRepository`, `IDKIRepository`, `IAnalysisRepository` protocols
   - Document method signatures

2. Create `infrastructure/db/repositories/sbi_repository.py`
   - Implement `SBIRepository` class
   - Implement `to_domain()` method in `SpeakerPositionTable` (if not exists)
   - Write integration tests

3. Update `infrastructure/db/repositories/dki_repository.py`
   - Ensure `DKIRepository` implements `IDKIRepository` protocol
   - Add missing methods if needed
   - Write integration tests

4. Create `infrastructure/db/repositories/analysis_repository.py` (if not exists)
   - Implement `AnalysisRepository` class
   - Add methods: `get_by_session`, `get_by_speaker`
   - Write integration tests

**Success Criteria:**
- All repositories implement their protocols
- Integration tests pass with test database
- Repository methods return correct domain models

#### 3.3. Phase 3: Use Case Implementation (2-3 gün)

**Tasks:**
1. Create `application/use_cases/compare_sessions.py`
   - Implement `CompareSessionsInput` and `CompareSessionsOutput` dataclasses
   - Implement `CompareSessionsUseCase` class
   - Implement all private methods:
     - `_fetch_sbi_data`
     - `_fetch_dki_data`
     - `_fetch_risk_data`
     - `_fetch_hedging_data`
     - `_fetch_speech_act_data`
     - `_fetch_narrative_data`
     - `_calculate_delta`
     - `_generate_narrative`
     - `_build_narrative_prompt`
     - `_extract_key_insights`
     - `_assess_risk`
     - `_generate_recommendation`
   - Add comprehensive error handling
   - Add structured logging

2. Write unit tests for use case
   - Mock all repositories
   - Test delta calculation logic
   - Test narrative generation (with mocked LLM)
   - Test error scenarios

3. Write integration tests
   - Use test database with sample data
   - Test end-to-end comparison flow
   - Verify performance (< 2 seconds for delta calculation)

**Success Criteria:**
- Unit tests achieve >85% coverage
- Integration tests pass
- Delta calculation completes in < 2 seconds
- All error scenarios handled gracefully

#### 3.4. Phase 4: API Layer (1-2 gün)

**Tasks:**
1. Update `interfaces/api/schemas.py`
   - Add request/response schemas:
     - `CompareSessionsRequest`
     - `MetricDeltaResponse`
     - `SpeechActDeltaResponse`
     - `NarrativeLayerDeltaResponse`
     - `AnalysisDeltaResponse`
     - `ContrastReportResponse`
     - `CompareSessionsResponse`

2. Create `interfaces/api/routers/v1/compare.py`
   - Implement `POST /compare/sessions` endpoint
   - Implement `GET /compare/sessions/available` endpoint
   - Add dependency injection for repositories
   - Add error handling
   - Add permission checking

3. Register router in main app
   - Import and include router in `interfaces/api/app.py`

4. Write API tests
   - Test endpoint with valid requests
   - Test endpoint with invalid requests
   - Test error scenarios
   - Verify response schemas

**Success Criteria:**
- API endpoints return correct responses
- API tests pass
- Endpoints are properly documented (OpenAPI/Swagger)

#### 3.5. Phase 5: LLM Integration (1 gün)

**Tasks:**
1. Integrate with existing `AIAnalyst` service
   - Ensure `AIAnalyst` implements required interface
   - Test narrative generation with actual LLM
   - Calibrate prompt for optimal output

2. Add LLM fallback
   - If LLM service fails, return delta without narrative
   - Log LLM failures appropriately

3. Add LLM cost tracking
   - Track token usage for narrative generation
   - Add metrics for monitoring

**Success Criteria:**
- LLM generates coherent narratives
- Fallback mechanism works correctly
- Cost tracking is implemented

#### 3.6. Phase 6: Frontend Integration (3-5 gün)

**Tasks:**
1. Create comparison API service
   - Implement TypeScript API client
   - Add type definitions

2. Create session selector component
   - Dropdown for session A
   - Dropdown for session B
   - Validation to prevent comparing same session

3. Create delta visualization components
   - Metric delta cards with color coding
   - Bar charts for normalized deltas
   - Speaker-level delta breakdown

4. Create narrative summary component
   - Display LLM-generated summary
   - Show model and timestamp metadata

5. Create comparison report page
   - Integrate all components
   - Add export functionality (PDF/Markdown)

6. Add responsive design
   - Ensure components work on mobile
   - Optimize for different screen sizes

**Success Criteria:**
- Frontend components render correctly
- User can successfully compare sessions
- Export functionality works
- Responsive design passes all breakpoints

#### 3.7. Phase 7: Testing & QA (2-3 gün)

**Tasks:**
1. Performance testing
   - Load test API endpoint
   - Verify < 2 second response time under load
   - Optimize if necessary

2. Manual testing
   - Test with real session data
   - Verify delta calculations are accurate
   - Verify narrative summaries are useful

3. User acceptance testing
   - Demo to stakeholders
   - Gather feedback
   - Iterate based on feedback

4. Documentation
   - Update API documentation
   - Write user guide for frontend
   - Add developer documentation

**Success Criteria:**
- Performance benchmarks met
- Manual testing passes
- Stakeholder approval received
- Documentation complete

---

### 4. EDGE CASES & ERROR HANDLING

#### 4.1. Data Availability Issues

**Scenario:** One or both sessions have incomplete data

**Handling:**
- If a metric is missing in one session, treat it as None
- Log warning for missing data
- Include in `significant_changes` list as "data unavailable"
- Allow comparison to proceed with available metrics

**Example:**
```python
if risk_a is None or risk_b is None:
    logger.warning(
        "compare_sessions.risk_data_unavailable",
        session_a=session_a,
        session_b=session_b,
        risk_a_available=risk_a is not None,
        risk_b_available=risk_b is not None,
    )
    delta_risk = None
    delta_risk_normalized = None
    delta_risk_significant = False
```

#### 4.2. Speaker Mismatch

**Scenario:** Sessions have different sets of speakers

**Handling:**
- Calculate deltas only for common speakers
- Track speakers only in A and only in B
- Include speaker changes in `significant_changes`
- Highlight speaker additions/removals in narrative

**Example:**
```python
speakers_only_in_a = speakers_a - speakers_b
speakers_only_in_b = speakers_b - speakers_a

if speakers_only_in_a:
    significant_changes.append(
        f"Speakers exited session: {', '.join(sorted(speakers_only_in_a))}"
    )
```

#### 4.3. Zero Baseline Values

**Scenario:** Baseline value is 0, causing division by zero in normalization

**Handling:**
- Add epsilon (ε = 1e-6) to denominator
- Log warning when epsilon is used
- Consider alternative normalization for zero baselines

**Example:**
```python
normalized = delta / (abs(value_a) + 1e-6)
if abs(value_a) < 1e-6:
    logger.warning(
        "compare_sessions.zero_baseline",
        metric=metric_name,
        speaker=speaker_id,
        delta=delta,
    )
```

#### 4.4. LLM Service Failure

**Scenario:** LLM service is unavailable or returns error

**Handling:**
- Catch LLM exceptions
- Return delta without narrative
- Set `narrative_summary` to error message
- Log error with full context
- Allow user to retry narrative generation

**Example:**
```python
try:
    narrative_summary = await self._generate_narrative(delta, language)
except Exception as exc:
    logger.error(
        "compare_sessions.narrative_generation_failed",
        session_a=session_a,
        session_b=session_b,
        error=str(exc),
    )
    narrative_summary = "Narrative generation failed. Please try again later."
```

#### 4.5. Repository Query Failures

**Scenario:** Database query fails or times out

**Handling:**
- Catch database exceptions
- Return partial results if possible
- Include error in output errors list
- Log error with full context
- Set success=False if critical data missing

**Example:**
```python
try:
    sbi_a = await self._fetch_sbi_data(session_a)
except Exception as exc:
    logger.error(
        "compare_sessions.sbi_fetch_failed",
        session=session_a,
        error=str(exc),
    )
    errors.append(f"SBI data fetch failed for session {session_a}: {exc}")
    sbi_a = {}
```

#### 4.6. Invalid Session IDs

**Scenario:** User provides non-existent session IDs

**Handling:**
- Validate session IDs exist before comparison
- Return clear error message for invalid IDs
- Suggest available session IDs
- Log validation failure

**Example:**
```python
# Validate session IDs exist
available_sessions = await self._get_available_sessions()
if session_a not in available_sessions:
    errors.append(f"Session A '{session_a}' not found")
if session_b not in available_sessions:
    errors.append(f"Session B '{session_b}' not found")

if errors:
    return CompareSessionsOutput(success=False, errors=tuple(errors))
```

---

### 5. PERFORMANCE OPTIMIZATION

#### 5.1. Database Query Optimization

**Strategies:**
1. Use indexed columns for session_id and speaker_id
2. Batch queries where possible
3. Use selectinload for eager loading
4. Add query result caching for repeated comparisons

**Example:**
```python
# Add composite index for session-speaker queries
__table_args__ = (
    Index("ix_sbi_session_speaker", "session_id", "speaker_id", unique=True),
)
```

#### 5.2. Delta Calculation Optimization

**Strategies:**
1. Pre-calculate aggregate metrics (risk, hedging) during analysis
2. Store pre-computed speaker-level aggregates
3. Use vectorized operations for batch calculations
4. Cache delta results for repeated comparisons

**Example:**
```python
# Pre-calculate aggregate risk during analysis
# Store in analysis table or separate aggregate table
class SessionAggregate(Base):
    __tablename__ = "session_aggregates"
    
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    avg_risk_score: Mapped[float] = mapped_column(Float)
    avg_hedging_rate: Mapped[dict[str, float]] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(DateTime)
```

#### 5.3. LLM Optimization

**Strategies:**
1. Use smaller, faster models for narrative generation
2. Cache narrative summaries for repeated comparisons
3. Implement prompt compression
4. Use streaming responses for long narratives

**Example:**
```python
# Cache narrative summaries
@lru_cache(maxsize=100)
async def _generate_narrative_cached(
    delta_hash: str, language: str
) -> str:
    return await self._generate_narrative(delta, language)
```

#### 5.4. API Response Optimization

**Strategies:**
1. Implement pagination for large delta results
2. Use compression for large JSON responses
3. Implement field selection (partial response)
4. Add ETag support for conditional requests

**Example:**
```python
# Field selection
@router.post("/sessions/compare")
async def compare_sessions(
    request: CompareSessionsRequest,
    fields: list[str] = Query(None, description="Fields to include in response"),
):
    # Only return requested fields
    pass
```

---

### 6. TESTING STRATEGY

#### 6.1. Unit Tests

**Coverage Targets:**
- Domain models: >90%
- Use case logic: >85%
- Repository methods: >80%

**Test Categories:**
1. Model validation tests
2. Delta calculation tests
3. Normalization tests
4. Significance threshold tests
5. Narrative prompt building tests
6. Insight extraction tests

**Example:**
```python
# tests/unit/domain/test_analysis_delta.py
def test_sbi_delta_calculation():
    delta = AnalysisDelta(
        session_a_id="session1",
        session_b_id="session2",
        delta_sbi={"speaker1": 0.2},
        delta_sbi_normalized={"speaker1": 0.25},
        delta_sbi_significant={"speaker1": True},
        # ... other fields
    )
    
    assert delta.most_drifted_speaker == "speaker1"
    assert delta.total_significant_changes >= 1
```

#### 6.2. Integration Tests

**Test Scenarios:**
1. End-to-end comparison with real database
2. Repository integration tests
3. API endpoint integration tests
4. LLM integration tests

**Example:**
```python
# tests/integration/test_compare_sessions_integration.py
async def test_full_comparison_flow(test_db):
    # Setup: Insert test data
    await insert_test_sbi_data(test_db, "session1")
    await insert_test_sbi_data(test_db, "session2")
    
    # Execute
    use_case = make_compare_sessions_use_case(test_db)
    output = await use_case.execute(
        CompareSessionsInput(session_a_id="session1", session_b_id="session2")
    )
    
    # Assert
    assert output.succeeded
    assert output.analysis_delta is not None
    assert output.contrast_report is not None
```

#### 6.3. Performance Tests

**Test Scenarios:**
1. Delta calculation performance (< 2 seconds)
2. API endpoint response time (< 3 seconds)
3. Database query performance
4. LLM generation latency

**Example:**
```python
# tests/performance/test_delta_calculation.py
def test_delta_calculation_performance():
    start_time = time.time()
    
    # Execute delta calculation
    delta = calculate_delta(...)
    
    elapsed = time.time() - start_time
    assert elapsed < 2.0, f"Delta calculation took {elapsed:.2f}s, expected < 2s"
```

#### 6.4. Manual Testing

**Test Scenarios:**
1. Compare sessions with significant changes
2. Compare sessions with minimal changes
3. Compare sessions with missing data
4. Compare sessions with different speakers
5. Verify narrative quality
6. Verify visualizations

**Test Data:**
- Use real diplomatic session data
- Include edge cases (empty sessions, single speaker, etc.)
- Test with different language settings

---

### 7. DEPLOYMENT CONSIDERATIONS

#### 7.1. Database Migrations

**Migration Steps:**
1. No new tables required (uses existing tables)
2. Add indexes if not present:
   - `speaker_positions(session_id, speaker_id)` - may already exist
   - `dki_results(session_id, speaker_id)` - may need to add
3. Add aggregate tables for performance (optional)

**Example Migration:**
```python
# alembic/versions/XXXX_add_comparison_indexes.py
def upgrade():
    op.create_index(
        'ix_dki_session_speaker',
        'dki_results',
        ['session_id', 'speaker_id']
    )

def downgrade():
    op.drop_index('ix_dki_session_speaker', table_name='dki_results')
```

#### 7.2. Configuration

**New Configuration Options:**
```python
# config/settings.py
class Settings(BaseSettings):
    # Comparison thresholds
    COMPARISON_SBI_THRESHOLD: float = 0.15
    COMPARISON_DKI_THRESHOLD: float = 0.15
    COMPARISON_RISK_THRESHOLD: float = 0.10
    COMPARISON_HEDGING_THRESHOLD: float = 0.10
    
    # LLM settings
    COMPARISON_NARRATIVE_ENABLED: bool = True
    COMPARISON_NARRATIVE_MODEL: str = "gpt-4o-mini"
    COMPARISON_NARRATIVE_MAX_TOKENS: int = 1000
    
    # Performance
    COMPARISON_CACHE_ENABLED: bool = True
    COMPARISON_CACHE_TTL_SECONDS: int = 3600
```

#### 7.3. Monitoring

**Metrics to Track:**
1. Comparison request count
2. Comparison success/failure rate
3. Delta calculation latency
4. LLM generation latency
5. LLM token usage
6. Cache hit rate

**Example Metrics:**
```python
# application/metrics.py
from prometheus_client import Counter, Histogram

comparison_requests_total = Counter(
    'comparison_requests_total',
    'Total comparison requests',
    ['status']  # success, failure
)

comparison_delta_duration = Histogram(
    'comparison_delta_duration_seconds',
    'Delta calculation duration'
)

comparison_llm_duration = Histogram(
    'comparison_llm_duration_seconds',
    'LLM narrative generation duration'
)

comparison_llm_tokens = Histogram(
    'comparison_llm_tokens_total',
    'LLM token usage for narrative generation'
)
```

#### 7.4. Rollback Plan

**Rollback Steps:**
1. Disable API endpoint (remove router from app)
2. Revert database migrations (if any)
3. Restore previous configuration
4. Clear cache

**Rollback Triggers:**
- High error rate (>10%)
- Performance degradation (>5s response time)
- Data quality issues
- User complaints

---

### 8. DEPENDENCIES

#### 8.1. Internal Dependencies

**Required Components:**
1. `SpeakerPositionTable` (SBI data)
2. `DKIResultModel` (DKI data)
3. `AISentenceAnalysis` (risk, hedging, speech act data)
4. `BilateralSentiment` (bilateral sentiment data)
5. `AIAnalyst` (LLM service)
6. Existing repository infrastructure

**Optional Components:**
1. `NarrativeSalienceTracker` (narrative data - can be stubbed)
2. Caching layer (Redis, etc.)

#### 8.2. External Dependencies

**Python Packages:**
- `pydantic>=2.0` (already in use)
- `sqlalchemy>=2.0` (already in use)
- `structlog` (already in use)
- No new packages required for core functionality

**Optional Packages:**
- `redis` (for caching)
- `prometheus-client` (for metrics)
- `markdown` (for export functionality)

#### 8.3. Dependency Graph

```
CompareSessionsUseCase
├── ISBIRepository
│   └── SpeakerPositionTable
├── IDKIRepository
│   └── DKIResultModel
├── IAnalysisRepository
│   └── AISentenceAnalysis
├── IBilateralSentimentRepository
│   └── BilateralSentiment
└── LLMServiceProtocol
    └── AIAnalyst
        └── OpenAI/Anthropic API
```

---

### 9. SECURITY CONSIDERATIONS

#### 9.1. Access Control

**Permissions:**
- `view_comparison`: View comparison results
- `create_comparison`: Create new comparisons
- `export_comparison`: Export comparison reports

**Implementation:**
```python
@router.post("/sessions/compare")
async def compare_sessions(
    request: CompareSessionsRequest,
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("create_comparison")),
):
    # Implementation
```

#### 9.2. Data Privacy

**Considerations:**
- Comparison results may contain sensitive diplomatic information
- Implement data retention policies
- Audit log for all comparison requests
- Encrypt comparison results at rest (optional)

#### 9.3. Rate Limiting

**Implementation:**
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/sessions/compare")
@limiter.limit("10/minute")
async def compare_sessions(...):
    # Implementation
```

#### 9.4. Input Validation

**Validations:**
1. Session ID format validation
2. Threshold range validation (0.0 to 1.0)
3. Language code validation
4. Prevent comparing same session (A == B)

**Example:**
```python
class CompareSessionsRequest(BaseModel):
    session_a_id: str = Field(..., min_length=1, max_length=100)
    session_b_id: str = Field(..., min_length=1, max_length=100)
    sbi_threshold: float = Field(0.15, ge=0.0, le=1.0)
    # ... other fields
    
    @model_validator
    def validate_sessions_different(cls, v):
        if v.session_a_id == v.session_b_id:
            raise ValueError("Session A and Session B must be different")
        return v
```

---

### 10. FUTURE ENHANCEMENTS

#### 10.1. Multi-Session Comparison

**Description:** Compare more than two sessions at once

**Implementation:**
- Extend `AnalysisDelta` to support N sessions
- Implement time-series visualization
- Add trend analysis

#### 10.2. Historical Comparison

**Description:** Compare current session against historical baseline

**Implementation:**
- Define baseline sessions (e.g., average of last 10 sessions)
- Calculate deviation from baseline
- Add baseline configuration

#### 10.3. Automated Anomaly Detection

**Description:** Automatically flag sessions with significant changes

**Implementation:**
- Schedule periodic comparisons
- Alert on significant changes
- Integrate with existing anomaly detection system

#### 10.4. Export Enhancements

**Description:** Enhanced export formats and customization

**Implementation:**
- Excel export with formatting
- PowerPoint report generation
- Customizable report templates
- Scheduled report generation

#### 10.5. Machine Learning Enhancements

**Description:** Use ML to predict future changes

**Implementation:**
- Train model on historical deltas
- Predict future session states
- Add confidence intervals to predictions

---

### 11. SUCCESS METRICS

#### 11.1. Technical Metrics

**Performance:**
- Delta calculation latency: P50 < 1s, P95 < 2s
- API response time: P50 < 2s, P95 < 3s
- LLM generation latency: P50 < 5s, P95 < 10s

**Reliability:**
- Success rate: >99%
- Error rate: <1%
- Uptime: >99.9%

**Quality:**
- Significant change precision: ≥0.85
- LLM coherence score: ≥4/5
- Test coverage: >85%

#### 11.2. Business Metrics

**Adoption:**
- Number of comparisons per week
- Number of unique users
- User retention rate

**Value:**
- Time saved vs. manual comparison
- Number of insights generated
- User satisfaction score (NPS)

#### 11.3. Monitoring Dashboard

**Key Metrics to Display:**
1. Comparison request rate (requests/minute)
2. Average delta calculation time
3. Average LLM generation time
4. Success/failure rate
5. Cache hit rate
6. Token usage rate
7. Cost per comparison

---

### 12. RISK MITIGATION

#### 12.1. Technical Risks

**Risk:** Database performance degradation
**Mitigation:**
- Add proper indexes
- Implement caching
- Monitor query performance
- Optimize slow queries

**Risk:** LLM service unavailability
**Mitigation:**
- Implement fallback mechanism
- Cache narrative summaries
- Use multiple LLM providers
- Implement retry logic

**Risk:** Data quality issues
**Mitigation:**
- Validate input data
- Handle missing data gracefully
- Log data quality issues
- Implement data quality checks

#### 12.2. Business Risks

**Risk:** Low user adoption
**Mitigation:**
- Conduct user research
- Iterate based on feedback
- Provide training and documentation
- Demonstrate value quickly

**Risk:** Incorrect delta calculations
**Mitigation:**
- Comprehensive testing
- Manual verification
- User feedback loop
- Calculation transparency

**Risk:** High LLM costs
**Mitigation:**
- Implement caching
- Use smaller models
- Optimize prompts
- Monitor costs closely

---

### 13. DOCUMENTATION REQUIREMENTS

#### 13.1. Developer Documentation

**Required Documents:**
1. Architecture overview
2. API documentation (OpenAPI/Swagger)
3. Database schema documentation
4. Repository protocol documentation
5. Use case documentation
6. Testing guide
7. Deployment guide

#### 13.2. User Documentation

**Required Documents:**
1. User guide (how to use comparison feature)
2. Interpretation guide (how to understand deltas)
3. FAQ
4. Troubleshooting guide
5. Video tutorial (optional)

#### 13.3. API Documentation

**Required Sections:**
1. Endpoint description
2. Request schema
3. Response schema
4. Error codes
5. Example requests/responses
6. Rate limits
7. Authentication requirements

---

### 14. ACCEPTANCE CRITERIA

#### 14.1. Functional Requirements

- [ ] User can compare two sessions via API
- [ ] Delta is calculated for all metrics (SBI, DKI, Risk, Hedging, Speech Act, Narrative)
- [ ] Significant changes are correctly identified
- [ ] LLM generates coherent narrative summary
- [ ] User can view comparison results in frontend
- [ ] User can export comparison report (PDF/Markdown)
- [ ] System handles missing data gracefully
- [ ] System handles speaker mismatches gracefully

#### 14.2. Non-Functional Requirements

- [ ] Delta calculation completes in < 2 seconds
- [ ] API response time < 3 seconds
- [ ] Significant change precision ≥ 0.85
- [ ] LLM coherence score ≥ 4/5
- [ ] Test coverage > 85%
- [ ] Success rate > 99%
- [ ] API is properly documented
- [ ] Code follows project style guidelines

#### 14.3. Integration Requirements

- [ ] Integrates with existing SBI repository
- [ ] Integrates with existing DKI repository
- [ ] Integrates with existing analysis repository
- [ ] Integrates with existing LLM service
- [ ] Follows existing use case pattern
- [ ] Follows existing repository pattern
- [ ] Uses existing logging infrastructure
- [ ] Uses existing error handling patterns

---

### 15. APPENDICES

#### Appendix A: Glossary

- **Session:** A single diplomatic meeting or panel discussion
- **Panel:** Group of sessions related to a specific topic or time period
- **Delta:** The difference between two values (B - A)
- **Normalized Delta:** Delta divided by baseline absolute value
- **Significant Change:** A change that exceeds a predefined threshold
- **SBI:** Speaker-Based Index, measures speaker position
- **DKI:** Discourse-Kinetic Index, measures position change over time
- **Narrative:** The story or framing used by speakers
- **Hedging:** Use of uncertain language to avoid commitment

#### Appendix B: Reference Implementations

**B.1. Similar Features in Other Systems**
- Google Analytics: Date range comparison
- GitHub: Commit comparison
- JIRA: Issue comparison between sprints

**B.2. Academic References**
- Time-series analysis for diplomatic data
- Delta calculation methodologies
- Significance threshold calibration

#### Appendix C: Configuration Examples

**C.1. Development Configuration**
```python
COMPARISON_SBI_THRESHOLD = 0.15
COMPARISON_DKI_THRESHOLD = 0.15
COMPARISON_RISK_THRESHOLD = 0.10
COMPARISON_HEDGING_THRESHOLD = 0.10
COMPARISON_NARRATIVE_ENABLED = True
COMPARISON_NARRATIVE_MODEL = "gpt-4o-mini"
COMPARISON_CACHE_ENABLED = False
```

**C.2. Production Configuration**
```python
COMPARISON_SBI_THRESHOLD = 0.15
COMPARISON_DKI_THRESHOLD = 0.15
COMPARISON_RISK_THRESHOLD = 0.10
COMPARISON_HEDGING_THRESHOLD = 0.10
COMPARISON_NARRATIVE_ENABLED = True
COMPARISON_NARRATIVE_MODEL = "gpt-4o"
COMPARISON_CACHE_ENABLED = True
COMPARISON_CACHE_TTL_SECONDS = 3600
```

#### Appendix D: Troubleshooting Guide

**D.1. Common Issues**

**Issue:** Delta calculation is slow
**Solution:** Check database indexes, enable caching, optimize queries

**Issue:** Narrative generation fails
**Solution:** Check LLM service status, verify API keys, check rate limits

**Issue:** Significant changes not detected
**Solution:** Adjust thresholds, verify data quality, check normalization logic

**Issue:** Speaker mismatch errors
**Solution:** Verify speaker IDs are consistent across sessions, check speaker mapping

#### Appendix E: Code Examples

**E.1. Complete Use Case Example**
```python
# Example usage of CompareSessionsUseCase
async def main():
    # Initialize repositories
    sbi_repo = SBIRepository(db_session)
    dki_repo = DKIRepository(db_session)
    analysis_repo = AnalysisRepository(db_session)
    bilateral_repo = BilateralSentimentRepository(db_session)
    llm_service = AIAnalyst()
    
    # Initialize use case
    use_case = CompareSessionsUseCase(
        sbi_repository=sbi_repo,
        dki_repository=dki_repo,
        analysis_repository=analysis_repo,
        bilateral_repository=bilateral_repo,
        llm_service=llm_service,
    )
    
    # Execute comparison
    input_data = CompareSessionsInput(
        session_a_id="panel_001",
        session_b_id="panel_002",
        include_narrative=True,
    )
    
    output = await use_case.execute(input_data)
    
    if output.succeeded:
        print(f"Most drifted speaker: {output.contrast_report.most_drifted_speaker}")
        print(f"Most drifted dimension: {output.contrast_report.most_drifted_dimension}")
        print(f"Narrative summary:\n{output.contrast_report.narrative_summary}")
    else:
        print(f"Errors: {output.errors}")
```

**E.2. API Request Example**
```bash
curl -X POST http://localhost:8000/api/v1/compare/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_a_id": "panel_001",
    "session_b_id": "panel_002",
    "sbi_threshold": 0.15,
    "dki_threshold": 0.15,
    "risk_threshold": 0.10,
    "hedging_threshold": 0.10,
    "include_narrative": true,
    "narrative_language": "en"
  }'
```

---

### END OF REPORT

**Report Version:** 1.0  
**Generated:** 2026-06-05  
**Author:** AI Development Agent  
**Purpose:** Complete technical specification for TASK-E01 implementation  
**Target Audience:** AI Agent for implementation and expansion
