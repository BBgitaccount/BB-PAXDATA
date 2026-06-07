# Technical Review: TASK-A04 Speech Act Classification & Illocutionary Drift

## 1. Critical Findings

### 1.1 Unmanaged Literal Type Extension in DriftEvent Schema

**Classification**: critical  
**Location**: `bb_paxdata/infrastructure/db/drift_events.py`, `bb_paxdata/domain/services/temporal.py`  
**Root Cause**: The report extends `drift_type` to include `"ILLOCUTIONARY"` by mutating a `Literal` type used in SQLAlchemy `mapped_column` and Pydantic validators. Existing SQLite rows contain values from the prior Literal set (`SENTIMENT`, `TOPIC`, `LEXICAL`, `TONE`, `RISK`). SQLAlchemy 2.0 `mapped_column(String)` stores the value at the DB level, but application-level Pydantic schemas and `Literal` validators will raise `ValidationError` when deserializing existing rows. Graph topology indicates Community 571 (DriftEvent) has 62 nodes, weak cohesion (0.04), and high betweenness centrality, meaning this schema fracture propagates to temporal analysis, KPI dashboards (Community 709), and the event bus (Community 583).  
**Proposed Resolution**:
```python
# bb_paxdata/infrastructure/db/drift_events.py
from typing import Literal, get_args

_DRIFT_TYPE_V1 = Literal["SENTIMENT", "TOPIC", "LEXICAL", "TONE", "RISK"]
_DRIFT_TYPE_V2 = Literal["SENTIMENT", "TOPIC", "LEXICAL", "TONE", "RISK", "ILLOCUTIONARY"]

def normalize_drift_type(value: str) -> _DRIFT_TYPE_V2:
    if value in get_args(_DRIFT_TYPE_V2):
        return value  # type: ignore[return-value]
    return "RISK"  # Safe fallback for legacy rows

# In the ORM model:
drift_type: Mapped[str] = mapped_column(String, nullable=False)

# In the domain validator:
from pydantic import field_validator

class DriftEvent(BaseModel):
    drift_type: _DRIFT_TYPE_V2
    
    @field_validator("drift_type", mode="before")
    @classmethod
    def _coerce_legacy(cls, v: str) -> str:
        return normalize_drift_type(v)
```
**Impact Assessment**: Without a coercion layer, existing drift event queries will crash the temporal analyzer on startup, breaking all downstream diplomatic stance metrics and HITL calibration workflows (Community 581).

### 1.2 Frozen Pydantic Model Mutation Breaks Deserialization

**Classification**: critical  
**Location**: `bb_paxdata/domain/models/frame_annotation.py`  
**Root Cause**: The report modifies `FiveWOneH`, which declares `model_config = ConfigDict(frozen=True)`. Adding the `speech_act` field is a breaking schema change. Existing serialized instances in Redis cache (Community 79), the WORM event store (Community 583), or database JSONB columns will fail to validate on load because Pydantic frozen models reject unknown fields by default (`extra="forbid"`). The graph report shows Community 583 is a cross-community bridge with 12 nodes; breaking this model breaks event replay and cache hydration across the pipeline.  
**Proposed Resolution**:
```python
# Transition strategy: temporary backward-compatible config
class FiveWOneH(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")  # 2-release transition window
    
    who: list[str] = Field(default_factory=list)
    what: list[str] = Field(default_factory=list)
    when: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)
    speech_act: Optional[SpeechActClassification] = Field(default=None)

# Permanent strategy: explicit migration wrapper
class FiveWOneHV2(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    who: list[str] = Field(default_factory=list)
    what: list[str] = Field(default_factory=list)
    when: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)
    speech_act: Optional[SpeechActClassification] = Field(default=None)

    @classmethod
    def from_legacy(cls, legacy: dict) -> "FiveWOneHV2":
        legacy.pop("speech_act", None)
        return cls(**legacy)
```
**Impact Assessment**: Production event replay and cache hydration will fail with `ValidationError` on every restart, causing pipeline stalls and requiring manual cache eviction.

### 1.3 Missing Protocol Definition Violates IoC Architecture

**Classification**: critical  
**Location**: `bb_paxdata/domain/services/speech_act_classifier.py`, `bb_paxdata/application/service_container.py`  
**Root Cause**: The report introduces `SpeechActClassifierService` as a concrete class without a domain protocol. Graph topology shows Community 653 (Application protocols) contains 69 nodes including `NERServiceProtocol`, `FramingServiceProtocol`, and `HedgingServiceProtocol`. The `ServiceContainer` (god node, 64 edges) lazy-loads services by protocol. Omitting a protocol prevents dependency injection, breaks the singleton pattern, and fragments the service graph. The new service will become an isolated node (the graph already has 515 isolated nodes).  
**Proposed Resolution**:
```python
# bb_paxdata/domain/ports/speech_act_port.py
from typing import Protocol, Optional
from bb_paxdata.domain.models.speech_act import SpeechActClassification

class SpeechActClassifierProtocol(Protocol):
    async def classify(
        self, 
        text: str, 
        srl_context: Optional[dict] = None
    ) -> SpeechActClassification: ...

# bb_paxdata/domain/services/speech_act_classifier.py
class SpeechActClassifierService:
    __slots__ = ("model_name", "_log", "triggers", "force_modifiers")
    # existing implementation ...

# bb_paxdata/application/service_container.py
class ServiceContainer:
    def __init__(self):
        self._speech_act_classifier: Optional[SpeechActClassifierProtocol] = None
    
    def get_speech_act_classifier(self) -> SpeechActClassifierProtocol:
        if self._speech_act_classifier is None:
            self._speech_act_classifier = SpeechActClassifierService(
                model_name=self.config.speech_act_model or "deberta-v3-small"
            )
        return self._speech_act_classifier
```
**Impact Assessment**: Without protocol registration, the service cannot be mocked in unit tests (Community 28/488), cannot be swapped for alternative implementations, and will be invisible to the Graphify knowledge graph, creating a maintenance dead zone.

## 2. Major Findings

### 2.1 Unsafe Enum Construction from LLM Output

**Classification**: major  
**Location**: `bb_paxdata/infrastructure/ai/frame_detection/five_w_one_h_extractor.py`  
**Root Cause**: The extraction logic performs `SpeechActType(parsed.primary_speech_act.upper())` without validation. If the LLM hallucinates an invalid value (e.g., `"COMMISSIVE_DIRECTIVE"`, `"ASSERT"`, `"directive"`), this raises `ValueError` and aborts the entire pipeline stage. The report provides no retry or fallback schema. Graph analysis shows Community 168 (AIAnomalyController/LLM integration) has 71 nodes with 0.03 cohesion, indicating high LLM interaction complexity and failure surface area.  
**Proposed Resolution**:
```python
from bb_paxdata.domain.models.speech_act import SpeechActType
from bb_paxdata.domain.services.recovery_engine import RecoveryEngine

def _safe_parse_speech_act(self, raw: str) -> tuple[SpeechActType, float]:
    cleaned = raw.strip().upper()
    try:
        return SpeechActType(cleaned), 1.0
    except ValueError:
        valid_members = {m.value for m in SpeechActType}
        if cleaned in valid_members:
            return SpeechActType(cleaned), 1.0
        # Recovery: default to ASSERTIVE with penalized confidence
        return SpeechActType.ASSERTIVE, 0.5

# In the extract() method:
primary, primary_conf = self._safe_parse_speech_act(parsed.primary_speech_act)
secondary = None
if parsed.secondary_speech_act:
    secondary, _ = self._safe_parse_speech_act(parsed.secondary_speech_act)
    
speech_act = SpeechActClassification(
    primary_type=primary,
    secondary_type=secondary,
    confidence=min(parsed.speech_act_confidence, primary_conf),
    force_modifier=parsed.force_modifier
)
```
**Impact Assessment**: Unhandled `ValueError` will crash the `AnalysisPipeline` (god node, 171 edges) for every transcript segment where the LLM deviates from the schema, causing complete pipeline failure and retry exhaustion.

### 2.2 Magic String Coupling in Temporal Analysis

**Classification**: major  
**Location**: `bb_paxdata/domain/services/temporal.py`, `bb_paxdata/domain/services/analysis_trigger.py`  
**Root Cause**: The report introduces string keys `"AI_Speech_Act"` and `"AI_Speech_Act_Modifier"` in `analysis_trigger.py` and `temporal.py`. These are not defined as constants, not type-checked, and not discoverable by static analysis. Graph topology shows Community 107 (transcript parsing utilities) and Community 58 (speaker normalization) already suffer from similar string-key fragility. This pattern propagates technical debt across the pipeline.  
**Proposed Resolution**:
```python
# bb_paxdata/domain/constants/speech_act_keys.py
from typing import Final

SPEECH_ACT_PRIMARY: Final[str] = "speech_act_primary"
SPEECH_ACT_MODIFIER: Final[str] = "speech_act_modifier"
SPEECH_ACT_CONFIDENCE: Final[str] = "speech_act_confidence"

# bb_paxdata/domain/services/analysis_trigger.py
from bb_paxdata.domain.constants.speech_act_keys import SPEECH_ACT_PRIMARY, SPEECH_ACT_MODIFIER

sentence_data.append({
    "speaker_id": sp_id,
    "global_sent_order": s.global_sent_order or 0,
    "text": s.text or "",
    "AI_Duygu_Skoru": s.vader_compound,
    "AI_Risk_Skoru": s.risk_score,
    "AI_Birincil_Konu": s.dominant_topic,
    "AI_Diplomatik_Ton": s.dominant_frame,
    SPEECH_ACT_PRIMARY: getattr(s, "speech_act", "ASSERTIVE"),
    SPEECH_ACT_MODIFIER: getattr(s, "speech_act_force_modifier", None),
})

# bb_paxdata/domain/services/temporal.py
sa_data = sentence.get(SPEECH_ACT_PRIMARY, "ASSERTIVE")
sa_mod = sentence.get(SPEECH_ACT_MODIFIER)
```
**Impact Assessment**: Key name drift between pipeline stages will cause silent data loss in drift detection (null series), leading to false negatives in illocutionary drift alerts and corrupted temporal analytics.

### 2.3 Unvalidated Confidence Arithmetic in Drift Detection

**Classification**: major  
**Location**: `bb_paxdata/domain/services/drift_algorithms.py`  
**Root Cause**: The `detect_illocutionary_drift` function computes `final_conf = min(1.0, base_conf * (1.0 + mod_adj))`. While capped at 1.0, the formula conflates historical prevalence (`base_conf`) with linguistic intensity (`mod_adj`). A single `COMMISSIVE` in a window of 3 yields `base_conf = 0.33`; with strong modifier `mod_adj = 0.2`, final confidence is `0.396`, which fails the default threshold of `0.5`. The algorithm therefore requires at least 2 `COMMISSIVE` acts in a window of 3 to trigger, but the documentation does not state this implicit constraint. The mathematical model is under-specified.  
**Proposed Resolution**:
```python
def detect_illocutionary_drift(
    speech_act_series: list[str],
    force_modifiers: list[Optional[str]],
    window_size: int = 3,
    confidence_threshold: float = 0.5,
    min_commissive_ratio: float = 0.5  # Explicit constraint
) -> list[dict[str, Any]]:
    if len(speech_act_series) < window_size:
        return []

    drift_points = []
    for i in range(window_size - 1, len(speech_act_series)):
        prev_window = speech_act_series[i - window_size + 1: i]
        current_act = speech_act_series[i]
        
        if current_act != "DIRECTIVE":
            continue
            
        comm_count = prev_window.count("COMMISSIVE")
        window_len = len(prev_window)
        base_conf = comm_count / window_len if window_len > 0 else 0.0
        
        # Explicit ratio gate
        if base_conf < min_commissive_ratio:
            continue
            
        # Modifier adjustment with documented bounds
        mod_adj = _compute_modifier_adjustment(force_modifiers[i])
        final_conf = min(1.0, base_conf * (1.0 + mod_adj))
        
        if final_conf >= confidence_threshold:
            drift_points.append({
                "start_index": i - window_size + 1,
                "end_index": i,
                "confidence": round(final_conf, 4),
                "magnitude": round(final_conf * 1.5, 2),
                "before_state": "COMMISSIVE",
                "after_state": f"DIRECTIVE:{force_modifiers[i] or 'none'}",
                "commissive_ratio": round(base_conf, 4)
            })
    return drift_points

def _compute_modifier_adjustment(modifier: Optional[str]) -> float:
    if not modifier:
        return 0.0
    mod_lower = modifier.lower()
    if mod_lower in ("strongly", "categorically", "absolutely", "şiddetle", "kesinlikle"):
        return 0.2
    if mod_lower in ("respectfully", "saygıyla"):
        return -0.1
    return 0.0
```
**Impact Assessment**: Undocumented implicit thresholds cause unpredictable detection behavior across different speakers and transcript lengths, undermining the claimed drift recall >= 0.85 metric.

### 2.4 Schema Mismatch Between Domain Model and ORM

**Classification**: major  
**Location**: `bb_paxdata/infrastructure/db/models.py`, `bb_paxdata/domain/models/ai_analysis.py`  
**Root Cause**: The report adds `speech_act` to `AIAnalysisResult` (Pydantic nested model) and `AISentenceAnalysis` (SQLAlchemy ORM) but uses inconsistent field names and types. `AIAnalysisResult.speech_act` is a nested `SpeechActClassification` Pydantic model. `AISentenceAnalysis.speech_act` is a flat `Mapped[str | None]`. No serialization bridge is defined. Graph topology shows Community 14 (Sentence ORM) and Community 6 (AnalysisContext) are tightly coupled; schema mismatches break the repository pattern.  
**Proposed Resolution**:
```python
# bb_paxdata/infrastructure/db/models.py
from sqlalchemy.dialects.sqlite import JSON

class AISentenceAnalysis(Base):
    # ... existing fields ...
    speech_act_json: Mapped[dict | None] = mapped_column(
        JSON, 
        nullable=True,
        doc="Serialized SpeechActClassification"
    )
    
    @property
    def speech_act_domain(self) -> Optional[SpeechActClassification]:
        if self.speech_act_json is None:
            return None
        return SpeechActClassification.model_validate(self.speech_act_json)

# bb_paxdata/domain/models/ai_analysis.py
class AIAnalysisResult(BaseModel):
    # ...
    speech_act: Optional[SpeechActClassification] = Field(default=None)
    
    def to_orm_dict(self) -> dict:
        base = self.model_dump(exclude={"speech_act"})
        base["speech_act_json"] = self.speech_act.model_dump() if self.speech_act else None
        return base
```
**Impact Assessment**: Flat string columns lose `force_modifier` and `confidence` data, causing the temporal analyzer to receive incomplete inputs and silently degrade drift detection accuracy.

### 2.5 SRL Context Parameter is a Dead Code Path

**Classification**: major  
**Location**: `bb_paxdata/domain/services/speech_act_classifier.py`  
**Root Cause**: The `classify` method accepts `srl_context: Optional[dict]` and logs it, but never uses it for classification logic. The transformer branch is a `pass` statement. Graph topology shows Community 756 (SRL Pipeline) and Community 775 (SRL Domain Objects) are high-cohesion communities with 40% node overlap; SRL data is available but ignored. This creates a false dependency and wastes pipeline I/O.  
**Proposed Resolution**:
```python
async def classify(self, text: str, srl_context: Optional[dict] = None) -> SpeechActClassification:
    if srl_context:
        # Deterministic override: if SRL shows ARG0=speaker + ARGM-MOD=must/should, boost DIRECTIVE
        args = srl_context.get("args", [])
        mods = [a for a in args if a.get("role") == "ARGM-MOD"]
        if any(m.get("text", "").lower() in {"must", "should", "gerekir", "zorunda"} for m in mods):
            heuristic = self.classify_heuristically(text)
            if heuristic.primary_type == SpeechActType.DIRECTIVE:
                heuristic = heuristic.model_copy(update={"confidence": min(1.0, heuristic.confidence + 0.15)})
            return heuristic
    # Fallback to heuristic until transformer is operational
    return self.classify_heuristically(text)
```
**Impact Assessment**: Dead code increases cyclomatic complexity and creates maintenance liability. When the transformer is eventually implemented, the unused parameter signature may conflict with the actual SRL integration pattern.

## 3. Minor Findings

### 3.1 Heuristic Confidence Values are Unvalidated

**Classification**: minor  
**Location**: `bb_paxdata/domain/services/speech_act_classifier.py`  
**Root Cause**: `classify_heuristically` assigns fixed confidence values (0.5 default, 0.75 for trigger match, +0.1 for modifier) without empirical calibration. The report claims F1 >= 0.80 but provides no validation dataset or calibration curve. Graph shows Community 161 (Krippendorff Alpha tests) and Community 581 (CalibrationService) exist but are not utilized.  
**Proposed Resolution**:
```python
from bb_paxdata.domain.services.calibration_service import CalibrationService

class SpeechActClassifierService:
    def __init__(self, model_name: str = "deberta-v3-small") -> None:
        self.model_name = model_name
        self._log = structlog.get_logger(__name__).bind(service="speech_act_classifier")
        self._calibration = CalibrationService(metric="speech_act_confidence")
        # ... existing trigger setup ...
        
    def classify_heuristically(self, text: str) -> SpeechActClassification:
        # ... existing matching logic ...
        raw_confidence = 0.75 if matched_types else 0.5
        calibrated = self._calibration.apply_platt_scaling(raw_confidence)
        return SpeechActClassification(
            primary_type=primary,
            secondary_type=secondary,
            confidence=round(calibrated, 3),
            force_modifier=modifier
        )
```
**Impact Assessment**: Unvalidated confidence scores propagate to drift detection thresholds, causing false positives/negatives in downstream temporal analysis.

### 3.2 Missing Graphify Update Trigger

**Classification**: minor  
**Location**: Project root / CI pipeline  
**Root Cause**: The report adds 4 new files and modifies 6 existing files. The graph report indicates the graph is built from commit `8d37ef99` and warns to run `graphify update .` after code changes. The TASK-A04 report does not include this step. New nodes (`SpeechActClassification`, `SpeechActClassifierService`) will be isolated (joining the existing 515 isolated nodes), breaking code-review-graph navigation.  
**Proposed Resolution**:
```yaml
# .github/workflows/ci.yml
- name: Update Graphify Knowledge Graph
  run: |
    graphify update .
    git diff --exit-code graph_report.md || echo "::warning::Graph report is stale"
```
**Impact Assessment**: Stale graph edges cause Antigravity and Continue.dev agents to miss cross-references, reducing code review accuracy and navigation efficiency.

### 3.3 Test Fixture Lacks Speaker Diversity

**Classification**: minor  
**Location**: `tests/quality/test_quality_pipeline_integration.py`  
**Root Cause**: The integration test for illocutionary drift uses a single speaker (`"speaker_01"`) with 3 sentences. The `TemporalAnalyzer` (Community 571) is designed for multi-speaker panels. Testing with one speaker does not validate speaker isolation logic or cross-speaker contamination.  
**Proposed Resolution**:
```python
def test_illocutionary_drift_multi_speaker_isolation(temporal_analyzer):
    speaker_data = {
        "speaker_01": {"name": "Ambassador A", "country": "US"},
        "speaker_02": {"name": "Ambassador B", "country": "TR"}
    }
    sentence_data = [
        # Speaker 01: COMMISSIVE -> DIRECTIVE (should trigger)
        {"speaker_id": "speaker_01", "global_sent_order": 1, "AI_Speech_Act": "COMMISSIVE", "AI_Speech_Act_Modifier": None},
        {"speaker_id": "speaker_01", "global_sent_order": 2, "AI_Speech_Act": "DIRECTIVE", "AI_Speech_Act_Modifier": "strongly"},
        # Speaker 02: ASSERTIVE only (should not leak into speaker_01's drift)
        {"speaker_id": "speaker_02", "global_sent_order": 3, "AI_Speech_Act": "ASSERTIVE", "AI_Speech_Act_Modifier": None},
    ]
    drifts = temporal_analyzer.analyze_panel_drift(
        panel_data={"panel_id": "test_drift_panel"}, 
        speaker_data=speaker_data, 
        sentence_data=sentence_data
    )
    illocutionary = [d for d in drifts if d.drift_type == "ILLOCUTIONARY"]
    assert len(illocutionary) == 1
    assert all(d.speaker_id == "speaker_01" for d in illocutionary)
```
**Impact Assessment**: Incomplete test coverage allows speaker-crossing bugs to reach production, corrupting per-actor diplomatic stance metrics.

### 3.4 Inconsistent Force Modifier Lexicon

**Classification**: minor  
**Location**: `bb_paxdata/domain/services/speech_act_classifier.py`  
**Root Cause**: The heuristic classifier uses regex patterns for force modifiers but omits common diplomatic intensifiers present in the Turkish lexicon (Community 176). Missing: `mutlak` (absolutely), `kati` (firmly), `samimi` (sincerely - moderate). The regex `r"\b(strongly|categorically|absolutely|firmly|şiddetle|kesinlikle|açıkça)\b"` uses `açıkça` (clearly) as strong, but it is semantically moderate.  
**Proposed Resolution**:
```python
self.force_modifiers = {
    "strong": r"\b(strongly|categorically|absolutely|firmly|mutlak|kati|şiddetle|kesinlikle)\b",
    "moderate": r"\b(consistently|clearly|willingly|açıkça|düzenli|samimi)\b",
    "mitigated": r"\b(respectfully|tentatively|humbly|saygıyla|ricayla|kısmen)\b"
}
```
**Impact Assessment**: Misclassified force modifiers skew drift confidence scores, causing false escalation or suppression of illocutionary drift alerts.

### 3.5 Hardcoded Coercion Logic in Domain Model

**Classification**: minor  
**Location**: `bb_paxdata/domain/models/speech_act.py`  
**Root Cause**: The `is_coercive` property uses a hardcoded tuple instead of referencing the service's configured modifier lexicon. If the lexicon changes, this property becomes stale.  
**Proposed Resolution**:
```python
from typing import ClassVar, FrozenSet

class SpeechActClassification(BaseModel):
    primary_type: SpeechActType
    secondary_type: Optional[SpeechActType] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    force_modifier: Optional[str] = None
    
    _COERCIVE_MODIFIERS: ClassVar[FrozenSet[str]] = frozenset({
        "strongly", "categorically", "absolutely", "şiddetle", "kesinlikle"
    })
    
    @property
    def is_coercive(self) -> bool:
        return (
            self.primary_type == SpeechActType.DIRECTIVE 
            and self.force_modifier is not None
            and self.force_modifier.lower() in self._COERCIVE_MODIFIERS
        )
```
**Impact Assessment**: Stale coercion logic will misclassify high-pressure diplomatic language, causing risk scoring errors in the bilateral sentiment matrix (Community 97).

## 4. Informational Observations

### 4.1 Pipeline Latency Claim Unsubstantiated

**Classification**: informational  
**Location**: Report Section 7.3  
**Root Cause**: The report asserts "pipeline overhead ≤ 8%" without benchmarking methodology, baseline measurement, or hardware specification. Graph topology shows Community 10 (CollectStage) and Community 28 (TestCollectStageLazyAIEvaluation) contain latency-sensitive instrumentation, but no speech-act-specific metrics are defined.  
**Proposed Resolution**:
```python
# bb_paxdata/infrastructure/monitoring/metrics_collector.py
from prometheus_client import Histogram

SPEECH_ACT_LATENCY = Histogram(
    "speech_act_classification_seconds",
    "Latency of speech act classification stage",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)
```
**Impact Assessment**: Unsubstantiated performance claims prevent capacity planning and may violate SLOs under production load.

### 4.2 AnalysisAssembler Integration Point Undefined

**Classification**: informational  
**Location**: `bb_paxdata/application/pipeline/analysis_assembler.py` (implied)  
**Root Cause**: The report modifies `AIAnalysisResult` and `FiveWOneH`, but does not specify how `AnalysisAssembler` (inferred edge from `Analysis` god node) merges speech_act data into the final `Analysis` domain model. Graph shows `Analysis` has 157 inferred edges, many connecting to assembler components. The assembly logic is not documented.  
**Proposed Resolution**:
```python
# bb_paxdata/application/pipeline/analysis_assembler.py
def _merge_speech_act_into_analysis(
    self, 
    analysis: Analysis, 
    five_w_one_h: FiveWOneH
) -> Analysis:
    if five_w_one_h.speech_act:
        analysis.speech_act = five_w_one_h.speech_act
        # Propagate to sentence-level if sentence-level classification absent
        for sentence in analysis.sentences:
            if sentence.speech_act is None:
                sentence.speech_act = five_w_one_h.speech_act
    return analysis
```
**Impact Assessment**: Missing assembly logic causes speech_act data to remain orphaned in the 5W1H extraction stage, never reaching the database or downstream drift analyzer.

### 4.3 Community Isolation Risk for New Components

**Classification**: informational  
**Location**: Graph topology (Global)  
**Root Cause**: Graph report identifies 515 isolated nodes and 356 thin communities. The new files (`speech_act.py`, `speech_act_classifier.py`, `drift_algorithms.py` additions) are not explicitly connected to existing high-centrality communities (Community 60: AnalysisPipeline, Community 653: Protocols, Community 1: Fischer DNA). Without deliberate edge creation (imports, protocol registration, test coverage), these components will join the isolated set.  
**Proposed Resolution**:
- Import `SpeechActClassification` in `bb_paxdata/domain/models/__init__.py`
- Register protocol in `bb_paxdata/domain/ports/__init__.py`
- Add service factory in `bb_paxdata/application/service_container.py`
- Reference in `AnalysisPipeline` configuration (Community 60)
- Add unit tests in `tests/unit/domain/services/test_speech_act_classifier.py` (link to Community 28)
**Impact Assessment**: Isolated nodes are invisible to graph-based code review tools, reducing maintainability and increasing duplication risk.

### 4.4 Missing Alembic Migration for ORM Changes

**Classification**: informational  
**Location**: `bb_paxdata/infrastructure/db/models.py`  
**Root Cause**: The report adds `speech_act`, `speech_act_confidence`, and `speech_act_force_modifier` columns to `AISentenceAnalysis` but does not provide an Alembic migration script. Graph shows Community 87 (Alembic migration helpers) has 9 nodes with 0.20 cohesion, indicating migration infrastructure exists but is not utilized here.  
**Proposed Resolution**:
```python
# alembic/versions/xxxx_add_speech_act_to_aisentenceanalysis.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    with op.batch_alter_table("ai_sentence_analysis") as batch_op:
        batch_op.add_column(sa.Column("speech_act", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("speech_act_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("speech_act_force_modifier", sa.String(100), nullable=True))

def downgrade():
    with op.batch_alter_table("ai_sentence_analysis") as batch_op:
        batch_op.drop_column("speech_act_force_modifier")
        batch_op.drop_column("speech_act_confidence")
        batch_op.drop_column("speech_act")
```
**Impact Assessment**: Missing migrations cause schema drift between production and development environments, breaking `poetry run bbpaxdata migrate run` workflows (Community 92).

### 4.5 Segment vs. Sentence Granularity Ambiguity

**Classification**: informational  
**Location**: `bb_paxdata/domain/models/speech_act.py`, `bb_paxdata/infrastructure/db/models.py`  
**Root Cause**: The report states that `SegmentAnalyzedEvent` already contains `speech_act: Mapped[str | None]` at the segment level, but the new `SpeechActClassification` is attached to `FiveWOneH` (segment-level) and `AISentenceAnalysis` (sentence-level). The graph shows `Segment` (122 edges) and `Sentence` (108 edges) are both god nodes with high betweenness. Attaching speech act to both levels without a clear aggregation rule creates ambiguity.  
**Proposed Resolution**:
```python
# bb_paxdata/domain/services/segment_enrichment_gateway.py (Community 26)
def aggregate_speech_act(self, sentences: list[Sentence]) -> Optional[SpeechActClassification]:
    """Aggregate sentence-level speech acts to segment level via majority vote."""
    if not sentences:
        return None
    counts = {}
    for s in sentences:
        if s.speech_act:
            counts[s.speech_act] = counts.get(s.speech_act, 0) + 1
    if not counts:
        return None
    dominant = max(counts, key=counts.get)
    return SpeechActClassification(
        primary_type=dominant,
        confidence=counts[dominant] / len(sentences)
    )
```
**Impact Assessment**: Granularity ambiguity causes segment-level and sentence-level analytics to diverge, producing inconsistent diplomatic stance reports in the HITL dashboard (Community 508).