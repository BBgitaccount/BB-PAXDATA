# TASK-A03 — Appraisal Theory Vector (Martin & White 2005)
## Upgraded AI-Agent Implementation Report
**Report Date:** 2026-06-05 | **Graph Commit:** `a67be8f4` | **Supersedes:** TASK_A03_DEVELOPMENT_REPORT.md

---

## 0. TASK METADATA

| Field          | Value                                              |
| -------------- | -------------------------------------------------- |
| Task Code      | TASK-A03                                           |
| Project        | BB-PAXDATA — Diplomatik Söylem Analiz Sistemi      |
| Root           | `c:\Users\THINKPAD\Desktop\BB-PAXDATA`             |
| Difficulty     | M                                                  |
| Priority       | P2 — Phase 2 (after TASK-A01)                      |
| Theory Source  | Martin & White (2005) *The Language of Evaluation* |
| Dependency     | TASK-A01 (SRL Enrichment Layer) — COMPLETE         |
| Runtime        | Python 3.11+, Pydantic v2, asyncio                 |
| Test Framework | pytest + pytest-asyncio                            |

---

## 1. CODEBASE STATE — GRAPH-DERIVED FACTS

Graph: 7419 nodes · 13468 edges · 774 communities. 25% of edges are INFERRED (avg confidence 0.59). All facts below are EXTRACTED unless otherwise annotated.

### 1.1 God Nodes Relevant to TASK-A03

| Node                      | Edges | Community | Relevance                                                                                          |
| ------------------------- | ----- | --------- | -------------------------------------------------------------------------------------------------- |
| `Analysis`                | 165   | 60, 28    | Root domain model; receives `appraisal_vector` field                                               |
| `Segment`                 | 113   | 1, 60     | Primary processing unit; `power_index` field modified                                              |
| `Sentence`                | 97    | multiple  | Granular analysis target                                                                           |
| `_process_single_file()`  | 87    | 139       | Betweenness centrality 0.073 — highest cross-community bridge; integration MUST route through this |
| `ServiceContainer`        | 64    | 13        | IoC container; `AppraisalService` must be registered here                                          |
| `BilateralSentimentTable` | 58    | 1, 36     | `asymmetry_score` modification target                                                              |
| `AnalysisTriggerService`  | 54    | 60, 142   | Actual integration target (not `analysis_trigger.py` script)                                       |

### 1.2 Pre-Existing Appraisal Representations (CONFLICT ZONE)

The graph reveals two existing appraisal-related constructs that the original report does not fully resolve:

**Community 0** contains `AppraisalAttitude` alongside `Enum`, `AnomalySeverity`, `BackendType`, `AIProvider`. This is an existing domain Enum (values: POSITIVE / NEGATIVE / NEUTRAL) used by:
- `FramingService` — Community 118 test nodes include `"Test positive appraisal attitude."` and `"Test negative appraisal attitude."`
- `AIAnalysisResult.ai_appraisal_attitude` field (string) — referenced in `CrossAnomalyService._extract_ai_values()` at L454: `"ai_appraisal": getattr(analysis, "ai_appraisal_attitude", "neutral")`
- `CrossAnomalyService._detect_negative_appraisal_persuasive_tone()` — Community 56

**Community 179** contains `"Determine the appraisal attitude."` as a method on `FramingService`, confirming that appraisal attitude classification is already live in the pipeline at segment granularity.

TASK-A03 introduces a third representation (`AppraisalVector`) without a bridge or migration plan for the two existing ones. This is a critical architectural gap.

### 1.3 Async Context Confirmed

Communities 62 (`AsyncEventBus`), 110 (`AbstractUnitOfWork` with async session), 143 (`asyncio` parallel service execution), and 142 (`AnalysisTriggerService`) confirm the pipeline is fully async. `CollectStage` (Community 10) executes services concurrently. Any synchronous call in this context will block the event loop.

### 1.4 `CollectStage` is the Correct Integration Layer

Community 10 contains `_build_collect_stage()`, `test_bypass_result_has_no_frame_or_topic()`, `test_bypass_triggers_telemetry()`. The pattern for all deterministic services (HedgingService, SentimentService, RiskService) is injection via `CollectStage`, not direct mutation in `AnalysisTriggerService`. The original report's §4 integration target (`analysis_trigger.py`) is architecturally inconsistent with this pattern.

---

## 2. FINDINGS — CRITICAL

---

### FINDING C-01

**Classification:** critical
**Location:** `AppraisalService.__new__` — `src/bb_paxdata/domain/services/appraisal_service.py`

**Root Cause:** The singleton implementation uses double-checked locking without a mutex. Under Python's GIL, class-level attribute writes (`cls._instance = super().__new__(cls)`) are not atomic across OS thread boundaries when the ASGI server spawns multiple threads (uvicorn with `--workers > 1` or thread pool for blocking I/O). Two concurrent first-calls will both pass the `cls._instance is None` check and produce two distinct instances, violating the singleton contract and duplicating the LRU cache.

```python
# CURRENT (broken under multi-thread concurrency)
def __new__(cls) -> "AppraisalService":
    if cls._instance is None:                     # <-- race condition
        cls._instance = super().__new__(cls)
        cls._instance._initialized = False
    return cls._instance
```

**Proposed Resolution:** Use a module-level `threading.Lock` with double-checked locking. This pattern is safe under the GIL and correct for multi-threaded ASGI:

```python
import threading

_singleton_lock: threading.Lock = threading.Lock()

class AppraisalService:
    _instance: Optional["AppraisalService"] = None

    def __new__(cls) -> "AppraisalService":
        if cls._instance is None:
            with _singleton_lock:
                if cls._instance is None:          # second check inside lock
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
```

The same pattern applies to `HedgingService` if it follows the same singleton implementation — verify and apply uniformly.

**Impact Assessment:** Without this fix, concurrent requests at startup will create multiple `AppraisalService` instances with separate `_cache` OrderedDicts. The LRU cache provides no shared benefit, memory usage doubles per concurrent init, and the `_initialized` guard becomes unreliable. Under load testing, this manifests as inconsistent cache hit rates.

---

### FINDING C-02

**Classification:** critical
**Location:** §4 integration snippet — `analysis_trigger.py` / `AnalysisTriggerService`

**Root Cause:** Type mismatch in `appraisal_judgment_sanction_count` assignment. The field in `AIAnalysisResult` is declared `int` (`ge=0`), but the integration code assigns a boolean expression:

```python
# CURRENT (wrong — assigns bool to int field)
analysis_result.appraisal_judgment_sanction_count = (
    appraisal_vector.judgment_is_sanction and appraisal_vector.judgment_score < -0.2
)
# Evaluates to True (≡1) or False (≡0) — counts only ONE vector for document-level field
```

Two independent defects:
1. Python casts `True → 1` silently; Pydantic v2 with `strict=True` raises `ValidationError`. The `AIAnalysisResult` model config must be checked for `strict=True`. If present, this raises at runtime.
2. The assignment semantics are wrong for a document-level counter: this only reflects a single `AppraisalVector` result, not the aggregate across all segments.

**Proposed Resolution:** The document-level count must be computed from `AppraisalDocumentResult.judgment_sanction_count` after batch analysis, not from a single segment's vector:

```python
# In the pipeline's ASSEMBLE stage (not analysis_trigger.py):
doc_result: AppraisalDocumentResult = appraisal_svc.analyze_document(
    segments=[(seg.id, seg.text) for seg in session_segments],
    srl_frames_by_segment=srl_frames_by_segment,
)

# Then populate AIAnalysisResult at session/document level:
analysis_result = analysis_result.model_copy(update={
    "appraisal_vector": _aggregate_appraisal_vector(doc_result),  # see below
    "appraisal_judgment_sanction_count": doc_result.judgment_sanction_count,  # int property
    "dominant_appraisal_axis": doc_result.vectors[0][1].dominant_axis if doc_result.vectors else None,
})

def _aggregate_appraisal_vector(doc_result: AppraisalDocumentResult) -> Optional[AppraisalVector]:
    """Return the AppraisalVector with highest weighted_intensity as document representative."""
    if not doc_result.vectors:
        return None
    return max(
        (v for _, v in doc_result.vectors if v.has_any_detection),
        key=lambda v: v.weighted_intensity,
        default=None,
    )
```

**Impact Assessment:** Without this fix: (a) `strict=True` contexts raise `ValidationError` at runtime, crashing the pipeline for every analyzed document; (b) `AIAnalysisResult.is_high_judgment_sanction` always returns `False` (count never exceeds 1), rendering the `>= 2` threshold useless and making downstream propaganda detection (TASK-X04) deaf to multi-sanction documents.

---

### FINDING C-03

**Classification:** critical
**Location:** §4 integration snippet — `Segment.power_index` reassignment

**Root Cause:** The integration code attempts direct field mutation on `Segment`:

```python
# CURRENT (raises PydanticImmutableInstanceError if Segment is frozen)
if segment.power_index:
    segment.power_index = segment.power_index.model_copy(
        update={"appraisal_vector": appraisal_vector}
    )
```

The graph places `Segment` in Community 1 (Cohesion 0.16, high structural integrity). Community 36 explicitly tests `"Model frozen=True olduğu için doğrudan atama exception fırlatmalı."` for `BilateralSentiment`. Given that domain models throughout this codebase follow `frozen=True` by convention (verified: `PowerIndex`, `BilateralSentiment`, `AppraisalVector` all use `ConfigDict(frozen=True)`), `Segment` is almost certainly also frozen. Direct field assignment raises `ValidationError` / `PydanticImmutableInstanceError`.

**Proposed Resolution:** The `Segment` model's immutability contract requires creating a new segment instance. However, in a pipeline context, mutable intermediate state objects are the correct pattern. The `AppraisalVector` should not be written onto `Segment.power_index` directly. Instead, maintain a side-channel dict during the CollectStage execution, and write to the ORM model layer (not the domain model) during the FinalizeStage (Community 491):

```python
# In CollectStage._collect_appraisal() — returns a side-channel result
async def _collect_appraisal(
    self,
    segment: Segment,
    srl_frame: Optional[SRLFrame],
    hedging_markers: Optional[list[str]],
) -> AppraisalVector:
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(
        None,  # default ThreadPoolExecutor
        functools.partial(
            self._appraisal_svc.analyze,
            text=segment.text,
            segment_id=str(segment.id),
            srl_frame=srl_frame,
            hedging_detected_markers=hedging_markers,
        )
    )
    return vector

# appraisal_vector is stored in PipelineResult.extra_data, not on frozen Segment:
pipeline_result.extra_data["appraisal_vector"] = vector
```

The `PowerIndex.appraisal_weighted_power` property only applies when reading from a fully-assembled analysis object, not during live mutation of domain models.

**Impact Assessment:** Without this fix, the pipeline raises `PydanticImmutableInstanceError` on every analysis that has a `power_index` present, crashing document processing. Since `_process_single_file()` is the highest-centrality node (87 edges, betweenness 0.073), a crash here propagates across 24 dependent communities.

---

## 3. FINDINGS — MAJOR

---

### FINDING M-01

**Classification:** major
**Location:** `AppraisalService.analyze()` — `src/bb_paxdata/domain/services/appraisal_service.py`; `CollectStage` — `src/bb_paxdata/application/pipeline/`

**Root Cause:** `AppraisalService.analyze()` is a synchronous method. The pipeline's `CollectStage` executes services via `asyncio.gather()` (confirmed by Community 143 description: "Tüm servisleri paralel çalıştırır"). Calling a synchronous method directly from a coroutine blocks the event loop for the duration of the regex matching loop across all lexicon entries. For a 200-token segment with all three lexicons (AFFECT: ~30 entries, JUDGMENT: ~40 entries, APPRECIATION: ~25 entries), each with `re.search()`, this is ~95 compiled regex evaluations per segment.

**Proposed Resolution:** Wrap the synchronous call in `asyncio.get_event_loop().run_in_executor()` within `CollectStage`, or declare a thin async wrapper on `AppraisalService`. The service itself remains synchronous (CPU-bound, no I/O) but is dispatched to the default `ThreadPoolExecutor`:

```python
# In CollectStage or wherever AppraisalService is called from an async context:
import asyncio, functools

async def _analyze_appraisal_async(
    svc: AppraisalService,
    text: str,
    segment_id: Optional[str],
    srl_frame: Optional[SRLFrame],
    hedging_markers: Optional[list[str]],
) -> AppraisalVector:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(
            svc.analyze,
            text=text,
            segment_id=segment_id,
            srl_frame=srl_frame,
            hedging_detected_markers=hedging_markers,
        )
    )
```

Pre-compile all regex patterns at module load time to reduce per-call overhead:

```python
# At module level, after lexicon definitions:
_AFFECT_PATTERNS: list[tuple[re.Pattern, tuple[float, AffectType]]] = [
    (re.compile(r'\b' + re.escape(phrase) + r'\b'), val)
    for phrase, val in _AFFECT_SORTED
]
_JUDGMENT_PATTERNS: list[tuple[re.Pattern, tuple[float, JudgmentType, bool]]] = [
    (re.compile(r'\b' + re.escape(phrase) + r'\b'), val)
    for phrase, val in _JUDGMENT_SORTED
]
_APPRECIATION_PATTERNS: list[tuple[re.Pattern, tuple[float, AppreciationType]]] = [
    (re.compile(r'\b' + re.escape(phrase) + r'\b'), val)
    for phrase, val in _APPRECIATION_SORTED
]
```

Replace `re.search(r'\b' + re.escape(phrase) + r'\b', text_lower)` with `pattern.search(text_lower)` in each `_detect_*` method.

**Impact Assessment:** Without pre-compilation, each `analyze()` call re-compiles ~95 regex patterns. Python's `re` module caches 512 patterns by default, but cache eviction occurs under concurrent usage. At 100 segments/document, this is 9500 regex compilations. With pre-compilation, this drops to zero. The async wrapper prevents event loop starvation under load.

---

### FINDING M-02

**Classification:** major
**Location:** Community 0 (`AppraisalAttitude` Enum) + Community 179 (`FramingService.determine_appraisal_attitude()`) + `AIAnalysisResult.ai_appraisal_attitude` + `CrossAnomalyService._extract_ai_values()` L454

**Root Cause:** Three independent appraisal representations exist post-TASK-A03:
1. `AppraisalAttitude` Enum — string-valued (POSITIVE/NEGATIVE/NEUTRAL), populated by `FramingService`
2. `AIAnalysisResult.ai_appraisal_attitude` — LLM-generated string field
3. `AppraisalVector` — structured 3-axis domain model (TASK-A03)

`CrossAnomalyService._extract_ai_values()` reads `ai_appraisal_attitude` (type 2). `_detect_negative_appraisal_persuasive_tone()` (Community 56) uses this value to flag persuasive manipulation patterns. After TASK-A03, this rule has access to a richer signal (`AppraisalVector.judgment_is_sanction`, `AppraisalVector.judgment_score`) but will continue to use the impoverished string field unless explicitly updated.

**Proposed Resolution:** Two-phase approach:

**Phase A (TASK-A03 scope):** Add an adapter property on `AIAnalysisResult` that bridges the old field to the new:

```python
# In ai_analysis.py — add computed bridge property
@property
def appraisal_attitude_from_vector(self) -> str:
    """
    Bridge: derive legacy AppraisalAttitude string from AppraisalVector.
    Supersedes ai_appraisal_attitude for downstream rules.
    Returns: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
    """
    if self.appraisal_vector is None or not self.appraisal_vector.has_any_detection:
        return self.ai_appraisal_attitude or "neutral"
    v = self.appraisal_vector
    dominant_score = max(
        v.affect_score * v.affect_confidence,
        v.judgment_score * v.judgment_confidence,
        v.appreciation_score * v.appreciation_confidence,
        key=abs
    )
    if dominant_score > 0.15:
        return "POSITIVE"
    if dominant_score < -0.15:
        return "NEGATIVE"
    return "NEUTRAL"
```

**Phase B (future task):** Refactor `CrossAnomalyService._extract_ai_values()` to consume `AppraisalVector` directly, enabling `_detect_negative_appraisal_persuasive_tone()` to distinguish sanction-type judgment from affect-type negativity.

**Impact Assessment:** Without this bridge, `CrossAnomalyService` continues using the weaker `ai_appraisal_attitude` string, missing sanction-type negative judgments that the new service captures with high precision (e.g., `"violates international law"` → `judgment_score=-0.9, judgment_is_sanction=True`). The velvet-glove confrontation rule (Community 30) and propaganda detection (TASK-X04 dependency) both degrade.

---

### FINDING M-03

**Classification:** major
**Location:** `AppraisalService` — `_detect_affect`, `_detect_judgment`, `_detect_appreciation`; lexicon definitions

**Root Cause:** The `_detect_*` methods accumulate ALL matching phrases into `triggers` even when a longer match supersedes a shorter one. The lexicons are sorted longest-first (`_sorted_lexicon`), and the `best_score` is updated only when `abs(score) > abs(best_score)`. However, triggers continue to accumulate regardless:

```python
# Current behavior — both phrases land in triggers
for phrase, (score, affect_type) in _AFFECT_SORTED:
    if re.search(pattern, text_lower):
        triggers.append(phrase)                      # appended unconditionally
        if abs(score) > abs(best_score):
            best_score = score
            best_type = affect_type

# For "deeply concerned":
# Match 1: "deeply concerned" (score=-0.7) → best_score=-0.7, triggers=["deeply concerned"]
# Match 2: "concerned" (score=-0.4) → abs(-0.4) < abs(-0.7), no update, but triggers=["deeply concerned", "concerned"]
```

Secondary issue: `"effective"` appears in both `JUDGMENT_LEXICON` (score=0.5, CAPACITY, esteem=False) and `APPRECIATION_LEXICON` (score=0.5, VALUE). `"unacceptable"` appears in both `JUDGMENT_LEXICON` (score=-0.7, PROPRIETY, sanction=True) and `APPRECIATION_LEXICON` (score=-0.7, VALUE). For text containing these words, both axes fire simultaneously, making `dominant_axis` dependent on `confidence` values that are derived from trigger count — which is inflated by the subphrase accumulation bug above.

**Proposed Resolution:**

Introduce a consumed-spans tracker to prevent subphrase accumulation after a longer match:

```python
def _detect_affect(self, text_lower: str) -> tuple[float, Optional[AffectType], list[str]]:
    best_score = 0.0
    best_type: Optional[AffectType] = None
    triggers: list[str] = []
    consumed_positions: set[int] = set()  # character positions already claimed

    for pattern, (score, affect_type) in _AFFECT_PATTERNS:
        m = pattern.search(text_lower)
        if m:
            start, end = m.start(), m.end()
            # Skip if this span is entirely within an already-consumed longer match
            if any(start >= cs and end <= ce for cs, ce in _iter_consumed(consumed_positions)):
                continue
            triggers.append(pattern.pattern.replace(r'\b', '').replace('\\', ''))
            consumed_positions.add((start, end))  # store as tuple pairs
            if abs(score) > abs(best_score):
                best_score = score
                best_type = affect_type

    return best_score, best_type, triggers
```

Resolve lexicon ambiguities deterministically:

```python
# Remove from APPRECIATION_LEXICON (already in JUDGMENT with is_sanction context):
# "unacceptable" — keep in JUDGMENT_LEXICON only (is_sanction=True gives higher signal value)
# "effective" — keep in APPRECIATION_LEXICON only (JUDGMENT CAPACITY detection via "competent", "capable" is sufficient)
```

**Impact Assessment:** Without this fix, `confidence` values are over-inflated by subphrase double-counting, which causes `dominant_axis` to return incorrect results and `BilateralSentiment.asymmetry_score` to apply an incorrect appraisal weight. The `"unacceptable"` ambiguity causes multi-axis contamination for a high-frequency diplomatic word, producing different `dominant_axis` values for identical input depending on execution order of pattern matching.

---

### FINDING M-04

**Classification:** major
**Location:** `ServiceContainer` — `src/bb_paxdata/infrastructure/container/service_container.py` (Community 13)

**Root Cause:** `ServiceContainer` is the IoC container for all service singletons. The original report provides no instruction to register `AppraisalService` in it. Community 13 explicitly describes `ServiceContainer` as managing "uygulama genelindeki servis bağımlılıklarını" (application-wide service dependencies). Every other domain service (`HedgingService`, `SentimentService`, `RiskService`, `FramingService`, `TopicService`) is registered here. An unregistered `AppraisalService` forces callers to use `get_appraisal_service()` directly, bypassing dependency injection, preventing mock substitution in tests, and violating the IoC contract.

**Proposed Resolution:** Register `AppraisalService` in `ServiceContainer` following the `NERServiceProtocol`/`NERStub` pattern. Add `AppraisalServiceProtocol` to `src/bb_paxdata/application/protocols.py` (Community 653):

```python
# In src/bb_paxdata/application/protocols.py
from typing import Protocol, runtime_checkable, Optional
from bb_paxdata.domain.models.appraisal_vector import AppraisalVector
from bb_paxdata.domain.models.srl import SRLFrame

@runtime_checkable
class AppraisalServiceProtocol(Protocol):
    def analyze(
        self,
        text: str,
        segment_id: Optional[str] = None,
        srl_frame: Optional[SRLFrame] = None,
        hedging_detected_markers: Optional[list[str]] = None,
    ) -> AppraisalVector: ...

# In ServiceContainer.__init__ or _build():
from bb_paxdata.domain.services.appraisal_service import get_appraisal_service
from bb_paxdata.application.protocols import AppraisalServiceProtocol

self._appraisal_service: AppraisalServiceProtocol = get_appraisal_service()

@property
def appraisal_service(self) -> AppraisalServiceProtocol:
    return self._appraisal_service
```

**Impact Assessment:** Without ServiceContainer registration, `AppraisalService` cannot be mocked in `CollectStage` tests, the `test_service_container_initialization` test (Community 489) will not cover the new service, and the `no_ai_mode` pipeline variant (Community 533) has no mechanism to substitute a no-op `AppraisalService`.

---

### FINDING M-05

**Classification:** major
**Location:** `src/bb_paxdata/domain/models/power_index.py` — `model_rebuild()` requirement

**Root Cause:** The original report adds `appraisal_vector: Optional["AppraisalVector"]` to `PowerIndex` using a forward reference (string annotation). Pydantic v2 requires explicit `model_rebuild()` after all forward references are resolvable — i.e., after the `AppraisalVector` class is defined. Without this call, validators and JSON schema generation for `PowerIndex` will silently fail to resolve the forward reference, producing `None` for the field regardless of input.

```python
# CURRENT (forward ref never resolved at runtime)
class PowerIndex(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    # ... existing fields ...
    appraisal_vector: Optional["AppraisalVector"] = Field(default=None, ...)
```

**Proposed Resolution:** Add `model_rebuild()` call in the same module, after the import is resolvable at module load time. Since `AppraisalVector` is imported under `TYPE_CHECKING`, the rebuild must be deferred:

```python
# At the bottom of power_index.py, OUTSIDE the class body:
from __future__ import annotations
# ... class definition ...

# After all imports are available at runtime:
def _rebuild_power_index() -> None:
    """Called once after appraisal_vector module is loaded."""
    from bb_paxdata.domain.models.appraisal_vector import AppraisalVector  # noqa: F401
    PowerIndex.model_rebuild()

# Trigger via module __init__.py of domain/models/:
# from bb_paxdata.domain.models.power_index import _rebuild_power_index
# _rebuild_power_index()
```

Alternatively, use a non-forward reference with a lazy import guard:

```python
# If circular imports are avoided via dependency direction:
# appraisal_vector.py has NO imports from power_index.py (confirmed — it doesn't)
# Therefore direct import is safe:
from bb_paxdata.domain.models.appraisal_vector import AppraisalVector

class PowerIndex(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    appraisal_vector: Optional[AppraisalVector] = Field(default=None, ...)
    # No forward ref, no model_rebuild() needed
```

This is possible because the import dependency direction is `power_index → appraisal_vector` (acyclic). The `TYPE_CHECKING` guard in the original report is overly conservative.

**Impact Assessment:** Unresolved forward references in Pydantic v2 do not raise errors at class definition time; they fail silently during validation. `PowerIndex` instances constructed with a valid `AppraisalVector` will serialize the field as `None` in JSON/JSONB storage, losing all appraisal data permanently with no error signal.

---

### FINDING M-06

**Classification:** major
**Location:** `CollectStage` integration — §4 of original report

**Root Cause:** The integration snippet in §4 targets `analysis_trigger.py` as a script-level integration point. However, the graph shows `AnalysisTriggerService` (Community 142, 54 edges) as a class-based service that is injected into `CollectStage`. The correct integration follows the pattern of existing service calls in `CollectStage._run_all_services()` (Community 143). Writing to `analysis_trigger.py` directly bypasses the pipeline's phase separation (Phase 1 deterministic vs Phase 2 AI), the bypass tracking in `LimitedAIAnalyst` (Community 38), and the telemetry hooks in `test_bypass_triggers_telemetry()` (Community 10).

**Proposed Resolution:** Add `AppraisalService` to `CollectStage` as a constructor-injected dependency, parallel to `HedgingService`:

```python
# In CollectStage.__init__:
def __init__(
    self,
    # ... existing params ...
    hedging_service: HedgingServiceProtocol,
    appraisal_service: AppraisalServiceProtocol,  # NEW
) -> None:
    self._hedging_service = hedging_service
    self._appraisal_service = appraisal_service
    # ...

# In CollectStage._run_deterministic_services() (Phase 1):
async def _run_deterministic_services(self, context: AnalysisContext) -> None:
    # Run in parallel with HedgingService, SentimentService:
    hedging_task = asyncio.create_task(self._run_hedging(context))
    appraisal_task = asyncio.create_task(self._run_appraisal(context))  # NEW
    await asyncio.gather(hedging_task, appraisal_task, ...)

async def _run_appraisal(self, context: AnalysisContext) -> None:
    hedging_result = context.get_cached("hedging")  # from memoize pattern (Community 119)
    hedging_markers = hedging_result.detected_categories if hedging_result else []
    srl_frame = context.get_cached("srl")

    loop = asyncio.get_running_loop()
    vector = await loop.run_in_executor(
        None,
        functools.partial(
            self._appraisal_service.analyze,
            text=context.sentence.text,
            segment_id=str(context.sentence.id),
            srl_frame=srl_frame,
            hedging_detected_markers=[m.value for m in hedging_markers],
        )
    )
    context.store("appraisal", vector)
```

**Impact Assessment:** Without proper CollectStage integration: (a) Bypass tracking does not count appraisal analysis calls, skewing `LimitedAIAnalyst` efficiency metrics; (b) `test_bypass_triggers_telemetry()` does not cover appraisal; (c) the `no_ai_mode` pipeline variant does not conditionally skip appraisal analysis.

---

## 4. FINDINGS — MINOR

---

### FINDING m-01

**Classification:** minor
**Location:** `AppraisalService._cache_key()` — `src/bb_paxdata/domain/services/appraisal_service.py`

**Root Cause:** The cache key uses `sha256(text)[:16]` — 64 bits of hash space. For a corpus of 100K+ segments (535 files, ~472K words → estimated 50K–100K unique segments), the birthday paradox collision probability at 100K keys over 2^64 space is approximately 2.7×10^-10 — negligible. However, the implementation is inconsistent with `CacheBackend._make_key()` in Community 79, which uses `sha256(":".join(parts))[:16]` but appears to be the infrastructure cache layer, not the domain service cache. The LRU cache in `AppraisalService` is an in-memory OrderedDict, not the Redis/Disk backends.

More significantly, the `_cache_max = 1000` hard-coded limit with no configuration override means the cache size cannot be tuned for production workloads. For 100K segments, 99% will be cache misses on first pass.

**Proposed Resolution:** Expose `_cache_max` through `AppraisalPipelineConfig`:

```python
# In AppraisalPipelineConfig:
cache_max_entries: int = Field(
    default=5000,
    description="Maximum LRU cache entries for AppraisalService"
)

# In AppraisalService.__init__:
self._cache_max = self.config.cache_max_entries
```

---

### FINDING m-02

**Classification:** minor
**Location:** `AppraisalVector.to_dict_for_db()` — `src/bb_paxdata/domain/models/appraisal_vector.py`

**Root Cause:** The method omits the following fields that are defined on the model: `affect_confidence`, `judgment_confidence`, `appreciation_confidence`, `appreciation_type`, `graduation_focus`, `engagement_confidence`, `source_segment_id`, `model_version`. These fields provide diagnostic and provenance data essential for HITL review (Community 72, 151) and calibration audits (Community 186, `FormulaAuditor`).

**Proposed Resolution:** Use `model_dump()` with explicit exclusions rather than a manual dict:

```python
def to_dict_for_db(self) -> dict:
    """Serialize for JSONB storage. Excludes non-serializable computed properties."""
    base = self.model_dump(
        exclude={"trigger_words"}  # keep this separate for array column if needed
    )
    # Append computed properties that are diagnostically useful:
    base["dominant_axis"] = self.dominant_axis
    base["weighted_intensity"] = self.weighted_intensity
    base["is_negative_judgment_sanction"] = self.is_negative_judgment_sanction
    return base
```

---

### FINDING m-03

**Classification:** minor
**Location:** `AppraisalDocumentResult` — `src/bb_paxdata/domain/models/appraisal_vector.py`

**Root Cause:** `AppraisalDocumentResult` uses `frozen=False` while `AppraisalVector` uses `frozen=True`. Within the same module, this inconsistency allows callers to mutate `AppraisalDocumentResult.vectors` after construction. The `judgment_sanction_count` and `dominant_engagement` properties iterate `self.vectors` on every call — an O(n) operation that can be called multiple times per document in downstream rules. For large documents (1000+ segments), this is ~2000 iterations per `BilateralSentiment` reconstruction call.

**Proposed Resolution:** Cache computed properties using `functools.cached_property` (requires `frozen=False`, which is already the case):

```python
from functools import cached_property

class AppraisalDocumentResult(BaseModel):
    model_config = ConfigDict(frozen=False)

    @cached_property
    def judgment_sanction_count(self) -> int:
        return sum(1 for _, v in self.vectors if v.is_negative_judgment_sanction)

    @cached_property
    def dominant_engagement(self) -> EngagementType:
        mono = sum(1 for _, v in self.vectors if v.engagement_type == EngagementType.MONOGLOSS)
        hetero = len(self.vectors) - mono
        return EngagementType.MONOGLOSS if mono >= hetero else EngagementType.HETEROGLOSS
```

---

### FINDING m-04

**Classification:** minor
**Location:** `test_srl_modal_must_boosts_graduation` — `tests/unit/domain/services/test_appraisal_service.py`

**Root Cause:** The test assertion uses `>=` (greater-or-equal):

```python
assert result_with_srl.graduation_force >= result_no_srl.graduation_force
```

Given that `result_no_srl.graduation_force == 0.0` (no graduation words in `"We acknowledge this step."`), the assertion is trivially satisfied by any non-negative value including zero. A proper unit test requires a strict inequality to verify the SRL boost is actually applied:

**Proposed Resolution:**

```python
def test_srl_modal_must_boosts_graduation(self, service):
    text = "We acknowledge this step."
    srl_with_modal = SRLFrame(
        verb="acknowledge",
        arg0=SRLSpan(text="We", start_char=0, end_char=2),
        argm_mod="must"
    )
    result_no_srl = service.analyze(text)
    result_with_srl = service.analyze(text, srl_frame=srl_with_modal)

    assert result_no_srl.graduation_force == 0.0, "Baseline must have zero force"
    assert result_with_srl.graduation_force > 0.0, "Modal 'must' must produce positive force"
    assert result_with_srl.graduation_force_direction == "up", "Direction must be 'up' for 'must'"
    # Verify exact value: srl_argm_mod_graduation_boost default = 0.2
    assert abs(result_with_srl.graduation_force - 0.2) < 0.01
```

---

### FINDING m-05

**Classification:** minor
**Location:** `AppraisalService._detect_engagement()` — default engagement assignment

**Root Cause:** When neither monogloss nor heterogloss patterns are detected, the method returns `(EngagementType.MONOGLOSS, 0.3)` — a confidence of 0.3 for a default. This value is non-zero and will contribute to `engagement_confidence` in downstream uses. A default assignment should have confidence 0.0 (or a clearly designated sentinel confidence like 0.05) to indicate absence of evidence rather than weak positive evidence.

```python
# CURRENT:
if mono_hits == 0 and hetero_hits == 0:
    return EngagementType.MONOGLOSS, 0.3  # misleading: 0.3 implies evidence

# PROPOSED:
if mono_hits == 0 and hetero_hits == 0:
    return EngagementType.MONOGLOSS, 0.0  # explicit: no evidence detected, default applied
```

---

### FINDING m-06

**Classification:** minor
**Location:** `__init__.py` — `src/bb_paxdata/domain/models/` and `src/bb_paxdata/domain/services/`

**Root Cause:** The original report does not specify updates to package `__init__.py` files. If these packages use explicit `__all__` exports (pattern observed in Community 653 — Community 487 protocol packages), the new classes will be invisible to wildcard imports and may cause `ImportError` in downstream consumers that import from the package root.

**Proposed Resolution:** Add to `src/bb_paxdata/domain/models/__init__.py`:

```python
from bb_paxdata.domain.models.appraisal_vector import (
    AppraisalVector,
    AppraisalDocumentResult,
    AffectType,
    JudgmentType,
    AppreciationType,
    EngagementType,
)
```

Add to `src/bb_paxdata/domain/services/__init__.py`:

```python
from bb_paxdata.domain.services.appraisal_service import (
    AppraisalService,
    get_appraisal_service,
    AFFECT_LEXICON,
    JUDGMENT_LEXICON,
    APPRECIATION_LEXICON,
)
```

---

## 5. FINDINGS — INFORMATIONAL

---

### FINDING I-01

**Classification:** informational
**Location:** `AppraisalPipelineConfig` — `GRADUATION_FORCE_LEXICON` sharing

**Root Cause:** The original report notes in §9.4 that `HedgingService.HEDGING_LEXICON["anti_hedge"]` overlaps with graduation force-up words. The config file defines `LexiconConfig.graduation_force_up_words` independently. For long-term maintainability, these should be unified into a shared `GRADUATION_FORCE_LEXICON` constant importable by both services, reducing the risk of divergence as the lexicons evolve.

**Proposed Resolution:** Create `src/bb_paxdata/infrastructure/nlp/shared_lexicons.py`:

```python
"""Shared lexical resources used by multiple NLP services."""

GRADUATION_FORCE_UP: frozenset[str] = frozenset({
    "deeply", "extremely", "profoundly", "sharply", "categorically",
    "strongly", "utterly", "absolutely", "completely", "entirely",
    "highly", "greatly", "severely", "seriously", "fundamentally",
    "blatantly", "flagrantly", "undeniably", "unequivocally",
    # Anti-hedge overlap (also in HedgingService.HEDGING_LEXICON["anti_hedge"]):
    "definitely", "certainly",
})

GRADUATION_FORCE_DOWN: frozenset[str] = frozenset({
    "slightly", "somewhat", "marginally", "barely", "hardly",
    "mildly", "partially", "relatively", "rather", "quite",
    "a bit", "a little", "to some extent", "in some ways",
})
```

This is a non-blocking refactor; implement after core TASK-A03 tests pass.

---

### FINDING I-02

**Classification:** informational
**Location:** `CrossAnomalyService._detect_negative_appraisal_persuasive_tone()` — Community 56

**Root Cause:** This method currently operates on `ai_appraisal_attitude` (a string). After TASK-A03 is live and the bridge from FINDING M-02 is applied, a future task should upgrade this method to consume `AppraisalVector` directly. The upgrade enables three improvements:
1. Distinguish affect-type negativity (grief, fear) from sanction-type negativity (violation, illegal) — currently both resolve to `"NEGATIVE"`.
2. Use `graduation_force` as a signal strength multiplier for the confrontation detection threshold.
3. Use `engagement_type == MONOGLOSS + judgment_is_sanction == True` as a high-precision "categorical accusation" detector.

This is out of scope for TASK-A03 but should be logged as a dependency for TASK-X04 (Propaganda Detection).

---

### FINDING I-03

**Classification:** informational
**Location:** Graph — `Analysis` node, 151 INFERRED edges

**Root Cause:** The graph reports that `Analysis` has 151 INFERRED edges (avg confidence 0.59). Among these, the connections from `Analysis` to `AnalysisAssembler` and `DKIAssembler` (Community 696) are inferred. `DKIAssembler` computes `DKI = (Δθᵢ/Δt) × norm_diplo × 0.4 + ...`. After TASK-A03 adds `appraisal_vector` to `Analysis`/`AIAnalysisResult`, the `DKIAssembler` may need to incorporate `graduation_force` as a signal strength weight for TASK-A07 (Bayesian Position Tracker). This is a forward dependency, not a TASK-A03 blocker.

---

## 6. IMPLEMENTATION SEQUENCE — REVISED

Sequence deviates from the original §8 to address critical findings first:

```
Step 1: New model file (no dependencies, immediately testable)
  → src/bb_paxdata/domain/models/appraisal_vector.py
  → PATCH: Use model_dump() in to_dict_for_db() (FINDING m-02)
  → PATCH: cached_property on AppraisalDocumentResult (FINDING m-03)
  → PATCH: engagement default confidence = 0.0 (FINDING m-05)

Step 2: Protocol definition
  → src/bb_paxdata/application/protocols.py — AppraisalServiceProtocol
  → (FINDING M-04 prerequisite)

Step 3: Config file (no dependencies)
  → src/bb_paxdata/infrastructure/nlp/appraisal_config.py
  → PATCH: Add cache_max_entries field (FINDING m-01)

Step 4: Service file
  → src/bb_paxdata/domain/services/appraisal_service.py
  → PATCH: Thread-safe singleton (FINDING C-01)
  → PATCH: Pre-compile regex patterns (FINDING M-01)
  → PATCH: Consumed-spans tracker in _detect_* methods (FINDING M-03)
  → PATCH: Remove "unacceptable" from APPRECIATION_LEXICON (FINDING M-03)

Step 5: __init__.py exports (FINDING m-06)
  → src/bb_paxdata/domain/models/__init__.py
  → src/bb_paxdata/domain/services/__init__.py

Step 6: Existing model updates
  → power_index.py: Direct import (not TYPE_CHECKING), no model_rebuild() needed (FINDING M-05)
  → bilateral_sentiment.py: Replace getattr() with direct field access
  → ai_analysis.py: Add fields + appraisal_attitude_from_vector bridge property (FINDING M-02)

Step 7: ServiceContainer registration (FINDING M-04)
  → src/bb_paxdata/infrastructure/container/service_container.py

Step 8: CollectStage integration (FINDINGS C-03, M-01, M-06)
  → Add _collect_appraisal() async method with run_in_executor
  → Remove §4 analysis_trigger.py mutation pattern entirely
  → Store result in PipelineResult.extra_data, not on frozen Segment

Step 9: AssemblyStage: aggregate AppraisalDocumentResult → AIAnalysisResult (FINDING C-02)
  → Implement _aggregate_appraisal_vector()
  → Assign appraisal_judgment_sanction_count from doc_result.judgment_sanction_count (int)

Step 10: Tests
  → tests/unit/domain/models/test_appraisal_vector.py
  → tests/unit/domain/services/test_appraisal_service.py
  → PATCH: Fix srl_modal assertion (FINDING m-04)
  → ADD: test_service_container_has_appraisal_service()
  → ADD: test_collect_stage_runs_appraisal()

Step 11: Integration verification
  → pytest tests/ -k "appraisal" -v
  → pytest tests/unit/test_service_container.py -v
  → Measure latency delta on 100-segment batch
```

---

## 7. SUCCESS CRITERIA — REVISED

Original criteria preserved with precision corrections:

```
[C1] F1 ≥ 0.72 per axis independently (AFFECT, JUDGMENT, APPRECIATION)
     Measurement: SysFan evaluation set; if unavailable, 50 manually annotated
     diplomatic segments with ground truth labels.
     Failure condition: Any single axis F1 < 0.65 requires lexicon expansion before merge.

[C2] appraisal_judgment_sanction_count is type int, value ≥ 0, never bool
     Measurement: assert isinstance(r.appraisal_judgment_sanction_count, int)
     on 20 documents.

[C3] asymmetry_score variance increase ≥ 20% (10-session sample)
     Baseline: compute BilateralSentiment.asymmetry_score pre-TASK-A03.
     Measurement: scipy.stats.levene(pre_scores, post_scores) p < 0.05.

[C4] Graduation force ↔ HedgingService confidence_level Pearson r > 0.6
     Measurement: pearsonr on 100 paired (segment, appraisal_force, hedging_confidence)
     tuples. Note: correlation expected to be imperfect due to legitimate divergence
     (hedging anti-hedge ≠ appraisal graduation in all cases).

[C5] Pipeline latency increase < 10% (lexicon mode, classifier disabled)
     Measurement: timeit on analyze_document([100 segments]) pre/post TASK-A03.
     Pre-compiled regex requirement (FINDING M-01) is prerequisite to pass this gate.

[C6] AIAnalysisResult.coverage_rate ≥ 0.60 on 50 diplomatic transcript segments
     Measurement: AppraisalDocumentResult.coverage_rate ≥ 0.60.

[C7] Thread-safety test: 20 concurrent threads calling get_appraisal_service() return same id()
     Measurement: assert len({id(get_appraisal_service()) for _ in range(20)}) == 1
     under threading.Thread concurrency.

[C8] ServiceContainer.appraisal_service is not None after initialization
     Measurement: existing test_service_container_initialization() extended.
```

---

## 8. DEPENDENCY MAP — PRECISE

```
TASK-A01 (SRL Enrichment Layer) [COMPLETE]
  Provides: SRLFrame.argm_mod → AppraisalService._detect_graduation() boost
  Provides: SRLDocumentResult → analyze_document(srl_frames_by_segment)
  Interface contract: SRLFrame.argm_mod is Optional[str], modal verb or None
    Verify: SRLFrame model in src/bb_paxdata/domain/models/srl.py has argm_mod field.
    Risk: If TASK-A01 uses a different field name (e.g., argm_modal), _detect_graduation()
          will silently skip all SRL boosts (srl_frame.argm_mod returns AttributeError,
          which is not caught — the code accesses srl_frame.argm_mod without hasattr guard).
    Fix: Add guard: modal = getattr(srl_frame, 'argm_mod', None) or getattr(srl_frame, 'argm_modal', None)

TASK-A03 [THIS TASK]
  Produces: AppraisalVector on Segment (via PipelineResult.extra_data)
  Produces: AppraisalDocumentResult for session-level aggregation
  Modifies: AIAnalysisResult (appraisal_vector, appraisal_judgment_sanction_count, dominant_appraisal_axis)
  Does NOT modify: Segment (frozen), PowerIndex (read-only after ASSEMBLE)

TASK-A07 (Bayesian Position Tracker) [FUTURE]
  Consumes: AppraisalVector.graduation_force → signal strength weight
  Consumes: AppraisalVector.judgment_is_sanction → costly signal flag

TASK-X04 (Propaganda Detection) [FUTURE]
  Consumes: JUDGMENT:sanction/negative → Loaded Language, Name Calling
  Consumes: AFFECT:negative/high_force → Appeal to Fear
  Requires: FINDING M-02 Phase B (CrossAnomalyService refactor) to be complete
```

---

## 9. FILE MANIFEST — COMPLETE

```
NEW FILES:
  src/bb_paxdata/domain/models/appraisal_vector.py
  src/bb_paxdata/domain/services/appraisal_service.py
  src/bb_paxdata/infrastructure/nlp/appraisal_config.py
  src/bb_paxdata/infrastructure/nlp/shared_lexicons.py          [FINDING I-01]
  tests/unit/domain/models/test_appraisal_vector.py
  tests/unit/domain/services/test_appraisal_service.py

MODIFIED FILES:
  src/bb_paxdata/domain/models/power_index.py
    CHANGE: Direct import of AppraisalVector (not TYPE_CHECKING)
    CHANGE: Optional[AppraisalVector] field + appraisal_weighted_power property
    REMOVE: Forward reference string annotation

  src/bb_paxdata/domain/models/bilateral_sentiment.py
    CHANGE: asymmetry_score property — replace getattr() with direct field access
    CHANGE: appraisal_weight computation uses PowerIndex.appraisal_vector directly

  src/bb_paxdata/domain/models/ai_analysis.py
    CHANGE: Import AppraisalVector
    CHANGE: 3 new fields (appraisal_vector, appraisal_judgment_sanction_count, dominant_appraisal_axis)
    ADD: appraisal_attitude_from_vector bridge property [FINDING M-02]

  src/bb_paxdata/domain/models/__init__.py
    ADD: AppraisalVector exports [FINDING m-06]

  src/bb_paxdata/domain/services/__init__.py
    ADD: AppraisalService exports [FINDING m-06]

  src/bb_paxdata/application/protocols.py
    ADD: AppraisalServiceProtocol [FINDING M-04]

  src/bb_paxdata/infrastructure/container/service_container.py
    ADD: AppraisalService registration [FINDING M-04]

  src/bb_paxdata/application/pipeline/collect_stage.py  [or equivalent]
    ADD: _collect_appraisal() async method with run_in_executor [FINDINGS C-03, M-01, M-06]
    ADD: AppraisalServiceProtocol constructor injection

  src/bb_paxdata/application/pipeline/assemble_stage.py [or equivalent]
    ADD: _aggregate_appraisal_vector() + AIAnalysisResult population [FINDING C-02]

  tests/unit/test_service_container.py
    ADD: test_service_container_has_appraisal_service()

EXPLICITLY NOT MODIFIED:
  analysis_trigger.py (any variant) — §4 pattern from original report is incorrect;
    all integration happens in CollectStage/AssemblyStage [FINDING M-06, FINDING C-03]
```

---

## 10. KNOWN LIMITATIONS AND DEFERRED ITEMS

**Lexicon coverage:** The diplomatic corpus spans Turkish, English, and potentially Arabic/Russian segments. The current AFFECT/JUDGMENT/APPRECIATION lexicons contain English-only entries. Turkish appraisal expressions (e.g., "derin endişe" = "deeply concerned") are not covered. The DIPLO lexicon (`community 176` — Turkish diplomatic lexicon) should be cross-referenced and a `AFFECT_LEXICON_TR` extension created. This is deferred but should be planned before production deployment.

**Classifier mode (`use_classifier=True`):** The `AppraisalPipelineConfig.classifier_model_name = "cross-encoder/nli-deberta-v3-base"` references a zero-shot NLI model, not a fine-tuned appraisal classifier. Zero-shot NLI on appraisal labels has reported F1 in the 0.55–0.65 range on SysFan. The `fine_tuned_path` option is the production path; zero-shot should be treated as a development baseline only.

**`SRLFrame.argm_mod` field name verification:** The SRL integration assumes `argm_mod` is a direct field on `SRLFrame`. This must be verified against the TASK-A01 implementation before the `_detect_graduation()` SRL branch is tested. A missing field raises `AttributeError` at runtime without the `getattr` guard proposed in the dependency map above.

**`AppraisalVector` missing from `CrossAnomalyService.AnalysisContext`:** Community 119 shows `AnalysisContext` memoizes service call results. After integration, `"appraisal"` must be added as a recognized key in `AnalysisContext._cache` to enable downstream rules in `CrossAnomalyService` to access the vector without re-computation.