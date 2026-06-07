# TASK-E01 · Contrastive Analysis Engine — Delta Mode
## Upgraded Development Report (v2.0 — Machine-Optimized)

**Report Version:** 2.0
**Supersedes:** v1.0
**Generated:** 2026-06-05
**Target:** Antigravity AI Implementation Agent

---

## SECTION 0 — TASK SPECIFICATION (AUTHORITATIVE)

**Task ID:** TASK-E01
**Category:** Engineering | **Difficulty:** M | **Priority:** P1

**Problem Statement:** PaxData processes each session independently. No automated mechanism exists to answer "what changed between two sessions?". This task implements a cross-session output comparison layer that operates on existing model outputs — no new ML models are required.

**Deliverables (binding):**
- domain/models/analysis_delta.py — AnalysisDelta, MetricDelta, SpeechActDistributionDelta, NarrativeLayerDelta 
- domain/models/contrast_report.py — ContrastReport 
- domain/services/compare_sessions_protocols.py — ISBIRepository, IDKIRepository, IAnalysisRepository 
- infrastructure/db/repositories/sbi_repository.py — SBIRepository 
- application/use_cases/compare_sessions.py — CompareSessionsUseCase, CompareSessionsInput, CompareSessionsOutput 
- interfaces/api/routers/v1/compare.py — POST /api/v1/compare/sessions, GET /api/v1/compare/sessions/available 
- interfaces/api/schemas.py — new request/response schemas (additive update)

**Success Criteria (contractual):**
- Delta calculation wall-time (DB fetch + compute, excluding LLM) < 2 seconds at P95
- Significant change detection precision ≥ 0.85 (manual evaluation against labeled pairs)
- LLM narrative coherence score ≥ 4/5 (LLM-as-judge protocol)
- Unit test coverage > 85% per module
- API success rate > 99% (LLM failure is a soft degradation, not a failure)

---

## SECTION 1 — EXISTING SYSTEM DATA MODEL (AUTHORITATIVE)

### 1.1 Session/Panel Identity

panel_id and session_id are used interchangeably across the codebase. File (infrastructure/db/models.py) uses file_id (PK), panel_number, date_str. All analysis result tables use session_id: str as the foreign reference. All repository methods in this task MUST accept session_id: str as the session identifier.

### 1.2 Existing Analysis Result Models

**SBI:**
- Domain: SpeakerPosition (domain/models/sbi_models.py)
- Fields: speaker_id: str, session_id: str, wordfish_theta: float, stance_density: float, engagement_score: float, sbi: float 
- ORM: SpeakerPositionTable (infrastructure/db/sbi_table.py)
- **REQUIRED ACTION:** SpeakerPositionTable must implement to_domain() -> SpeakerPosition. This method is assumed by SBIRepository and will raise AttributeError at runtime if absent. It must be added in Phase 2 before integration testing.

**DKI:**
- Domain: DKIResult (domain/models/dki.py)
- Fields: speaker_id: str, session_id: str, dki_score: float, velocity: float, semantic_shift: float, debate_loading: float 
- ORM: DKIResultModel (infrastructure/db/dki_table.py)
- Repository: DKIRepository (infrastructure/db/repositories/dki_repository.py) — must implement IDKIRepository protocol; verify get_by_session(session_id: str) -> list[DKIResult] exists or add it.

**Risk Score:**
- Source: AISentenceAnalysis (infrastructure/db/models.py, line 1993+)
- Domain accessor: Analysis.ai_risk_score: float | None, Analysis.risk_level: str, Analysis.risk_trajectory: str, Analysis.future_risk_tier: str 
- **Semantic clarification required:** ai_risk_score is sentence-level. _fetch_risk_data computes arithmetic mean over all analyses in a session. This is valid only if the corpus is balanced across speakers. A weighted average (by sentence length or analysis weight) is architecturally preferable but is deferred to a later task. The arithmetic mean is accepted for v1.

**Hedging:**
- Source: Analysis.hedging_result: HedgingResult | None 
- HedgingResult fields: score: float, categories: dict, confidence: float 
- _fetch_hedging_data aggregates score per speaker by arithmetic mean. Same semantic caveat as risk applies.

**Speech Act:**
- Source: Analysis.speech_act: SpeechActClassification | None 
- Analysis.speech_act.primary_type.value — string identifier for the act type
- Distribution normalized to percentage sum = 1.0 per speaker per session.

**Narrative/Discourse Flow:**
- Domain: DiscourseFlow (domain/models/discourse_flow.py)
- Fields: narrative_layer: str, narrative_target_actor: str, narrative_salience: float 
- Repository: DiscourseFlowRepository (infrastructure/db/repositories/country_repository.py)
- **STATUS:** _fetch_narrative_data is a non-functional stub (returns {}). See FINDING-001.

**Bilateral Sentiment:**
- Domain: BilateralSentiment (domain/models/bilateral_sentiment.py)
- Fields: panel_id: str, from_country: str, to_country: str, affinity_score: float, avg_sentiment: float 
- **STATUS:** Injected into use case constructor but never used. See FINDING-014.

### 1.3 Existing Infrastructure Patterns

**BaseRepository** (infrastructure/db/repositories/base.py):
```python
class BaseRepository(Generic[ModelT]):
    model_class: type[ModelT]
    def __init__(self, session: AsyncSession) -> None: ...
    async def get_by_id(self, id: int) -> ModelT | None: ...
    async def get_all(self) -> list[ModelT]: ...
    async def save(self, entity: ModelT) -> ModelT: ...
    async def delete(self, id: int) -> bool: ...
```
All new repositories MUST inherit from BaseRepository and implement their domain-specific protocol.

**Use Case Pattern** (reference: aggregate_bilateral_sentiment.py):
- @dataclass(frozen=True) for Input/Output
- succeeded: bool property on Output
- Constructor injection of repositories via typed parameters
- async def execute(self, input_data: InputType) -> OutputType 
- structlog structured logging at entry and exit

**API Router Pattern** (reference: interfaces/api/routers/v1/discourse.py):
- @router.get/post(...) with response_model= declared
- db: AsyncSession = Depends(get_db) 
- _has_permission: bool = Depends(PermissionChecker("permission_name")) — REQUIRED on all endpoints

---

## SECTION 2 — FINDINGS AND REQUIRED CORRECTIONS

The following findings are ordered by severity. All CRITICAL and MAJOR findings MUST be resolved before Phase acceptance. MINOR findings SHOULD be resolved; INFORMATIONAL findings are architectural notes.

---

### FINDING-001

**Classification:** CRITICAL
**Location:** application/use_cases/compare_sessions.py → _fetch_narrative_data 
**Root Cause:** _fetch_narrative_data is a permanent stub that unconditionally returns {}. All downstream NarrativeLayerDelta objects are constructed with empty layer_weights_a and layer_weights_b, making delta_narrative a populated dict of zero-delta objects. The DiscourseFlowRepository is available in infrastructure/db/repositories/country_repository.py but is never wired to this use case.

**Current Code (non-functional):**
```python
async def _fetch_narrative_data(self, session_id: str) -> dict[str, dict[str, float]]:
    # This depends on narrative salience tracker implementation
    # Placeholder implementation
    return {}
```

**Proposed Resolution:** Wire DiscourseFlowRepository into the use case and implement the fetch using narrative_salience as the weight:

```python
# domain/services/compare_sessions_protocols.py — add to protocol file
from bb_paxdata.domain.models.discourse_flow import DiscourseFlow

class IDiscourseFlowRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[DiscourseFlow]: ...

# application/use_cases/compare_sessions.py
class CompareSessionsUseCase:
    def __init__(
        self,
        sbi_repository: ISBIRepository,
        dki_repository: IDKIRepository,
        analysis_repository: IAnalysisRepository,
        bilateral_repository: IBilateralSentimentRepository,
        discourse_repository: IDiscourseFlowRepository,  # ADD THIS
        llm_service: LLMServiceProtocol | None = None,
    ) -> None:
        ...
        self._discourse_repo = discourse_repository

    async def _fetch_narrative_data(
        self, session_id: str
    ) -> dict[str, dict[str, float]]:
        flows: list[DiscourseFlow] = await self._discourse_repo.get_by_session(session_id)
        # Aggregate narrative_salience per (speaker, narrative_layer)
        # DiscourseFlow does not have speaker_id — if speaker attribution is absent,
        # aggregate at session level under a synthetic "__session__" key.
        # This must be confirmed against the DiscourseFlow schema before implementation.
        speaker_layers: dict[str, dict[str, list[float]]] = {}
        for flow in flows:
            # FIXME: confirm field name for speaker attribution in DiscourseFlow
            speaker = getattr(flow, "speaker_id", "__session__")
            speaker_layers.setdefault(speaker, {}).setdefault(
                flow.narrative_layer, []
            ).append(flow.narrative_salience)
        return {
            speaker: {
                layer: sum(vals) / len(vals)
                for layer, vals in layers.items()
            }
            for speaker, layers in speaker_layers.items()
        }
```

**Impact Assessment:** Without this fix, delta_narrative is always structurally populated but semantically empty. Any downstream consumer treating non-empty delta_narrative keys as valid evidence of narrative change will produce false positives.

---

### FINDING-002

**Classification:** CRITICAL
**Location:** application/use_cases/compare_sessions.py → _calculate_delta → speech act most_changed_type and narrative dominant_layer_change 
**Root Cause:** Both max() calls use key=dict.get which selects the key with the highest raw (signed) delta, not the highest absolute delta. A large negative delta is always ignored in favor of any positive delta, regardless of magnitude.

**Current Code (both instances):**
```python
# Speech act — line ~865
most_changed = max(delta_dist, key=delta_dist.get) if delta_dist else None
change_mag = abs(delta_dist[most_changed]) if most_changed else 0.0

# Narrative — line ~893
max_layer = max(delta_weights, key=delta_weights.get)
dominant_change = (max_layer, delta_weights[max_layer])
```

**Proposed Resolution:**
```python
# Speech act
most_changed = (
    max(delta_dist, key=lambda k: abs(delta_dist[k])) if delta_dist else None
)
change_mag = abs(delta_dist[most_changed]) if most_changed else 0.0

# Narrative
max_layer = max(delta_weights, key=lambda k: abs(delta_weights[k]))
dominant_change = (max_layer, delta_weights[max_layer])
```

**Impact Assessment:** SpeechActDistributionDelta.most_changed_type and NarrativeLayerDelta.dominant_layer_change systematically misidentify the highest-magnitude change when the true maximum is a decrease. LLM prompt and key_insights derived from these fields will be factually incorrect.

---

### FINDING-003

**Classification:** CRITICAL
**Location:** domain/models/contrast_report.py → class Config 
**Root Cause:** ContrastReport uses Pydantic v1 class Config syntax. The project requires pydantic>=2.0. In Pydantic v2, class Config is not recognized as a model configuration mechanism; json_encoders within it is silently ignored. datetime fields will serialize using Pydantic v2's default ISO 8601 format (which is actually correct), but any other json_encoders defined here will be silently dropped. Additionally, this signals that the author was unaware of the v1/v2 migration and may indicate other Pydantic v1 patterns exist in the new files.

**Current Code:**
```python
class Config:
    json_encoders = {
        datetime: lambda v: v.isoformat(),
    }
```

**Proposed Resolution:**
```python
from pydantic import ConfigDict

class ContrastReport(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )
    ...
```

Note: In Pydantic v2, datetime fields already serialize to ISO 8601 strings by default via .model_dump(mode="json"). The json_encoders entry is functionally redundant but the class Config pattern must still be removed to prevent confusion and future divergence.

**Impact Assessment:** If additional json_encoders are added to ContrastReport.Config in the future, they will silently fail with no error. The model will exhibit undefined serialization behavior.

---

### FINDING-004

**Classification:** CRITICAL
**Location:** application/use_cases/compare_sessions.py → CompareSessionsOutput.succeeded + endpoint compare_sessions 
**Root Cause:** execute() appends errors to errors list without always setting success=False. For example, SBI fetch failure appends "SBI data fetch failed: ..." to errors but sets sbi_a = {} and continues. Narrative generation failure also appends to errors and continues. The final successful path returns CompareSessionsOutput(success=True, ..., errors=tuple(errors)). succeeded is defined as self.success and len(self.errors) == 0, so any non-fatal error causes succeeded to return False. The endpoint then raises HTTP 500.

**Consequence:** A single LLM timeout converts a fully computed delta result into an HTTP 500. The client receives no data. This violates the stated requirement that "LLM failure is a soft degradation."

**Current Code:**
```python
# CompareSessionsOutput
@property
def succeeded(self) -> bool:
    return self.success and len(self.errors) == 0

# endpoint
if not output.succeeded:
    raise HTTPException(status_code=500, detail=...)
```

**Proposed Resolution:** Separate hard failures (delta computation failed) from soft failures (LLM narrative failed):

```python
@dataclass(frozen=True)
class CompareSessionsOutput:
    success: bool  # False only if delta calculation itself failed
    contrast_report: ContrastReport | None = None
    analysis_delta: AnalysisDelta | None = None
    errors: tuple[str, ...] = ()          # non-fatal errors (LLM, missing metrics)
    fatal_errors: tuple[str, ...] = ()    # fatal errors (delta calculation failed)

    @property
    def succeeded(self) -> bool:
        """True if delta was computed, regardless of soft failures."""
        return self.success and len(self.fatal_errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.errors) > 0
```

Update execute():
```python
# Step 1 fetch failures: append to errors (soft), continue
# Step 2 delta failure: append to fatal_errors, return success=False
# Step 3 LLM failure: append to errors (soft), continue with empty narrative
# Final return: success=True, errors=soft_errors, fatal_errors=()
```

Update endpoint:
```python
if not output.succeeded:
    raise HTTPException(
        status_code=500,
        detail={"fatal_errors": list(output.fatal_errors)}
    )
# return 200 with warnings in errors list even if LLM failed
```

**Impact Assessment:** Current behavior makes the API unreliable during any LLM degradation window. All successfully computed deltas are discarded. This directly violates the 99% success rate acceptance criterion.

---

### FINDING-005

**Classification:** CRITICAL
**Location:** application/use_cases/compare_sessions.py → _build_narrative_prompt 
**Root Cause:** The multi-line string at line ~999 contains {language} as a Python f-string-style placeholder, but the string is not an f-string and .format() is never called. The literal text {language} is sent to the LLM.

**Current Code:**
```python
base_prompt += """
Provide a concise 3-4 paragraph summary in {language} that:
1. Highlights the most important changes
...
"""
```

**Proposed Resolution:**
```python
base_prompt += f"""
Provide a concise 3-4 paragraph summary in {language} that:
1. Highlights the most important changes
2. Identifies which speaker(s) shifted the most
3. Explains what dimensions changed most significantly
4. Provides context on whether these changes represent escalation or de-escalation

Focus on actionable insights for diplomatic analysts.
"""
```

Alternatively, apply .format(language=language) to the assembled base_prompt before returning, but this risks double-formatting if any data embedded in the prompt contains {...} patterns. The f-string approach at the point of construction is safer.

**Impact Assessment:** Every LLM-generated narrative summary is produced in the model's default language (typically English), ignoring the narrative_language parameter. Requests specifying narrative_language="tr" receive English output. This silently degrades the feature for non-English use cases.

---

### FINDING-006

**Classification:** CRITICAL
**Location:** application/use_cases/compare_sessions.py → _generate_narrative_cached (Section 5.3)
**Root Cause (A):** @lru_cache does not compose with async def. lru_cache stores and returns the coroutine object on cache hit, not the resolved value. Every cache hit returns a stale coroutine that, when awaited, raises RuntimeError: cannot reuse already awaited coroutine.

**Root Cause (B):** The cached function signature is _generate_narrative_cached(delta_hash: str, language: str) but the body calls self._generate_narrative(delta, language) where delta is not a parameter of the cached function. This is a NameError at runtime.

**Current Code:**
```python
@lru_cache(maxsize=100)
async def _generate_narrative_cached(delta_hash: str, language: str) -> str:
    return await self._generate_narrative(delta, language)  # 'delta' is undefined
```

**Proposed Resolution:** Use an explicit dict cache as an instance variable:

```python
class CompareSessionsUseCase:
    def __init__(self, ...):
        ...
        self._narrative_cache: dict[tuple[str, str], str] = {}

    async def _get_cached_narrative(
        self, delta: AnalysisDelta, language: str
    ) -> str:
        import hashlib, json
        # Stable hash: sort keys for determinism
        delta_key = hashlib.sha256(
            json.dumps(
                {
                    "a": delta.session_a_id,
                    "b": delta.session_b_id,
                    "changes": sorted(delta.significant_changes),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        cache_key = (delta_key, language)
        if cache_key not in self._narrative_cache:
            self._narrative_cache[cache_key] = await self._generate_narrative(
                delta, language
            )
        return self._narrative_cache[cache_key]
```

For production deployments requiring distributed caching, replace self._narrative_cache with a Redis-backed async cache injected via constructor. The in-process dict is appropriate for single-process deployments.

**Impact Assessment:** If the lru_cache version is deployed, all narrative generation requests either fail on first call with NameError or return un-awaitable coroutines on cache hit, causing RuntimeError. The narrative generation subsystem is completely non-functional as specified.

---

### FINDING-007

**Classification:** CRITICAL
**Location:** domain/services/compare_sessions_protocols.py → IAnalysisRepository 
**Root Cause:** IAnalysisRepository.get_by_session declares return type list[Analysis] but Analysis is not imported in the protocol file. At module load time, Python resolves Analysis in the function annotation. Without from __future__ import annotations (which defers evaluation) or an explicit import, this raises NameError: name 'Analysis' is not defined.

**Current Code:**
```python
class IAnalysisRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[Analysis]: ...  # Analysis undefined
    async def get_by_speaker(self, speaker_id: str) -> list[Analysis]: ...
```

**Proposed Resolution:**
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bb_paxdata.domain.models.analysis import Analysis

class IAnalysisRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[Analysis]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[Analysis]: ...
```

Or use a runtime import:
```python
from bb_paxdata.domain.models.analysis import Analysis
```

The TYPE_CHECKING guard is preferred to avoid circular imports if Analysis imports from protocols.

**Impact Assessment:** Module fails to load entirely. All code that imports compare_sessions_protocols crashes at import time.

---

### FINDING-008

**Classification:** MAJOR
**Location:** application/use_cases/compare_sessions.py → execute() → all _fetch_* calls
**Root Cause:** All six fetch operations — _fetch_sbi_data, _fetch_dki_data, _fetch_risk_data, _fetch_hedging_data, _fetch_speech_act_data, _fetch_narrative_data — for both sessions are executed sequentially. These are independent I/O operations with no data dependencies on each other. Sequential execution adds worst-case latency equal to the sum of all individual query times.

Additionally, _fetch_risk_data, _fetch_hedging_data, and _fetch_speech_act_data all call self._analysis_repo.get_by_session(session_id) independently. For two sessions, this produces 6 identical queries against AISentenceAnalysis. Each query returns the same full result set.

**Proposed Resolution:**

Step 1 — Deduplicate analysis fetches by pre-fetching once per session:

```python
async def execute(self, input_data: CompareSessionsInput) -> CompareSessionsOutput:
    session_a, session_b = input_data.session_a_id, input_data.session_b_id

    # Pre-fetch analyses once per session (avoids 3x duplicate queries)
    analyses_a: list[Analysis] = []
    analyses_b: list[Analysis] = []
    try:
        analyses_a, analyses_b = await asyncio.gather(
            self._analysis_repo.get_by_session(session_a),
            self._analysis_repo.get_by_session(session_b),
        )
    except Exception as exc:
        return CompareSessionsOutput(
            success=False,
            fatal_errors=(f"Analysis fetch failed: {exc}",),
        )

    # All remaining fetches are parallelized
    results = await asyncio.gather(
        self._fetch_sbi_data(session_a),
        self._fetch_sbi_data(session_b),
        self._fetch_dki_data(session_a),
        self._fetch_dki_data(session_b),
        self._fetch_risk_from_analyses(analyses_a),
        self._fetch_risk_from_analyses(analyses_b),
        self._fetch_hedging_from_analyses(analyses_a),
        self._fetch_hedging_from_analyses(analyses_b),
        self._fetch_speech_act_from_analyses(analyses_a),
        self._fetch_speech_act_from_analyses(analyses_b),
        self._fetch_narrative_data(session_a),
        self._fetch_narrative_data(session_b),
        return_exceptions=True,
    )
    # Unpack results, check for exceptions per fetch
```

Step 2 — Refactor analysis-derived fetches to accept pre-fetched list[Analysis] instead of querying:

```python
def _fetch_risk_from_analyses(self, analyses: list[Analysis]) -> float | None:
    risk_scores = [a.ai_risk_score for a in analyses if a.ai_risk_score is not None]
    return sum(risk_scores) / len(risk_scores) if risk_scores else None

def _fetch_hedging_from_analyses(
    self, analyses: list[Analysis]
) -> dict[str, float]:
    speaker_hedging: dict[str, list[float]] = {}
    for a in analyses:
        if a.hedging_result and a.speaker_id:
            speaker_hedging.setdefault(a.speaker_id, []).append(a.hedging_result.score)
    return {s: sum(v) / len(v) for s, v in speaker_hedging.items()}

def _fetch_speech_act_from_analyses(
    self, analyses: list[Analysis]
) -> dict[str, dict[str, float]]:
    dist: dict[str, dict[str, float]] = {}
    for a in analyses:
        if a.speech_act and a.speaker_id:
            d = dist.setdefault(a.speaker_id, {})
            act_type = a.speech_act.primary_type.value
            d[act_type] = d.get(act_type, 0.0) + 1.0
    for speaker in dist:
        total = sum(dist[speaker].values())
        if total > 0:
            dist[speaker] = {k: v / total for k, v in dist[speaker].items()}
    return dist
```

**Impact Assessment:** Sequential execution with 6 per-session fetches (12 total async calls), three of which are identical get_by_session queries, adds approximately 3–6× unnecessary latency. The 2-second P95 target for delta calculation is at risk on any database with non-trivial query latency. The duplicate queries also impose unnecessary load on the database connection pool.

---

### FINDING-009

**Classification:** MAJOR
**Location:** infrastructure/db/repositories/sbi_repository.py → get_by_speaker 
**Root Cause:** get_by_speaker orders results by self.model_class.computed_at, but SpeakerPositionTable's documented fields (session_id, speaker_id, wordfish_theta, stance_density, engagement_score, sbi) do not include computed_at. This raises AttributeError: type object 'SpeakerPositionTable' has no attribute 'computed_at' at runtime.

**Current Code:**
```python
async def get_by_speaker(self, speaker_id: str) -> list[SpeakerPosition]:
    stmt = select(self.model_class).where(
        self.model_class.speaker_id == speaker_id
    ).order_by(self.model_class.computed_at)  # 'computed_at' does not exist
```

**Proposed Resolution:** Confirm the correct timestamp or ordering column in SpeakerPositionTable. If no timestamp column exists, add one:

```python
# infrastructure/db/sbi_table.py — add if absent
computed_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
)
```

Then use it in the repository:
```python
.order_by(self.model_class.computed_at.asc())
```

If no ordering is required by protocol consumers, remove the .order_by() clause entirely rather than using an incorrect column.

**Impact Assessment:** get_by_speaker raises AttributeError on every call. While CompareSessionsUseCase does not call get_by_speaker directly, any future consumer of SBIRepository that calls get_by_speaker will fail.

---

### FINDING-010

**Classification:** MAJOR
**Location:** interfaces/api/routers/v1/compare.py → compare_sessions endpoint
**Root Cause (A):** Repository classes are imported inside the endpoint function body. While CPython caches imports after the first load, this is an anti-pattern that bypasses the FastAPI dependency injection system and makes the endpoint impossible to unit-test without monkeypatching.

**Root Cause (B):** AIAnalyst() is instantiated with no arguments. AIAnalyst is an LLM client that requires configuration (API keys, model name, timeout). Constructing it inside the handler with no arguments either requires AIAnalyst to read from global config (a side effect that is untestable) or it silently constructs an unconfigured client that fails on the first LLM call.

**Root Cause (C):** Neither compare_sessions nor list_available_sessions includes _has_permission: bool = Depends(PermissionChecker(...)). This violates the access control requirement specified in Section 9.1 of the original report.

**Current Code:**
```python
@router.post("/sessions", response_model=CompareSessionsResponse)
async def compare_sessions(
    request: CompareSessionsRequest,
    db: AsyncSession = Depends(get_db),
    # Missing: _has_permission
):
    from bb_paxdata.infrastructure.db.repositories.sbi_repository import SBIRepository
    ...
    llm_service = AIAnalyst() if request.include_narrative else None
```

**Proposed Resolution:** Use FastAPI's Depends for all dependencies:

```python
# infrastructure/di.py (or existing DI module)
def get_llm_service() -> AIAnalyst:
    return AIAnalyst(
        model=settings.COMPARISON_NARRATIVE_MODEL,
        max_tokens=settings.COMPARISON_NARRATIVE_MAX_TOKENS,
    )

def get_compare_use_case(
    db: AsyncSession = Depends(get_db),
    llm_service: AIAnalyst = Depends(get_llm_service),
) -> CompareSessionsUseCase:
    return CompareSessionsUseCase(
        sbi_repository=SBIRepository(db),
        dki_repository=DKIRepository(db),
        analysis_repository=AnalysisRepository(db),
        bilateral_repository=BilateralSentimentRepository(db),
        discourse_repository=DiscourseFlowRepository(db),
        llm_service=llm_service,
    )

# interfaces/api/routers/v1/compare.py
@router.post("/sessions", response_model=CompareSessionsResponse)
async def compare_sessions(
    request: CompareSessionsRequest,
    use_case: CompareSessionsUseCase = Depends(get_compare_use_case),
    _has_permission: bool = Depends(PermissionChecker("create_comparison")),
):
    ...

@router.get("/sessions/available")
async def list_available_sessions(
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("view_comparison")),
):
    ...
```

**Impact Assessment:** Without permission checking, all comparison endpoints are publicly accessible to any authenticated user regardless of role. Without DI, the endpoint cannot be integration-tested without database access. AIAnalyst() with no arguments will produce undefined behavior in any environment where configuration is not globally available.

---

### FINDING-011

**Classification:** MAJOR
**Location:** interfaces/api/routers/v1/compare.py and interfaces/api/schemas.py — URL inconsistency
**Root Cause:** The router uses prefix="/compare" and @router.post("/sessions"). The resolved URL is /api/v1/compare/sessions. However, Section 9.1 of the original report declares @router.post("/sessions/compare"), which would resolve to /api/v1/compare/sessions/compare — a different, incorrect URL. The curl example in Appendix E.2 uses /api/v1/compare/sessions (the correct resolved path). The Section 9.1 declaration is incorrect and must not be used as the implementation reference.

**Authoritative URL contract:**
- POST /api/v1/compare/sessions — execute comparison
- GET /api/v1/compare/sessions/available — list available session IDs

**Impact Assessment:** If a developer implements based on Section 9.1 instead of the actual router code, the endpoint resolves to a different URL, causing all API clients to receive 404. This inconsistency must be removed from all documentation and confirmed as the /compare/sessions path.

---

### FINDING-012

**Classification:** MAJOR
**Location:** application/use_cases/compare_sessions.py → _extract_key_insights 
**Root Cause:** The list comprehension accesses delta.delta_sbi_normalized[speaker] via direct dict subscript, not .get(). If delta_sbi_significant[speaker] is True but speaker is absent from delta_sbi_normalized (possible through any delta computation bug or future refactor), this raises KeyError and the entire execute() call propagates an unhandled exception.

**Current Code:**
```python
sbi_changes = [
    (speaker, delta.delta_sbi_normalized[speaker])  # KeyError if speaker absent
    for speaker, is_sig in delta.delta_sbi_significant.items()
    if is_sig
]
```

**Proposed Resolution:**
```python
sbi_changes = [
    (speaker, norm_delta)
    for speaker, is_sig in delta.delta_sbi_significant.items()
    if is_sig
    if (norm_delta := delta.delta_sbi_normalized.get(speaker)) is not None
]
```

Apply the same pattern to any other location that crosses delta_dki_significant/delta_dki_normalized, delta_hedging_significant/delta_hedging_normalized.

**Impact Assessment:** KeyError in _extract_key_insights causes ContrastReport construction to fail. The execute() method catches this via the outer try/except block, appends to errors, and returns success=False. This turns a non-critical metadata extraction failure into a hard failure of the entire comparison.

---

### FINDING-013

**Classification:** MAJOR
**Location:** domain/models/contrast_report.py — data duplication of computed properties
**Root Cause:** ContrastReport stores most_drifted_speaker and most_drifted_dimension as concrete fields, set from delta.most_drifted_speaker and delta.most_drifted_dimension at construction time. AnalysisDelta already exposes these as computed @property values derived from the delta dicts. This creates two sources of truth. If ContrastReport is serialized to JSON and reconstructed, the delta field recomputes the properties fresh (correct values) while the stored fields retain the values from construction time. These will diverge if delta data is mutated post-construction (not possible with frozen delta, but possible if serialization/deserialization is involved and AnalysisDelta is not frozen=True).

**Root Cause Detail:** AnalysisDelta is a BaseModel, not a frozen=True dataclass. Pydantic v2 BaseModel instances are mutable by default. If any code mutates delta.delta_sbi after ContrastReport construction, contrast_report.most_drifted_speaker becomes stale.

**Proposed Resolution:** Remove the duplicated fields from ContrastReport and expose them as properties that delegate to delta:

```python
class ContrastReport(BaseModel):
    delta: AnalysisDelta = Field(..., description="Complete delta analysis")
    narrative_summary: str = Field(default="", ...)
    ...
    # REMOVE: most_drifted_speaker, most_drifted_dimension as stored fields

    @property
    def most_drifted_speaker(self) -> str | None:
        return self.delta.most_drifted_speaker

    @property
    def most_drifted_dimension(self) -> str:
        return self.delta.most_drifted_dimension
```

Additionally, add model_config = ConfigDict(frozen=True) to AnalysisDelta to prevent post-construction mutation.

**Impact Assessment:** With mutable AnalysisDelta and duplicated fields, any code that modifies the delta after building the report introduces silent data inconsistency between delta.* computed properties and contrast_report.* stored fields.

---

### FINDING-014

**Classification:** MAJOR
**Location:** application/use_cases/compare_sessions.py → __init__ → bilateral_repository 
**Root Cause:** bilateral_repository is accepted as a constructor parameter and stored as self._bilateral_repo, but is never referenced in any method. BilateralSentiment fields (affinity_score, avg_sentiment) are documented in Section 1.1 as analysis outputs but are absent from AnalysisDelta. The original report lists BilateralSentiment under section 1.1 outputs but provides no delta fields for it in AnalysisDelta.

**Decision Required (one of two resolutions):**

Option A — Intentional omission: Remove bilateral_repository from the constructor. Document that bilateral sentiment delta is deferred. Remove BilateralSentimentRepository import from the endpoint.

Option B — Add bilateral delta support:
```python
# AnalysisDelta — add fields
delta_affinity: dict[tuple[str, str], float] = Field(
    default_factory=dict,
    description="(from_country, to_country) -> Δaffinity_score"
)
delta_affinity_significant: dict[tuple[str, str], bool] = Field(
    default_factory=dict,
    description="(from_country, to_country) -> whether affinity delta exceeds threshold"
)

# CompareSessionsInput — add parameter
affinity_threshold: float = 0.10
```

**Impact Assessment:** Dead constructor parameter with no behavior. If Option A is not chosen, the bilateral sentiment dimension is silently excluded from comparisons without any indication to the caller.

---

### FINDING-015

**Classification:** MAJOR
**Location:** application/use_cases/compare_sessions.py → _calculate_delta → epsilon normalization
**Root Cause:** The normalization formula delta / (abs(value_a) + 1e-6) produces unbounded results when abs(value_a) is small but non-zero. For sbi_a = 0.001, sbi_b = 0.151, the raw delta is 0.150 but the normalized value is 0.150 / (0.001 + 1e-6) ≈ 149.85. Against a threshold of 0.15, this always flags as significant, even if the absolute change is within the metric's noise floor. This produces precision degradation in the significance detection system, directly threatening the ≥ 0.85 precision acceptance criterion.

**Proposed Resolution:** Apply a minimum floor based on each metric's practical scale. This must be calibrated against the actual distribution of metric values in production data, but the following starting values are derived from the metric definitions:

```python
# SBI is bounded by the Wordfish theta range (typically [-3, 3])
SBI_SCALE_FLOOR = 0.10
# DKI is a kinetic index, empirically expected to range roughly [0, 2]
DKI_SCALE_FLOOR = 0.10
# Hedging rate is a proportion [0, 1]
HEDGING_SCALE_FLOOR = 0.05

def _normalize_delta(
    delta: float, baseline: float, scale_floor: float
) -> float:
    """Normalize delta relative to baseline, with a minimum denominator floor."""
    return delta / max(abs(baseline), scale_floor)
```

Update all normalization calls:
```python
# SBI
normalized = _normalize_delta(delta, pos_a.sbi, SBI_SCALE_FLOOR)
# DKI
normalized = _normalize_delta(delta, res_a.dki_score, DKI_SCALE_FLOOR)
# Hedging
normalized = _normalize_delta(delta, rate_a, HEDGING_SCALE_FLOOR)
# Risk — [0, 1] scale
normalized = _normalize_delta(delta, risk_a, 0.05)
```

The scale_floor values MUST be validated against real session data before production deployment. These are initial estimates.

**Impact Assessment:** Near-zero baseline values cause false positives in significance detection, reducing precision below the 0.85 acceptance criterion. The normalization-based approach to significance is only valid when baselines are meaningfully bounded away from zero.

---

### FINDING-016

**Classification:** MINOR
**Location:** domain/models/contrast_report.py → report_id field
**Root Cause:** report_id is declared with default="". An empty string is not a valid unique identifier. The field description states "Unique identifier for this contrast report," which is contradicted by an empty-string default.

**Proposed Resolution:**
```python
import uuid

class ContrastReport(BaseModel):
    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this contrast report"
    )
```

**Impact Assessment:** If report_id is used as a database key or cache key, two reports with report_id="" are indistinguishable. Low severity only because ContrastReport is not currently persisted.

---

### FINDING-017

**Classification:** MINOR
**Location:** domain/models/contrast_report.py → narrative_summary field
**Root Cause:** narrative_summary is declared as a required field (... as default). In execute(), when include_narrative=False or LLM fails, narrative_summary is set to "". An empty string does not distinguish "narrative was not requested" from "narrative generation failed." Required fields with empty-string sentinels are an API design smell.

**Proposed Resolution:**
```python
narrative_summary: str | None = Field(
    default=None,
    description="LLM-generated narrative. None if not requested or generation failed."
)
narrative_summary_skipped: bool = Field(
    default=False,
    description="True if include_narrative=False"
)
narrative_summary_failed: bool = Field(
    default=False,
    description="True if narrative was requested but LLM generation failed"
)
```

**Impact Assessment:** Consumers cannot distinguish "narrative not requested" from "narrative failed" from "narrative is empty because no changes were detected," making error-handling logic in downstream consumers ambiguous.

---

### FINDING-018

**Classification:** MINOR
**Location:** interfaces/api/schemas.py → CompareSessionsRequest → @model_validator 
**Root Cause:** Pydantic v2 @model_validator requires an explicit mode argument (mode='before' or mode='after'). Without mode=, this is invalid syntax in Pydantic v2 and raises TypeError at class definition time.

**Current Code:**
```python
@model_validator
def validate_sessions_different(cls, v):
    if v.session_a_id == v.session_b_id:
        raise ValueError("Session A and Session B must be different")
    return v
```

**Proposed Resolution:**
```python
from pydantic import model_validator

class CompareSessionsRequest(BaseModel):
    ...

    @model_validator(mode="after")
    def validate_sessions_different(self) -> "CompareSessionsRequest":
        if self.session_a_id == self.session_b_id:
            raise ValueError("session_a_id and session_b_id must be different")
        return self
```

In mode='after', the validator receives the fully-constructed model instance as self, not cls, v.

**Impact Assessment:** CompareSessionsRequest fails to define at module load time. All imports of compare.py raise TypeError.

---

### FINDING-019

**Classification:** MINOR
**Location:** interfaces/api/schemas.py → AnalysisDeltaResponse, CompareSessionsResponse 
**Root Cause:** speakers_in_a, speakers_in_b, common_speakers, speakers_only_in_a, speakers_only_in_b are declared as set[str]. JSON does not have a set type. FastAPI serializes Python set as a JSON array, but set iteration order is non-deterministic in CPython (hash-randomization is enabled by default). For a machine-parsing consumer, non-deterministic field ordering creates spurious diffs between identical logical responses.

**Proposed Resolution:** Declare these fields as list[str] in the response schema and sort them at serialization time:

```python
# AnalysisDeltaResponse
speakers_in_a: list[str]
speakers_in_b: list[str]
common_speakers: list[str]
speakers_only_in_a: list[str]
speakers_only_in_b: list[str]

# In endpoint, when constructing AnalysisDeltaResponse:
speakers_in_a=sorted(output.analysis_delta.speakers_in_a),
speakers_in_b=sorted(output.analysis_delta.speakers_in_b),
...
```

**Impact Assessment:** Non-deterministic JSON responses from semantically identical requests. Any consumer that hashes or diffs response bodies will produce false positives.

---

### FINDING-020

**Classification:** MINOR
**Location:** application/use_cases/compare_sessions.py → _assess_risk 
**Root Cause:** The threshold 5 in if delta.total_significant_changes > 5: return "MODERATE_CONCERN" is hardcoded and not exposed via Settings or CompareSessionsInput. This value is arbitrary and untested. The return values "HIGH_RISK_ESCALATION", "RISK_DEESCALATION", "MODERATE_CONCERN", "STABLE" are untyped strings, not a controlled enum, making downstream pattern-matching brittle.

**Proposed Resolution:**
```python
# domain/models/analysis_delta.py — add enum
from enum import Enum

class RiskAssessmentLevel(str, Enum):
    HIGH_RISK_ESCALATION = "HIGH_RISK_ESCALATION"
    RISK_DEESCALATION = "RISK_DEESCALATION"
    MODERATE_CONCERN = "MODERATE_CONCERN"
    STABLE = "STABLE"

# config/settings.py — add
COMPARISON_MODERATE_CONCERN_CHANGE_THRESHOLD: int = 5

# CompareSessionsUseCase._assess_risk
def _assess_risk(self, delta: AnalysisDelta) -> RiskAssessmentLevel:
    if delta.delta_risk_significant:
        if delta.delta_risk and delta.delta_risk > 0:
            return RiskAssessmentLevel.HIGH_RISK_ESCALATION
        return RiskAssessmentLevel.RISK_DEESCALATION
    if delta.total_significant_changes > settings.COMPARISON_MODERATE_CONCERN_CHANGE_THRESHOLD:
        return RiskAssessmentLevel.MODERATE_CONCERN
    return RiskAssessmentLevel.STABLE
```

**Impact Assessment:** Hardcoded threshold cannot be tuned without code changes. Untyped string return values cause runtime failures in any code that uses strict equality or match on the return value if the string changes.

---

### FINDING-021

**Classification:** MINOR
**Location:** application/use_cases/compare_sessions.py → AnalysisDelta.most_drifted_speaker (computed property)
**Root Cause:** The drift score for a speaker is computed as:
```python
score += abs(self.delta_sbi_normalized.get(speaker, 0.0))
score += abs(self.delta_dki_normalized.get(speaker, 0.0))
score += abs(self.delta_hedging_normalized.get(speaker, 0.0))
```
Speech act change magnitude (SpeechActDistributionDelta.change_magnitude) is excluded. A speaker who maintained identical SBI/DKI/hedging but shifted entirely from assertive to cooperative speech acts would score 0.0 and would never be identified as the most drifted speaker, despite a potentially significant behavioral change.

**Proposed Resolution:**
```python
@property
def most_drifted_speaker(self) -> str | None:
    if not self.common_speakers:
        return None
    drift_scores: dict[str, float] = {}
    for speaker in self.common_speakers:
        score = 0.0
        score += abs(self.delta_sbi_normalized.get(speaker, 0.0))
        score += abs(self.delta_dki_normalized.get(speaker, 0.0))
        score += abs(self.delta_hedging_normalized.get(speaker, 0.0))
        if speaker in self.delta_speech_act:
            score += self.delta_speech_act[speaker].change_magnitude
        drift_scores[speaker] = score
    return max(drift_scores, key=drift_scores.get) if drift_scores else None
```

**Impact Assessment:** most_drifted_speaker under-detects speech-act-dominant drifts. For diplomatic analysis, speech act shifts (e.g., from cooperative to assertive) are high-signal behavioral changes that should contribute to the drift score.

---

### FINDING-022

**Classification:** MINOR
**Location:** application/use_cases/compare_sessions.py → significant_changes: list[str] 
**Root Cause:** Entries in significant_changes are human-readable formatted strings (e.g., "SBI: speaker1 (0.200, normalized: 0.250)"). Machine parsing of this field requires string tokenization and pattern matching, which is fragile. The field is described as list[str] but should be structured data for programmatic consumption.

**Proposed Resolution:**
```python
# domain/models/analysis_delta.py — new dataclass
@dataclass(frozen=True)
class SignificantChange:
    dimension: str          # "SBI" | "DKI" | "Risk" | "Hedging" | "SpeakerExit" | "SpeakerEntry"
    speaker_id: str | None  # None for aggregate dimensions
    raw_delta: float | None
    normalized_delta: float | None

# AnalysisDelta
significant_changes: list[SignificantChange] = Field(default_factory=list)
```

Update significant_changes population in _calculate_delta to construct SignificantChange objects. Retain a significant_changes_text: list[str] field for human-readable summaries if the LLM prompt requires it.

**Impact Assessment:** Current string-based field is unusable by any structured consumer without fragile string parsing.

---

### FINDING-023

**Classification:** MINOR
**Location:** Section 5.2 (Performance Optimization) → SessionAggregate ORM model
**Root Cause:** avg_hedging_rate is declared as Mapped[dict[str, float]] = mapped_column(JSON) but the Mapped[dict[str, float]] type annotation on a mapped_column(JSON) requires SQLAlchemy 2.0's JSON type and proper type mapping. The column declaration is correct, but the calculated_at field uses Mapped[datetime] = mapped_column(DateTime) without timezone=True, which stores naive datetimes. All other timestamp fields in this codebase use timezone=True.

**Proposed Resolution:**
```python
class SessionAggregate(Base):
    __tablename__ = "session_aggregates"
    __table_args__ = (
        Index("ix_session_aggregates_session_id", "session_id"),
    )

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    avg_risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    avg_hedging_rate: Mapped[dict[str, float]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

**Impact Assessment:** timezone=True omission stores naive datetimes. Comparison with timezone-aware datetimes elsewhere raises TypeError in Python.

---

## SECTION 3 — CORRECTED IMPLEMENTATION SPECIFICATIONS

### 3.1 Domain Models (Corrected)

**domain/models/analysis_delta.py — complete corrected specification:**

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskAssessmentLevel(str, Enum):
    HIGH_RISK_ESCALATION = "HIGH_RISK_ESCALATION"
    RISK_DEESCALATION = "RISK_DEESCALATION"
    MODERATE_CONCERN = "MODERATE_CONCERN"
    STABLE = "STABLE"


@dataclass(frozen=True)
class SignificantChange:
    dimension: str
    speaker_id: str | None
    raw_delta: float | None
    normalized_delta: float | None


@dataclass(frozen=True)
class MetricDelta:
    metric_name: str
    value_a: float | None
    value_b: float | None
    delta: float | None
    delta_normalized: float | None
    is_significant: bool
    threshold: float


@dataclass(frozen=True)
class SpeechActDistributionDelta:
    speaker_id: str
    distribution_a: dict[str, float]
    distribution_b: dict[str, float]
    delta_distribution: dict[str, float]
    most_changed_type: str | None  # key with max abs(delta_distribution[k])
    change_magnitude: float        # abs(delta_distribution[most_changed_type])


@dataclass(frozen=True)
class NarrativeLayerDelta:
    speaker_id: str
    layer_weights_a: dict[str, float]
    layer_weights_b: dict[str, float]
    delta_weights: dict[str, float]
    dominant_layer_change: tuple[str, float] | None  # (layer, delta), signed


class AnalysisDelta(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_a_id: str = Field(...)
    session_b_id: str = Field(...)
    comparison_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    delta_sbi: dict[str, float] = Field(default_factory=dict)
    delta_sbi_normalized: dict[str, float] = Field(default_factory=dict)
    delta_sbi_significant: dict[str, bool] = Field(default_factory=dict)

    delta_dki: dict[str, float] = Field(default_factory=dict)
    delta_dki_normalized: dict[str, float] = Field(default_factory=dict)
    delta_dki_significant: dict[str, bool] = Field(default_factory=dict)

    delta_risk: float | None = Field(default=None)
    delta_risk_normalized: float | None = Field(default=None)
    delta_risk_significant: bool = Field(default=False)

    delta_hedging: dict[str, float] = Field(default_factory=dict)
    delta_hedging_normalized: dict[str, float] = Field(default_factory=dict)
    delta_hedging_significant: dict[str, bool] = Field(default_factory=dict)

    delta_speech_act: dict[str, SpeechActDistributionDelta] = Field(default_factory=dict)
    delta_narrative: dict[str, NarrativeLayerDelta] = Field(default_factory=dict)

    significant_changes: list[SignificantChange] = Field(default_factory=list)

    speakers_in_a: frozenset[str] = Field(default_factory=frozenset)
    speakers_in_b: frozenset[str] = Field(default_factory=frozenset)
    common_speakers: frozenset[str] = Field(default_factory=frozenset)
    speakers_only_in_a: frozenset[str] = Field(default_factory=frozenset)
    speakers_only_in_b: frozenset[str] = Field(default_factory=frozenset)

    @property
    def most_drifted_speaker(self) -> str | None:
        if not self.common_speakers:
            return None
        drift_scores: dict[str, float] = {}
        for speaker in self.common_speakers:
            score = 0.0
            score += abs(self.delta_sbi_normalized.get(speaker, 0.0))
            score += abs(self.delta_dki_normalized.get(speaker, 0.0))
            score += abs(self.delta_hedging_normalized.get(speaker, 0.0))
            if speaker in self.delta_speech_act:
                score += self.delta_speech_act[speaker].change_magnitude
            drift_scores[speaker] = score
        return max(drift_scores, key=drift_scores.get) if drift_scores else None

    @property
    def most_drifted_dimension(self) -> str:
        dimension_drifts = {
            "SBI": sum(abs(v) for v in self.delta_sbi_normalized.values()),
            "DKI": sum(abs(v) for v in self.delta_dki_normalized.values()),
            "Risk": abs(self.delta_risk_normalized or 0.0),
            "Hedging": sum(abs(v) for v in self.delta_hedging_normalized.values()),
            "SpeechAct": sum(
                d.change_magnitude for d in self.delta_speech_act.values()
            ),
        }
        return max(dimension_drifts, key=dimension_drifts.get)

    @property
    def total_significant_changes(self) -> int:
        return len(self.significant_changes)
```

**domain/models/contrast_report.py — complete corrected specification:**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.domain.models.analysis_delta import AnalysisDelta, RiskAssessmentLevel


class ContrastReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    delta: AnalysisDelta = Field(...)

    narrative_summary: str | None = Field(
        default=None,
        description="LLM-generated narrative. None if not requested or generation failed."
    )
    narrative_summary_skipped: bool = Field(default=False)
    narrative_summary_failed: bool = Field(default=False)
    narrative_summary_model: str = Field(default="")
    narrative_summary_timestamp: datetime | None = Field(default=None)

    # Delegates to delta — no stored duplication
    @property
    def most_drifted_speaker(self) -> str | None:
        return self.delta.most_drifted_speaker

    @property
    def most_drifted_dimension(self) -> str:
        return self.delta.most_drifted_dimension

    key_insights: list[str] = Field(default_factory=list)
    risk_assessment: RiskAssessmentLevel | None = Field(default=None)
    risk_level_changed: bool = Field(default=False)
    recommendation: str | None = Field(default=None)

    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this contrast report"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
```

### 3.2 Use Case — Corrected execute() Skeleton

```python
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from bb_paxdata.domain.models.analysis_delta import (
    AnalysisDelta, SignificantChange, SpeechActDistributionDelta, NarrativeLayerDelta,
)
from bb_paxdata.domain.models.contrast_report import ContrastReport

if TYPE_CHECKING:
    from bb_paxdata.application.protocols import LLMServiceProtocol
    from bb_paxdata.domain.models.analysis import Analysis

logger = structlog.get_logger(__name__)

# Normalization scale floors — calibrate against production data before release
_SBI_SCALE_FLOOR = 0.10
_DKI_SCALE_FLOOR = 0.10
_HEDGING_SCALE_FLOOR = 0.05
_RISK_SCALE_FLOOR = 0.05


def _normalize(delta: float, baseline: float, floor: float) -> float:
    return delta / max(abs(baseline), floor)


@dataclass(frozen=True)
class CompareSessionsInput:
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
    success: bool
    contrast_report: ContrastReport | None = None
    analysis_delta: AnalysisDelta | None = None
    errors: tuple[str, ...] = ()        # soft/non-fatal
    fatal_errors: tuple[str, ...] = ()  # hard failures

    @property
    def succeeded(self) -> bool:
        return self.success and len(self.fatal_errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.errors) > 0


class CompareSessionsUseCase:

    def __init__(
        self,
        sbi_repository: Any,
        dki_repository: Any,
        analysis_repository: Any,
        bilateral_repository: Any,      # retained for future bilateral delta
        discourse_repository: Any,
        llm_service: LLMServiceProtocol | None = None,
    ) -> None:
        self._sbi_repo = sbi_repository
        self._dki_repo = dki_repository
        self._analysis_repo = analysis_repository
        self._bilateral_repo = bilateral_repository
        self._discourse_repo = discourse_repository
        self._llm_service = llm_service
        self._narrative_cache: dict[tuple[str, str], str] = {}

    async def execute(self, input_data: CompareSessionsInput) -> CompareSessionsOutput:
        session_a, session_b = input_data.session_a_id, input_data.session_b_id
        soft_errors: list[str] = []

        logger.info(
            "compare_sessions.started",
            session_a=session_a, session_b=session_b,
        )

        # Pre-fetch analyses once per session (covers risk, hedging, speech act)
        try:
            analyses_a, analyses_b = await asyncio.gather(
                self._analysis_repo.get_by_session(session_a),
                self._analysis_repo.get_by_session(session_b),
            )
        except Exception as exc:
            return CompareSessionsOutput(
                success=False,
                fatal_errors=(f"Analysis pre-fetch failed: {exc}",),
            )

        # Parallel fetch of all remaining data sources
        fetch_results = await asyncio.gather(
            self._fetch_sbi_data(session_a),
            self._fetch_sbi_data(session_b),
            self._fetch_dki_data(session_a),
            self._fetch_dki_data(session_b),
            self._fetch_narrative_data(session_a),
            self._fetch_narrative_data(session_b),
            return_exceptions=True,
        )

        def _unwrap(result: Any, name: str, default: Any) -> Any:
            if isinstance(result, Exception):
                soft_errors.append(f"{name} fetch failed: {result}")
                return default
            return result

        sbi_a    = _unwrap(fetch_results[0], "SBI(A)",        {})
        sbi_b    = _unwrap(fetch_results[1], "SBI(B)",        {})
        dki_a    = _unwrap(fetch_results[2], "DKI(A)",        {})
        dki_b    = _unwrap(fetch_results[3], "DKI(B)",        {})
        narr_a   = _unwrap(fetch_results[4], "Narrative(A)",  {})
        narr_b   = _unwrap(fetch_results[5], "Narrative(B)",  {})

        # Derive analysis-backed metrics from pre-fetched analyses (no extra queries)
        risk_a    = self._fetch_risk_from_analyses(analyses_a)
        risk_b    = self._fetch_risk_from_analyses(analyses_b)
        hedging_a = self._fetch_hedging_from_analyses(analyses_a)
        hedging_b = self._fetch_hedging_from_analyses(analyses_b)
        speech_a  = self._fetch_speech_act_from_analyses(analyses_a)
        speech_b  = self._fetch_speech_act_from_analyses(analyses_b)

        # Compute delta
        try:
            delta = self._calculate_delta(
                session_a=session_a,
                session_b=session_b,
                sbi_a=sbi_a, sbi_b=sbi_b,
                dki_a=dki_a, dki_b=dki_b,
                risk_a=risk_a, risk_b=risk_b,
                hedging_a=hedging_a, hedging_b=hedging_b,
                speech_act_a=speech_a, speech_act_b=speech_b,
                narrative_a=narr_a, narrative_b=narr_b,
                input_data=input_data,
            )
        except Exception as exc:
            return CompareSessionsOutput(
                success=False,
                fatal_errors=(f"Delta calculation failed: {exc}",),
                errors=tuple(soft_errors),
            )

        # Generate narrative (soft failure — delta is still returned)
        narrative_summary: str | None = None
        narrative_failed = False
        narrative_skipped = not input_data.include_narrative or not self._llm_service
        if not narrative_skipped:
            try:
                narrative_summary = await self._get_cached_narrative(
                    delta, input_data.narrative_language
                )
            except Exception as exc:
                soft_errors.append(f"Narrative generation failed: {exc}")
                narrative_failed = True

        contrast_report = ContrastReport(
            delta=delta,
            narrative_summary=narrative_summary,
            narrative_summary_skipped=narrative_skipped,
            narrative_summary_failed=narrative_failed,
            narrative_summary_model=getattr(self._llm_service, "model_name", "")
            if self._llm_service else "",
            narrative_summary_timestamp=datetime.now(timezone.utc)
            if narrative_summary else None,
            key_insights=self._extract_key_insights(delta),
            risk_assessment=self._assess_risk(delta),
            risk_level_changed=delta.delta_risk_significant,
            recommendation=self._generate_recommendation(delta),
        )

        logger.info(
            "compare_sessions.completed",
            session_a=session_a,
            session_b=session_b,
            significant_changes=delta.total_significant_changes,
            most_drifted_speaker=delta.most_drifted_speaker,
            soft_error_count=len(soft_errors),
        )

        return CompareSessionsOutput(
            success=True,
            contrast_report=contrast_report,
            analysis_delta=delta,
            errors=tuple(soft_errors),
        )
```

### 3.3 Repository Protocol — Corrected

```python
# domain/services/compare_sessions_protocols.py
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from bb_paxdata.domain.models.sbi_models import SpeakerPosition
    from bb_paxdata.domain.models.dki import DKIResult
    from bb_paxdata.domain.models.analysis import Analysis
    from bb_paxdata.domain.models.discourse_flow import DiscourseFlow
    from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment


class ISBIRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[SpeakerPosition]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[SpeakerPosition]: ...
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> SpeakerPosition | None: ...


class IDKIRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[DKIResult]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[DKIResult]: ...
    async def get_by_session_and_speaker(
        self, session_id: str, speaker_id: str
    ) -> DKIResult | None: ...


class IAnalysisRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[Analysis]: ...
    async def get_by_speaker(self, speaker_id: str) -> list[Analysis]: ...


class IDiscourseFlowRepository(Protocol):
    async def get_by_session(self, session_id: str) -> list[DiscourseFlow]: ...


class IBilateralSentimentRepository(Protocol):
    async def get_by_panel(self, panel_id: str) -> list[BilateralSentiment]: ...
```

### 3.4 API Endpoint — Corrected

```python
# interfaces/api/routers/v1/compare.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.session import get_db
from bb_paxdata.interfaces.api.auth import PermissionChecker
from bb_paxdata.interfaces.api.schemas import (
    CompareSessionsRequest,
    CompareSessionsResponse,
)

router = APIRouter(prefix="/compare", tags=["comparison"])

# Authoritative URLs:
#   POST /api/v1/compare/sessions
#   GET  /api/v1/compare/sessions/available


def get_compare_use_case(
    db: AsyncSession = Depends(get_db),
) -> CompareSessionsUseCase:
    from bb_paxdata.infrastructure.db.repositories.sbi_repository import SBIRepository
    from bb_paxdata.infrastructure.db.repositories.dki_repository import DKIRepository
    from bb_paxdata.infrastructure.db.repositories.analysis_repository import AnalysisRepository
    from bb_paxdata.infrastructure.db.repositories.country_repository import (
        BilateralSentimentRepository,
        DiscourseFlowRepository,
    )
    from bb_paxdata.domain.services.ai_analyst import AIAnalyst
    from bb_paxdata.config.settings import settings

    llm_service = AIAnalyst(
        model=settings.COMPARISON_NARRATIVE_MODEL,
        max_tokens=settings.COMPARISON_NARRATIVE_MAX_TOKENS,
    ) if settings.COMPARISON_NARRATIVE_ENABLED else None

    return CompareSessionsUseCase(
        sbi_repository=SBIRepository(db),
        dki_repository=DKIRepository(db),
        analysis_repository=AnalysisRepository(db),
        bilateral_repository=BilateralSentimentRepository(db),
        discourse_repository=DiscourseFlowRepository(db),
        llm_service=llm_service,
    )


@router.post("/sessions", response_model=CompareSessionsResponse)
async def compare_sessions(
    request: CompareSessionsRequest,
    use_case: CompareSessionsUseCase = Depends(get_compare_use_case),
    _has_permission: bool = Depends(PermissionChecker("create_comparison")),
) -> CompareSessionsResponse:
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
            detail={
                "fatal_errors": list(output.fatal_errors),
                "errors": list(output.errors),
            },
        )
    return _build_response(output)


@router.get("/sessions/available")
async def list_available_sessions(
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("view_comparison")),
) -> dict:
    from bb_paxdata.infrastructure.db.repositories.sbi_repository import SBIRepository
    from sqlalchemy import select, func

    sbi_repo = SBIRepository(db)
    stmt = select(func.distinct(sbi_repo.model_class.session_id)).order_by(
        sbi_repo.model_class.session_id
    )
    result = await db.execute(stmt)
    session_ids = [row[0] for row in result.all()]
    return {"session_ids": session_ids}
```

### 3.5 Request Schema — Corrected

```python
# interfaces/api/schemas.py (additive)
from pydantic import BaseModel, Field, model_validator
import re

_LANG_CODE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")  # ISO 639-1 with optional region

class CompareSessionsRequest(BaseModel):
    session_a_id: str = Field(..., min_length=1, max_length=200)
    session_b_id: str = Field(..., min_length=1, max_length=200)
    sbi_threshold: float = Field(0.15, ge=0.0, le=1.0)
    dki_threshold: float = Field(0.15, ge=0.0, le=1.0)
    risk_threshold: float = Field(0.10, ge=0.0, le=1.0)
    hedging_threshold: float = Field(0.10, ge=0.0, le=1.0)
    include_narrative: bool = Field(True)
    narrative_language: str = Field("en", min_length=2, max_length=5)

    @model_validator(mode="after")
    def validate_fields(self) -> "CompareSessionsRequest":
        if self.session_a_id == self.session_b_id:
            raise ValueError("session_a_id and session_b_id must differ")
        if not _LANG_CODE_RE.match(self.narrative_language):
            raise ValueError(
                f"narrative_language must be ISO 639-1 format (e.g. 'en', 'tr', 'fr')"
            )
        return self
```

---

## SECTION 4 — IMPLEMENTATION ROADMAP (CORRECTED)

### Phase 1 — Core Domain Models (1–2 days)

Prerequisites: None.

Tasks:
1. Create domain/models/analysis_delta.py per Section 3.1 corrected spec. Includes SignificantChange, MetricDelta, SpeechActDistributionDelta, NarrativeLayerDelta, AnalysisDelta, RiskAssessmentLevel.
2. Create domain/models/contrast_report.py per Section 3.1. Remove stored most_drifted_speaker/most_drifted_dimension fields; use property delegation.
3. Update domain/models/__init__.py to export new types.
4. Write unit tests: delta arithmetic, normalization with _normalize(), most_drifted_speaker including speech act contribution, total_significant_changes, most_drifted_dimension including SpeechAct dimension.

Acceptance: All unit tests pass. AnalysisDelta and ContrastReport serialize/deserialize via model.model_dump(mode="json") without loss.

### Phase 2 — Repository Layer (1–2 days)

Prerequisites: Phase 1 complete.

Tasks:
1. Create domain/services/compare_sessions_protocols.py per Section 3.3. All Analysis, DiscourseFlow, BilateralSentiment references under TYPE_CHECKING.
2. **ADD to_domain() -> SpeakerPosition to SpeakerPositionTable** (infrastructure/db/sbi_table.py). This is a blocking dependency for SBIRepository.
3. Create infrastructure/db/repositories/sbi_repository.py. Fix get_by_speaker ordering column (confirm computed_at exists or use an alternative sort column).
4. Verify DKIRepository implements IDKIRepository. Add get_by_session if absent.
5. Verify or create AnalysisRepository with get_by_session(session_id: str) -> list[Analysis].
6. Verify DiscourseFlowRepository has get_by_session(session_id: str) -> list[DiscourseFlow]. Add if absent.
7. Write integration tests against test DB for all repository methods.

Acceptance: All repositories implement their protocols (verified via runtime_checkable Protocol or isinstance check in tests). SpeakerPositionTable.to_domain() returns a valid SpeakerPosition.

### Phase 3 — Use Case (2–3 days)

Prerequisites: Phase 2 complete.

Tasks:
1. Create application/use_cases/compare_sessions.py per Section 3.2. Implement execute() with asyncio.gather for parallel fetch, pre-fetched analysis queries, corrected normalization (_normalize() with scale floors), corrected max() calls using abs(), significant_changes as list[SignificantChange], and corrected _build_narrative_prompt (f-string with language).
2. Implement _fetch_narrative_data using DiscourseFlowRepository (FINDING-001 resolution).
3. Implement _get_cached_narrative with dict-based cache (FINDING-006 resolution).
4. Implement _assess_risk returning RiskAssessmentLevel enum (FINDING-020 resolution).
5. Unit tests: mock all repositories, test all delta calculation branches, test narrative caching, test asyncio.gather error propagation, test soft vs. fatal error classification.
6. Integration test: end-to-end with test DB, verify total fetch+compute < 2 seconds with representative data volumes.

Acceptance: Unit tests > 85% coverage. Integration test meets < 2-second P95 constraint. All CRITICAL and MAJOR findings resolved.

### Phase 4 — API Layer (1–2 days)

Prerequisites: Phase 3 complete.

Tasks:
1. Add CompareSessionsRequest with corrected @model_validator(mode="after") and narrative_language ISO 639-1 validation.
2. Update AnalysisDeltaResponse speaker set fields to list[str] (sorted).
3. Create interfaces/api/routers/v1/compare.py per Section 3.4. Include PermissionChecker on both endpoints. Register router in interfaces/api/app.py.
4. Implement get_compare_use_case dependency provider. Remove in-function imports and unparameterized AIAnalyst().
5. API tests: valid requests, invalid requests (same session IDs, invalid language, out-of-range thresholds), LLM failure returns 200 with warnings, fatal delta failure returns 500.

Acceptance: All API tests pass. Endpoints visible in OpenAPI docs. Permission check rejects unauthorized requests with 403.

### Phase 5 — LLM Integration (1 day)

Prerequisites: Phase 4 complete.

Tasks:
1. Confirm LLMServiceProtocol definition in application/protocols.py. Ensure generate(prompt: str, temperature: float, max_tokens: int) -> str is the contract.
2. Confirm AIAnalyst implements LLMServiceProtocol with model_name: str attribute.
3. Verify narrative prompt with {language} f-string expansion produces correct language instruction.
4. Test narrative caching: two identical delta inputs with same language return same narrative without second LLM call.
5. Add COMPARISON_NARRATIVE_MODEL and COMPARISON_NARRATIVE_MAX_TOKENS to Settings.

### Phase 6 — Frontend (3–5 days)

Prerequisites: Phase 4 complete. Backend API endpoints stable.

Implementation notes for the TypeScript client:
- narrative_summary: string | null — handle null for skipped/failed cases
- narrative_summary_failed: boolean — display degradation warning if true
- Speaker set fields arrive as string[] (sorted) — no client-side normalization needed
- risk_assessment arrives as one of: "HIGH_RISK_ESCALATION" | "RISK_DEESCALATION" | "MODERATE_CONCERN" | "STABLE" | null 
- errors: string[] in response body — surface as non-blocking warnings in UI

### Phase 7 — QA and Calibration (2–3 days)

Tasks:
1. Validate _SBI_SCALE_FLOOR, _DKI_SCALE_FLOOR, _HEDGING_SCALE_FLOOR, _RISK_SCALE_FLOOR against real session data distribution. Adjust until significant change precision ≥ 0.85 on labeled pairs.
2. Validate COMPARISON_MODERATE_CONCERN_CHANGE_THRESHOLD (default 5) against labeled risk assessments.
3. Load test POST /api/v1/compare/sessions at 10 RPS for 60 seconds. Verify P95 total response time < 3 seconds (excluding LLM). Verify P95 delta-only time < 2 seconds.
4. LLM-as-judge evaluation: generate 20 narrative summaries from diverse session pairs, score coherence 1–5, verify mean ≥ 4.0.
5. Manual audit of most_changed_type and dominant_layer_change against raw distributions to verify abs() fix in FINDING-002 is correct.

---

## SECTION 5 — CONFIGURATION (COMPLETE)

```python
# config/settings.py — additions to existing Settings class
class Settings(BaseSettings):
    # Significance thresholds
    COMPARISON_SBI_THRESHOLD: float = 0.15
    COMPARISON_DKI_THRESHOLD: float = 0.15
    COMPARISON_RISK_THRESHOLD: float = 0.10
    COMPARISON_HEDGING_THRESHOLD: float = 0.10

    # Normalization scale floors (calibrate before production)
    COMPARISON_SBI_SCALE_FLOOR: float = 0.10
    COMPARISON_DKI_SCALE_FLOOR: float = 0.10
    COMPARISON_HEDGING_SCALE_FLOOR: float = 0.05
    COMPARISON_RISK_SCALE_FLOOR: float = 0.05

    # Risk assessment
    COMPARISON_MODERATE_CONCERN_CHANGE_THRESHOLD: int = 5

    # LLM
    COMPARISON_NARRATIVE_ENABLED: bool = True
    COMPARISON_NARRATIVE_MODEL: str = "gpt-4o-mini"       # dev
    # COMPARISON_NARRATIVE_MODEL: str = "gpt-4o"          # prod
    COMPARISON_NARRATIVE_MAX_TOKENS: int = 1000

    # Cache (in-process dict; replace with Redis for multi-worker)
    COMPARISON_CACHE_ENABLED: bool = True  # controls whether _get_cached_narrative is used
    COMPARISON_CACHE_TTL_SECONDS: int = 3600  # relevant only for Redis-backed cache
```

---

## SECTION 6 — DATABASE MIGRATIONS

**Migration: add indexes for comparison performance**

```python
# alembic/versions/XXXX_add_comparison_indexes.py
def upgrade() -> None:
    # SBI composite index (may already exist — use IF NOT EXISTS equivalent)
    op.create_index(
        "ix_speaker_positions_session_speaker",
        "speaker_positions",
        ["session_id", "speaker_id"],
        unique=True,
        if_not_exists=True,
    )
    # DKI composite index
    op.create_index(
        "ix_dki_results_session_speaker",
        "dki_results",
        ["session_id", "speaker_id"],
        if_not_exists=True,
    )
    # AISentenceAnalysis session index (for analysis pre-fetch)
    op.create_index(
        "ix_ai_sentence_analysis_session",
        "ai_sentence_analysis",
        ["session_id"],
        if_not_exists=True,
    )

def downgrade() -> None:
    op.drop_index("ix_speaker_positions_session_speaker", "speaker_positions")
    op.drop_index("ix_dki_results_session_speaker", "dki_results")
    op.drop_index("ix_ai_sentence_analysis_session", "ai_sentence_analysis")
```

**SessionAggregate table (optional, for performance optimization in Phase 7+):**

```python
def upgrade() -> None:
    op.create_table(
        "session_aggregates",
        sa.Column("session_id", sa.String, primary_key=True),
        sa.Column("avg_risk_score", sa.Float, nullable=True),
        sa.Column("avg_hedging_rate", sa.JSON, nullable=True),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_session_aggregates_session_id", "session_aggregates", ["session_id"])
```

---

## SECTION 7 — MONITORING

```python
# application/metrics.py
from prometheus_client import Counter, Histogram, Gauge

comparison_requests_total = Counter(
    "paxdata_comparison_requests_total",
    "Total comparison requests",
    ["status"],  # "success" | "fatal_error" | "partial_success"
)

comparison_delta_duration_seconds = Histogram(
    "paxdata_comparison_delta_duration_seconds",
    "Delta calculation duration (fetch + compute, excluding LLM)",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0],
)

comparison_llm_duration_seconds = Histogram(
    "paxdata_comparison_llm_duration_seconds",
    "LLM narrative generation duration",
    buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)

comparison_llm_tokens_total = Histogram(
    "paxdata_comparison_llm_tokens_total",
    "LLM token usage per narrative generation",
    buckets=[100, 200, 500, 750, 1000, 1500],
)

comparison_cache_hits_total = Counter(
    "paxdata_comparison_cache_hits_total",
    "Narrative cache hits",
)

comparison_significant_changes = Histogram(
    "paxdata_comparison_significant_changes_per_request",
    "Number of significant changes per comparison",
    buckets=[0, 1, 2, 5, 10, 20, 50],
)
```

Instrument execute() by wrapping the fetch+compute block with comparison_delta_duration_seconds.time() and the LLM call with comparison_llm_duration_seconds.time().

---

## SECTION 8 — ACCEPTANCE CRITERIA (BINDING)

All criteria must pass before this task is marked complete.

**Functional:**
- POST /api/v1/compare/sessions returns 200 with valid ContrastReport for any two valid session IDs in the system.
- AnalysisDelta contains non-empty delta_sbi, delta_dki, delta_hedging for sessions with common speakers.
- delta_narrative is non-empty if DiscourseFlowRepository.get_by_session returns data.
- narrative_summary is a non-empty string when include_narrative=True and LLM service is reachable.
- narrative_summary_failed=True and narrative_summary=None when LLM service is unreachable; response status is still 200.
- Same-session comparison request (session_a_id == session_b_id) returns HTTP 422 with validation error.
- Invalid narrative_language format returns HTTP 422 with validation error.
- Unauthorized request (no permission) returns HTTP 403.

**Non-Functional:**
- P95 delta calculation latency (fetch + compute, measured via comparison_delta_duration_seconds) < 2 seconds.
- P95 total API response latency (including LLM when enabled) < 3 seconds on representative load.
- Significant change detection precision ≥ 0.85 on a labeled evaluation set of ≥ 20 session pairs.
- LLM narrative coherence score ≥ 4/5 (LLM-as-judge on ≥ 20 generated summaries).
- Unit test coverage > 85% for analysis_delta.py, contrast_report.py, compare_sessions.py.
- API success rate (HTTP 2xx for valid requests) > 99% in 10-minute load test at 5 RPS.

**Integration:**
- SBIRepository, DKIRepository, AnalysisRepository, DiscourseFlowRepository each implement their respective protocols (verified by isinstance(repo, IProtocol) in integration tests with runtime_checkable).
- All new endpoints registered in interfaces/api/app.py and visible in /docs (OpenAPI).
- All new Settings fields present in config/settings.py with documented defaults.
- Alembic migration applies cleanly on an empty database and on the current production schema.

---

## SECTION 9 — FINDING INDEX (MACHINE-PARSEABLE SUMMARY)

| ID | Classification | Location | Root Cause Summary |
|---|---|---|---|
| FINDING-001 | CRITICAL | compare_sessions.py::_fetch_narrative_data | Permanent stub returns {} |
| FINDING-002 | CRITICAL | compare_sessions.py::_calculate_delta | max() without abs() for magnitude |
| FINDING-003 | CRITICAL | contrast_report.py::class Config | Pydantic v1 syntax in v2 project |
| FINDING-004 | CRITICAL | compare_sessions.py::execute + endpoint | Soft errors treated as fatal, HTTP 500 on LLM failure |
| FINDING-005 | CRITICAL | compare_sessions.py::_build_narrative_prompt | Unresolved {language} literal in non-f-string |
| FINDING-006 | CRITICAL | compare_sessions.py::_generate_narrative_cached | lru_cache on async def + undefined delta variable |
| FINDING-007 | CRITICAL | compare_sessions_protocols.py::IAnalysisRepository | Analysis not imported, NameError at module load |
| FINDING-008 | MAJOR | compare_sessions.py::execute | Sequential fetches; 3× duplicate analysis queries |
| FINDING-009 | MAJOR | sbi_repository.py::get_by_speaker | computed_at column does not exist on model |
| FINDING-010 | MAJOR | compare.py endpoint | In-function imports, no-arg AIAnalyst(), missing PermissionChecker |
| FINDING-011 | MAJOR | compare.py + Section 9.1 | URL path inconsistency between sections |
| FINDING-012 | MAJOR | compare_sessions.py::_extract_key_insights | Direct dict subscript without .get(), KeyError risk |
| FINDING-013 | MAJOR | contrast_report.py | Stored fields duplicate computed properties; desync on round-trip |
| FINDING-014 | MAJOR | compare_sessions.py::__init__ | bilateral_repository injected but unused; bilateral delta absent |
| FINDING-015 | MAJOR | compare_sessions.py::_calculate_delta | Epsilon normalization unbounded near zero baseline |
| FINDING-016 | MINOR | contrast_report.py::report_id | default="" violates uniqueness guarantee |
| FINDING-017 | MINOR | contrast_report.py::narrative_summary | Required field set to "" sentinel; ambiguous meaning |
| FINDING-018 | MINOR | schemas.py::CompareSessionsRequest | @model_validator missing mode= in Pydantic v2 |
| FINDING-019 | MINOR | schemas.py::AnalysisDeltaResponse | set[str] fields produce non-deterministic JSON |
| FINDING-020 | MINOR | compare_sessions.py::_assess_risk | Hardcoded threshold 5; untyped string return |
| FINDING-021 | MINOR | analysis_delta.py::most_drifted_speaker | Speech act magnitude excluded from drift score |
| FINDING-022 | MINOR | analysis_delta.py::significant_changes | Human-readable strings; not machine-parseable |
| FINDING-023 | MINOR | Section 5.2 SessionAggregate | calculated_at missing timezone=True |