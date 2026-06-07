# TASK-A06 TECHNICAL DEVELOPMENT REPORT — UPGRADED
**Report Version:** 2.0  
**Supersedes:** TASK-A06 Development Report v1.0  
**Commit Baseline:** `8d37ef99`  
**Graph Stats:** 8419 nodes · 15046 edges · 878 communities  

---

## METADATA

**Task Identifier:** TASK-A06  
**Task Name:** Presupposition Mining — Gizli Taahhütlerin Çıkarımı  
**Category:** Academic → Engineering Bridge  
**Difficulty:** L  
**Priority:** P2 (Secondary Critical Path)  
**Theoretical Foundation:** Lewis (1979) Common Ground Theory; Beaver & Geurts (2014) Presupposition Triggers  
**Architecture:** Hybrid Rule-Based + LLM Verification Pipeline  
**Upstream Dependency:** TASK-A01 (SRL enrichment, dependency parse)  
**Downstream Impact:** AIAnalysisResult, BilateralSentiment, PowerIndex, CrossAnomalyService  

---

## PART I — CODEBASE INTEGRATION AUDIT

### FINDING C-01

**Classification:** CRITICAL  
**Location:** `domain/models/presupposition.py` (proposed)  
**Root Cause:** The proposed `Presupposition` and `PresuppositionExtractionResult` are plain Python `dataclass` objects. The entire BB-PAXDATA domain model uses `frozen=True` Pydantic models — confirmed by `BilateralSentimentTable` (58 edges, Community 36), `HumanReview` ("immutable Pydantic yapılarıdır", Community 179), `CalibrationReport` (Community 52), and `AIAnalysisResult` ("Ham dict yerine Pydantic modeli", Community 168). Using a `dataclass` will break Pydantic serialization, schema validation via `DataContractValidator` (Community 5), and any downstream `model_dump()` / `model_validate()` calls.  
**Proposed Resolution:** Replace all `@dataclass` definitions with `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`.

```python
# CURRENT (INCORRECT):
from dataclasses import dataclass

@dataclass
class Presupposition:
    trigger_word: str
    trigger_type: TriggerType
    ...

# CORRECTED:
from pydantic import BaseModel, ConfigDict, field_validator

class Presupposition(BaseModel):
    model_config = ConfigDict(frozen=True)

    trigger_word: str
    trigger_type: TriggerType
    presupposed_content: str
    confidence: float
    segment_id: str
    speaker: str
    timestamp: Optional[float] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    verification_method: Optional[VerificationMethod] = None  # See FINDING C-02
    llm_confidence: Optional[float] = None

    @field_validator("confidence", "llm_confidence", mode="before")
    @classmethod
    def clamp_to_unit_interval(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be in [0.0, 1.0], got {v}")
        return v
```

**Impact Assessment:** Any pipeline run that constructs `Presupposition` as a dataclass and passes it to `AIAnalysisResult.hidden_commitments` will raise a `ValidationError` at runtime. The `DataContractValidator.validate_ai_output()` Pandera check will fail silently or crash depending on schema strictness.

---

### FINDING C-02

**Classification:** CRITICAL  
**Location:** `domain/models/presupposition.py` (proposed), `verification_method` field  
**Root Cause:** `verification_method` is typed `Optional[str]` with inline comments listing valid values `"rule"`, `"llm"`, `"hybrid"`. The codebase defines enums for every categorical state — `AnomalySeverity`, `ReviewStatus`, `ReviewType`, `DkiStance`, `MetricType` (Community 0, 17). Using a raw `str` field bypasses Pydantic enum validation, allows out-of-vocabulary values, and breaks pattern matching in downstream consumers.  
**Proposed Resolution:** Define a `VerificationMethod` enum and use it in the model.

```python
from enum import Enum

class VerificationMethod(str, Enum):
    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"
```

**Impact Assessment:** Without enum typing, downstream code that matches on `verification_method` (e.g., for telemetry grouping or HITL review routing) risks silent key errors.

---

### FINDING C-03

**Classification:** CRITICAL  
**Location:** `domain/models/ai_analysis.py` — `AIAnalysisResult`; `domain/services/pandera_validator.py` — `DataContractValidator`  
**Root Cause:** The report instructs adding `hidden_commitments: list[Presupposition]` to `AIAnalysisResult` without updating the Pandera schema in `DataContractValidator`. The graph confirms `DataContractValidator` validates `AIAnalysisResult` output via `validate_ai_output()` (Community 5: "Validate AI analysis output using Pandera schema"). Adding an unregistered field will cause `validate_ai_output()` to either reject the record or strip the field silently, depending on `strict` mode.  
**Proposed Resolution:** Add `hidden_commitments` to the output schema with appropriate dtype and shape.

```python
# In AISentenceOutputSchema (pandera):
import pandera as pa
from pandera.typing import Series

class AISentenceOutputSchema(pa.DataFrameModel):
    # ... existing fields ...
    hidden_commitment_count: Series[int] = pa.Field(ge=0, nullable=False, default=0)
    hidden_commitment_json: Series[str] = pa.Field(nullable=True)
    # NOTE: Pandera cannot validate nested Pydantic objects inline.
    # Serialize to JSON column; validate count separately.

# In AIAnalysisResult:
class AIAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    # ... existing fields ...
    hidden_commitments: list[Presupposition] = Field(default_factory=list)

    @computed_field
    @property
    def hidden_commitment_count(self) -> int:
        return len(self.hidden_commitments)
```

**Impact Assessment:** Without schema update, the `test eval-sentence` CLI path and the integration QA pipeline (`QualityPipeline`, Community 69) will reject any `AIAnalysisResult` containing `hidden_commitments`.

---

### FINDING C-04

**Classification:** CRITICAL  
**Location:** `domain/services/presupposition_verifier.py` (proposed) — `cached_verification()` and `batch_verify_presuppositions()`; `infrastructure/ai/` — existing `AnthropicClient`, `BatchProcessor`  
**Root Cause:** The report proposes a custom `batch_verify_presuppositions()` using a stub `call_llm()` function, and a `@lru_cache`-based `cached_verification()`. Both ignore existing infrastructure:

1. **`BatchProcessor`** (Community 42) already provides `BatchItem`, `BatchResult`, `BatchStats`, cache-check, and chunk-processing. Reimplementing this is a duplication that diverges from the codebase's operational contract.

2. **`AnthropicClient`** (Community 43) is the project's canonical Anthropic interface. All LLM calls must route through `AIClientFactory.from_settings()` → `AnthropicClient`. The stub `call_llm()` is unresolvable.

3. **`@lru_cache` on `cached_verification()`**: The project has a `CacheBackend` protocol (Community 79) with `RedisCacheBackend` (Community 172) and `InMemoryLRUCache` (Community 144). Additionally, `lru_cache` is thread-safe for CPython but not async-safe. The pipeline is fully async (all repositories use `async/await`, Community 14, 88, 152). A synchronous `lru_cache` in an async service context risks cache stampede under concurrency.

4. **Known critical bug**: There is a confirmed broken JSON prefill logic bug in `AnthropicClient` (referenced in codebase audit; manifests as malformed `assistant` prefill messages). Any verification layer calling `AnthropicClient` directly must account for this until the bug is resolved.

**Proposed Resolution:**

```python
# src/bb_paxdata/domain/services/presupposition_verifier.py

from bb_paxdata.infrastructure.ai.client_factory import AIClientFactory
from bb_paxdata.application.pipeline.batch_processor import BatchProcessor, BatchItem
from bb_paxdata.infrastructure.cache.backend import CacheBackend
from bb_paxdata.domain.registry.prompt_registry import get_prompt_registry

class PresuppositionVerifier:
    """
    LLM-backed verification layer for presupposition candidates.
    Routes through existing AIClientFactory and BatchProcessor infrastructure.
    """

    _PROMPT_KEY = "presupposition_verification_v1"

    def __init__(
        self,
        ai_client_factory: AIClientFactory,
        cache: CacheBackend,
        batch_processor: BatchProcessor,
    ) -> None:
        self._client = ai_client_factory.from_settings()
        self._cache = cache
        self._batch = batch_processor
        self._registry = get_prompt_registry()
        self._prompt_version = self._registry.get(self._PROMPT_KEY)

    async def verify_batch(
        self,
        candidates: list[PresuppositionCandidate],
    ) -> list[PresuppositionCandidate]:
        """
        Verifies candidates via LLM using BatchProcessor.
        Cache key: sha256(trigger_word + trigger_type + segment_hash).
        """
        items = [
            BatchItem(
                id=self._make_cache_key(c),
                payload=c,
            )
            for c in candidates
        ]
        result = await self._batch.process(
            items=items,
            process_fn=self._verify_single,
            cache_fn=self._cache_lookup,
        )
        return [r.output for r in result.successful]

    async def _verify_single(self, candidate: PresuppositionCandidate) -> PresuppositionCandidate:
        # NOTE: Use AnthropicClient.complete() with JSON mode, NOT prefill.
        # Prefill is currently broken (see audit ref). Use responseMimeType pattern
        # or Groq/Gemini backend as fallback if Anthropic prefill is unresolved.
        prompt = self._build_prompt(candidate)
        response = await self._client.complete(
            messages=[{"role": "user", "content": prompt}],
            options=CompletionOptions(json_mode=True),
        )
        return self._parse_response(candidate, response)

    @staticmethod
    def _make_cache_key(c: PresuppositionCandidate) -> str:
        import hashlib
        raw = f"{c.trigger_word}|{c.trigger_type.value}|{c.segment_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

**Impact Assessment:** Without this fix the `call_llm()` stub causes `NameError` at runtime. The `@lru_cache` pattern introduces cache stampede risk and bypasses the Redis-backed production cache. The JSON prefill bug will corrupt LLM responses and produce unparseable output.

---

### FINDING C-05

**Classification:** CRITICAL  
**Location:** `domain/services/presupposition_extractor.py` (proposed) — `extract_presuppositions()` function signature  
**Root Cause:** The function is defined as synchronous: `def extract_presuppositions(...) -> PresuppositionExtractionResult`. The integration point — `CollectStage` / `AnalysisPipeline` — is fully async. `SpacyAdapter.analyze_sentence()` is async (Community 1870). Calling a blocking synchronous function from an async pipeline without `asyncio.to_thread()` will block the event loop for the full parse+verification duration.  
**Proposed Resolution:**

```python
# INCORRECT (blocks event loop):
def extract_presuppositions(
    doc: spacy.tokens.Doc,
    segment_id: str,
    speaker: str,
    ...
) -> PresuppositionExtractionResult:

# CORRECT — async wrapper with thread offload for CPU-bound rule layer:
async def extract_presuppositions(
    doc: spacy.tokens.Doc,
    segment_id: str,
    speaker: str,
    timestamp: Optional[float] = None,
    use_llm_verification: bool = True,
    llm_confidence_threshold: float = 0.85,
) -> PresuppositionExtractionResult:
    import asyncio
    # Rule-based layer is CPU-bound (spaCy token iteration)
    candidates = await asyncio.to_thread(
        _run_rule_layer, doc, segment_id, speaker, timestamp
    )
    if use_llm_verification:
        low_conf = [c for c in candidates if c.confidence < llm_confidence_threshold]
        high_conf = [c for c in candidates if c.confidence >= llm_confidence_threshold]
        verified_low = await verifier.verify_batch(low_conf)
        candidates = high_conf + verified_low
    return _build_result(candidates, ...)
```

**Impact Assessment:** Synchronous blocking in an async pipeline will cause pipeline stage timeouts and degrade throughput to single-threaded sequential execution. Under the 10-concurrent-session target, this collapses to serial processing.

---

### FINDING C-06

**Classification:** CRITICAL  
**Location:** `domain/services/presupposition_extractor.py` — `find_subject()`, `find_object()`, `extract_focus_np()`, `extract_that_clause()`, `extract_action()`, `is_known_entity()`  
**Root Cause:** Six helper functions are called throughout the extraction algorithms but are never defined anywhere in the report or the existing codebase. The graph confirms no nodes matching these names exist in the 8419-node graph. These are undefined symbols that will raise `NameError` at import time.  
**Proposed Resolution:** Define all helpers explicitly. Below are the two most ambiguous:

```python
def find_subject(token: spacy.tokens.Token, doc: spacy.tokens.Doc) -> str:
    """
    Find the nominal subject of a token using nsubj/nsubjpass dependency arcs.
    Falls back to empty string if no subject is found.
    """
    for child in token.children:
        if child.dep_ in ("nsubj", "nsubjpass", "csubj"):
            # Return the full span of the subject NP
            return doc[child.left_edge.i : child.right_edge.i + 1].text
    # Walk up to find a subject attached to a head verb
    if token.head != token and token.head.pos_ == "VERB":
        return find_subject(token.head, doc)
    return ""

def is_known_entity(entity_text: str, doc: spacy.tokens.Doc) -> bool:
    """
    Check if a noun is a named entity recognized by spaCy NER.
    Does NOT call an external entity list — uses the NER spans already
    on the Doc object (populated by SpacyAdapter upstream).
    """
    ent_texts = {ent.text.lower() for ent in doc.ents}
    return entity_text.lower() in ent_texts
```

**Impact Assessment:** All six undefined helpers cause `NameError` on first call. The entire extraction module is non-functional until these are resolved.

---

## PART II — MAJOR FINDINGS

### FINDING M-01

**Classification:** MAJOR  
**Location:** `domain/registry/prompt_registry.py` — `build_default_registry()`; `domain/services/presupposition_verifier.py` (proposed)  
**Root Cause:** The report defines a verification prompt template inline in a docstring but does not register it in `PromptRegistry`. The graph confirms `LLMConceptExtractor` (Community 180) explicitly SHA256-audits every prompt: "Concept extraction prompt'u oluştur. SHA256 Audit: Bu prompt'un versiyonu...". `PromptRegistry` (Community 45, 101) tracks every prompt with `PromptVersion`, `compute_hash()`, and `AcademicRefTrace`. An unregistered prompt cannot be: (a) version-tracked across deployments, (b) audited via `test_academic_ref_trace()`, (c) calibrated against HITL outcomes.  
**Proposed Resolution:**

```python
# In build_default_registry() or presupposition_verifier.py module init:
registry = get_prompt_registry()
registry.register(
    PromptVersion(
        key="presupposition_verification_v1",
        template=PRESUPPOSITION_VERIFICATION_PROMPT_TEMPLATE,
        academic_refs=[
            "Beaver & Geurts (2014) — Presupposition, Stanford Encyclopedia",
            "Lewis (1979) — Scorekeeping in a language game",
        ],
        version="1.0.0",
    )
)
```

**Impact Assessment:** Unregistered prompts cannot be calibrated by `CalibrationService` (Community 581). Cohen's Kappa and macro-F1 HITL metrics will not include presupposition verification quality. Prompt drift between deployments goes undetected.

---

### FINDING M-02

**Classification:** MAJOR  
**Location:** `domain/services/presupposition_extractor.py` — `extract_presuppositions()` placement  
**Root Cause:** The report places the extraction function in `linguistic_helpers.py`. The graph shows `linguistic_helpers.py`-equivalent functions are in Community 58 (`clean_speaker_name_helper`, `normalize_name_for_matching`, `parse_speakers_metadata`) — these are parsing utilities, not domain services. The existing pattern for domain logic is a dedicated service class registered in `ServiceContainer` (Community 13: "Uygulama genelindeki servis bağımlılıklarını yöneten IoC container. Singleton."). Placement in `linguistic_helpers.py` breaks the architectural boundary between infrastructure parsing utilities and domain service logic.  
**Proposed Resolution:** Create `src/bb_paxdata/domain/services/presupposition_service.py` containing `PresuppositionService` registered as a lazy singleton in `ServiceContainer`.

```python
# src/bb_paxdata/domain/services/presupposition_service.py
class PresuppositionService:
    """
    Domain service for presupposition extraction.
    Registered as lazy singleton in ServiceContainer.
    """
    def __init__(
        self,
        verifier: PresuppositionVerifier,
        lexicon: PresuppositionLexicon,
        nlp_manager: SpacyModelManager,
    ) -> None:
        self._verifier = verifier
        self._lexicon = lexicon
        self._nlp_manager = nlp_manager

    async def extract(
        self,
        doc: spacy.tokens.Doc,
        segment_id: str,
        speaker: str,
        timestamp: Optional[float] = None,
        use_llm_verification: bool = True,
        llm_confidence_threshold: float = 0.85,
    ) -> PresuppositionExtractionResult:
        ...

# In ServiceContainer:
@cached_property
def presupposition_service(self) -> PresuppositionService:
    return PresuppositionService(
        verifier=self._make_presupposition_verifier(),
        lexicon=PresuppositionLexicon.load_default(),
        nlp_manager=self.spacy_model_manager,
    )
```

**Impact Assessment:** Functions in `linguistic_helpers.py` are not lazy-loaded, not dependency-injected, and cannot be mocked in tests via `ServiceContainer` overrides. This makes unit testing impossible without direct patching.

---

### FINDING M-03

**Classification:** MAJOR  
**Location:** `domain/services/presupposition_extractor.py` — `extract_factive_presupposition()` and `extract_temporal_presupposition()` — negation handling  
**Root Cause:** The report acknowledges "Negated factives: 'Turkey doesn't know that...' → Presupposition still holds" as an edge case but provides no implementation. The correct behavior requires negation projection: a presupposition triggered by a factive verb survives sentential negation. However, the project has a dedicated `NegationDetector`/`SpacyNegationDetector` (Community 1866/1882) and `NegationCue` is the 8th god node (60 edges). Reimplementing negation detection inside presupposition extraction creates a redundancy and will diverge from the canonical negation logic.  
**Proposed Resolution:** Inject `NegationDetector` into `PresuppositionService` and query it per-token:

```python
def _apply_negation_projection(
    self,
    token: spacy.tokens.Token,
    doc: spacy.tokens.Doc,
    presupposition: PresuppositionCandidate,
) -> PresuppositionCandidate:
    """
    Apply presupposition projection under negation.
    Presuppositions of factive, implicative, and change-of-state verbs
    survive sentential negation. Temporal adverb presuppositions do NOT
    project under all negation scopes (cancellable in "not anymore").
    """
    negation_cues = self._negation_detector.detect_on_doc(doc)
    in_negation_scope = any(
        cue.scope_start <= token.i <= cue.scope_end
        for cue in negation_cues
    )
    if in_negation_scope:
        if presupposition.trigger_type in {
            TriggerType.FACTIVE_VERB,
            TriggerType.IMPLICATIVE_VERB,
            TriggerType.CHANGE_OF_STATE,
        }:
            # Presupposition projects: mark as negation-projected
            return presupposition.model_copy(update={
                "presupposed_content": presupposition.presupposed_content,
                "confidence": presupposition.confidence * 0.95,  # slight downgrade
            })
        elif presupposition.trigger_type == TriggerType.TEMPORAL_ADVERB:
            # "no longer X" cancels the temporal presupposition — filter out
            if token.text.lower() in {"anymore", "no longer"}:
                return None  # sentinel for filtering
    return presupposition
```

**Impact Assessment:** Without negation projection, the extractor will fail to detect presuppositions in the most linguistically significant diplomatic utterances: "Turkey no longer recognizes..." contains a temporal presupposition ("Turkey previously recognized...") that is critical for PowerIndex delta computation.

---

### FINDING M-04

**Classification:** MAJOR  
**Location:** `domain/lexicons/presupposition_triggers.py` (proposed) — `TRIGGER_LEXICON`; `infrastructure/nlp/` — `SpacyModelManager`, `SpacyNegationDetector`  
**Root Cause:** The trigger lexicon covers English only. The graph confirms Turkish diplomatic lexicon support: `DIPLO_LEXICON_TR` (Community 176), `LanguageDetector`/`LanguageRouter` (Community 37: "Turkish-focused and language-agnostic negation detection"), `EncodingNormalizer` (Community 106: supports Arabic, Cyrillic, Turkish diacritics). Diplomatic transcripts processed by BB-PAXDATA include Turkish-language segments. A monolingual trigger lexicon produces zero recall on Turkish-language presuppositions.  
**Proposed Resolution:** Extend `PresuppositionLexicon` with language routing:

```python
class PresuppositionLexicon:
    """
    Language-aware presupposition trigger lexicon.
    Default language: "en". Turkish ("tr") triggers are minimal
    and should be expanded in Phase 1.3.
    """
    _TRIGGERS: dict[str, dict[TriggerType, list[str]]] = {
        "en": {
            TriggerType.FACTIVE_VERB: [
                "know", "realize", "notice", "regret", "forget", "remember",
                "acknowledge", "admit", "recognize", "appreciate",
                "understand", "see", "discover", "find", "observe",
            ],
            TriggerType.IMPLICATIVE_VERB: [
                "manage", "fail", "bother", "hesitate", "deign", "trouble",
                "condescend", "vouchsafe",
            ],
            TriggerType.TEMPORAL_ADVERB: [
                "still", "again", "already", "anymore", "yet",
            ],
            TriggerType.TEMPORAL_MULTIWORD: [
                "no longer",
            ],
            TriggerType.CHANGE_OF_STATE: [
                "stop", "start", "begin", "continue", "resume", "cease",
                "quit", "commence", "halt", "terminate",
            ],
        },
        "tr": {
            TriggerType.FACTIVE_VERB: [
                "biliyor", "fark ediyor", "pişman", "hatırlıyor",
                "kabul ediyor", "anlıyor",
            ],
            TriggerType.TEMPORAL_ADVERB: [
                "hâlâ", "yine", "artık", "zaten",
            ],
            TriggerType.CHANGE_OF_STATE: [
                "durdu", "başladı", "devam ediyor", "sürdürüyor",
            ],
        },
    }

    def get_triggers(
        self,
        language: str = "en",
    ) -> dict[TriggerType, list[str]]:
        return self._TRIGGERS.get(language, self._TRIGGERS["en"])
```

**Impact Assessment:** Without Turkish triggers, all Turkish-language segments return zero presuppositions, producing silent blind spots in `AIAnalysisResult.hidden_commitments` for a significant portion of the corpus.

---

### FINDING M-05

**Classification:** MAJOR  
**Location:** `domain/services/presupposition_extractor.py` — `calculate_base_confidence()` — `TRIGGER_SPECIFICITY` weights  
**Root Cause:** The specificity weights contain an inverted ordering: `"realize": 0.65` is assigned lower specificity than `"know": 0.6` (already a discrepancy — realize > know in the table), then `"acknowledge": 0.85` is correct relative to factive strength. The fundamental problem is that specificity weights are hard-coded floats with no documented derivation methodology. The codebase derives calibration metrics from human reviews via `CalibrationService._cohens_kappa()` (Community 581). Initial weights must be derivable from or correctable by calibration data, not fixed constants.  
**Proposed Resolution:** Replace hard-coded floats with a calibration-loadable configuration:

```python
# In AppSettings (Community 113 — single source of truth pattern):
class PresuppositionConfig(BaseModel):
    trigger_specificity_overrides: dict[str, float] = Field(
        default_factory=lambda: {
            "regret": 0.90,
            "acknowledge": 0.85,
            "fail": 0.82,
            "manage": 0.80,
            "realize": 0.70,  # CORRECTED: realize > know for epistemic commitment
            "still": 0.68,
            "again": 0.65,
            "know": 0.60,
            "start": 0.50,
            "stop": 0.50,
            "continue": 0.55,
        }
    )
    default_specificity: float = 0.50
    llm_confidence_threshold: float = 0.85
    batch_size: int = 20
    cache_ttl_seconds: Optional[int] = None  # See FINDING m-03

# Usage:
specificity = settings.presupposition.trigger_specificity_overrides.get(
    trigger_word.lower(),
    settings.presupposition.default_specificity,
)
```

**Impact Assessment:** Hard-coded inverted weights produce systematically miscalibrated confidence scores for the highest-frequency triggers (`know`, `realize`), increasing false positive rates above the stated ≤0.18 threshold without any feedback mechanism.

---

### FINDING M-06

**Classification:** MAJOR  
**Location:** Section 7.1 — "Per-Segment Extraction: Rule-only < 50ms"; Section 7.3 — "100 segments/second (rule-only)"  
**Root Cause:** The two stated performance targets are mutually contradictory:
- "< 50ms per segment" → upper bound of 20 segments/second
- "100 segments/second" → 10ms per segment

They cannot both be true. Additionally, the `< 50ms` claim is empirically unsubstantiated for the `en_core_web_trf` transformer pipeline (the model confirmed in use by `SRLPipeline`, Community 44, Community 53). Transformer-based spaCy models on CPU have per-sentence latency of 50–200ms depending on sentence length. The rule layer iterates the already-parsed `Doc` (parse is computed upstream by SRL), so the marginal cost is token iteration only, which is O(n) and sub-millisecond for typical diplomatic sentences (20–80 tokens). The 50ms claim is pessimistic for rule-only and the 100 segments/second claim is optimistic and contradicts it.  
**Proposed Resolution:** Revise performance targets based on measured baselines:

```
Rule-only per segment: < 2ms (token iteration on pre-parsed Doc, not re-parsing)
LLM verification per candidate (batched, 20 candidates): 800–2000ms (network-bound)
LLM verification per segment (amortized over batch): 40–100ms
End-to-end pipeline latency increase: < 5% (rule-only), < 20% (with LLM)
Throughput (rule-only, 10 concurrent): > 200 segments/second
Throughput (with LLM, 10 concurrent, batched): > 10 segments/second
```

**Impact Assessment:** Incorrect performance targets in the report propagate to deployment SLAs and monitoring alert thresholds. If alerting is configured around the stated 50ms rule-only threshold, it will fire on correct behavior.

---

### FINDING M-07

**Classification:** MAJOR  
**Location:** Section 2.2 — "BilateralSentiment.commitment_tracking_module"  
**Root Cause:** `BilateralSentimentTable` is `frozen=True` (Community 36: "Model frozen=True olduğu için doğrudan atama exception fırlatmalı"). A frozen Pydantic model cannot have a `commitment_tracking_module` attached to it as a mutable attribute. The report describes the integration as though `BilateralSentimentTable` is a stateful service object. The actual pattern in the codebase is: immutable domain models carry computed fields (`effective_relationship`, `dominant_topic`), and aggregation logic lives in the `AggregationEngine` (Community 86) or use-case layer.  
**Proposed Resolution:** Integrate presupposition impact at the use-case layer:

```python
# In make_aggregate_bilateral_use_case() — Community 94:

async def execute(self, file_id: str) -> None:
    analyses = await self._analysis_repo.get_by_file(file_id)
    for pair, sentiments in self._group_by_dyad(analyses):
        presupposition_delta = self._compute_commitment_asymmetry(
            sentiments,
        )
        updated_bilateral = BilateralSentimentTable(
            **existing_bilateral.model_dump(),
            commitment_asymmetry_score=presupposition_delta,
            hidden_commitment_count=sum(
                len(a.hidden_commitments) for a in analyses
                if a.speaker in pair
            ),
        )
        await self._bilateral_repo.upsert(updated_bilateral)

def _compute_commitment_asymmetry(
    self,
    sentiments: list[AIAnalysisResult],
) -> float:
    """
    Commitment asymmetry: difference in hidden commitment count between
    dyad members, normalized by total commitment count.
    Follows BilateralSentimentTable.from_scores() normalization pattern.
    """
    speaker_a_count = sum(
        len(s.hidden_commitments)
        for s in sentiments if s.speaker == self._actor_a
    )
    speaker_b_count = sum(
        len(s.hidden_commitments)
        for s in sentiments if s.speaker == self._actor_b
    )
    total = speaker_a_count + speaker_b_count
    if total == 0:
        return 0.0
    return (speaker_a_count - speaker_b_count) / total
```

**Impact Assessment:** Any attempt to attach state to a frozen model raises `ValidationError` at runtime. The entire `BilateralSentiment` integration path is blocked until the architectural mismatch is corrected.

---

### FINDING M-08

**Classification:** MAJOR  
**Location:** Section 6.3 — `evaluate_on_gold_standard()` — precision/recall aggregation  
**Root Cause:** The aggregation `precision = sum(tp) / (sum(tp) + sum(fp))` computes micro-averaged precision, not macro-averaged. For a trigger type distribution with rare categories (cleft constructions appear ~3 times per 100 segments vs. temporal adverbs ~15 times), micro-averaging suppresses poor performance on rare types. The system must meet per-trigger-type thresholds, not just aggregate thresholds.  
**Proposed Resolution:**

```python
from collections import defaultdict

def evaluate_on_gold_standard() -> dict[str, dict[str, float]]:
    """
    Returns per-trigger-type and macro-averaged metrics.
    """
    gold_standard = load_gold_standard()
    per_type: dict[TriggerType, dict[str, list]] = defaultdict(
        lambda: {"tp": [], "fp": [], "fn": []}
    )

    for segment in gold_standard:
        doc = nlp(segment.text)
        extracted = extract_presuppositions(doc, segment.id, segment.speaker)
        for trigger_type in TriggerType:
            predicted = [p for p in extracted.presuppositions
                         if p.trigger_type == trigger_type]
            gold = [g for g in segment.gold_presuppositions
                    if g.trigger_type == trigger_type]
            tp, fp, fn = _align_predictions(predicted, gold)
            per_type[trigger_type]["tp"].append(tp)
            per_type[trigger_type]["fp"].append(fp)
            per_type[trigger_type]["fn"].append(fn)

    results = {}
    for trigger_type, counts in per_type.items():
        tp = sum(counts["tp"]); fp = sum(counts["fp"]); fn = sum(counts["fn"])
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        results[trigger_type.value] = {"precision": p, "recall": r, "f1": f1}

    # Macro average
    macro_p = sum(v["precision"] for v in results.values()) / len(results)
    macro_r = sum(v["recall"] for v in results.values()) / len(results)
    results["MACRO"] = {
        "precision": macro_p,
        "recall": macro_r,
        "f1": 2 * macro_p * macro_r / (macro_p + macro_r) if (macro_p + macro_r) > 0 else 0.0,
    }
    return results
```

**Success Criteria (revised):**
- Precision ≥ 0.82 per trigger type (not aggregate)
- Recall ≥ 0.65 per trigger type (not aggregate)
- Macro-F1 ≥ 0.72
- CLEFT_CONSTRUCTION minimum: Precision ≥ 0.75, Recall ≥ 0.50 (rare class allowance)

**Impact Assessment:** Micro-averaged metrics will report passing scores while individual trigger types (particularly CLEFT_CONSTRUCTION and IMPLICATIVE_VERB) fail silently. The HITL calibration system cannot identify which trigger type requires lexicon expansion.

---

## PART III — MINOR FINDINGS

### FINDING m-01

**Classification:** MINOR  
**Location:** Appendix A — "Total: 47 base patterns + morphological variants ≈ 80+ total triggers"  
**Root Cause:** Enumeration yields 15 (factive) + 8 (implicative) + 6 (temporal) + 10 (change-of-state) + 5 (definite NP patterns) + 3 (cleft patterns) = 47 base patterns. The three-item discrepancy ("47 base patterns" vs actual sum of 47) is self-consistent, but the claim "≈ 80+ total triggers" from "47 base patterns + morphological variants" is unverifiable without a defined morphological expansion algorithm. Morphological variants for English factive verbs ("knows", "knew", "knowing", "known") expand each base form by 3–5 variants. 47 × 3 = 141, not "≈ 80". The claim is internally inconsistent.  
**Proposed Resolution:** Replace the approximation with a deterministic count derived from spaCy lemmatization:

```python
# Matching should use token.lemma_ not token.text — this collapses all
# morphological variants automatically and eliminates the need to enumerate them.
# Base form count = 47; runtime match set is implicitly exhaustive via lemmatization.

if token.lemma_.lower() in self._lexicon.get_triggers(language)[trigger_type]:
    # Matches "knew", "knows", "knowing", "known" via lemma "know"
    ...
```

**Impact Assessment:** If the extractor uses `token.text` matching, it will miss inflected forms. Switching to `token.lemma_` eliminates the morphological expansion problem and makes the "47 base forms" count accurate and complete.

---

### FINDING m-02

**Classification:** MINOR  
**Location:** Section 8.1 — `PRESUPPOSITION_LLM_MODEL=claude-sonnet-4` (environment variable)  
**Root Cause:** The codebase uses `AIClientFactory.from_settings()` which reads the backend and model from `AppSettings` (Community 113: "Uygulama ayarları — magic number'ların tek kaynağı (Single Source of Truth)"). Adding a separate `PRESUPPOSITION_LLM_MODEL` env var creates a second source of truth for model selection and may cause the presupposition verifier to use a different model than the rest of the pipeline (e.g., if `AppSettings` is set to use Groq as the primary backend). The correct model string from the codebase's client registry is `claude-sonnet-4-20250514`, not `claude-sonnet-4`.  
**Proposed Resolution:** Remove `PRESUPPOSITION_LLM_MODEL` env var. Route through `AIClientFactory.from_settings()` without override. If a distinct backend is required for verification, add a `presupposition_backend_override: Optional[BackendType]` field to `PresuppositionConfig` under `AppSettings`.

---

### FINDING m-03

**Classification:** MINOR  
**Location:** Section 8.1 — `PRESUPPOSITION_CACHE_TTL=3600`  
**Root Cause:** Presupposition verification results are deterministic: the same `(trigger_word, trigger_type, segment_text)` triple always produces the same verification outcome. A 3600-second (1-hour) TTL wastes cache space by evicting entries that should be permanent within a session. The correct policy is either no TTL (indefinite, with LRU eviction) or a TTL aligned with the session processing window (typically minutes, not hours). The `RedisCacheBackend` (Community 172) notes "SCAN kullan, KEYS kullanma — production'da KEYS bloke eder" — keys should use the `sha256[:16]` prefix defined in `FINDING C-04`.  
**Proposed Resolution:** Set `cache_ttl_seconds: Optional[int] = None` (no TTL) with `max_size` LRU eviction. The `InMemoryLRUCache` (Community 144) handles this natively.

---

### FINDING m-04

**Classification:** MINOR  
**Location:** Section 5.2 — `calculate_base_confidence()` — additive confidence accumulation  
**Root Cause:** The confidence formula adds components: `confidence = 0.5 + specificity * 0.2 + parse_completeness * 0.2 + context * 0.1`. Maximum achievable confidence is `0.5 + 0.2 + 0.2 + 0.1 = 1.0` exactly. In practice, any trigger with `specificity = 0.9` (e.g., `"regret"`) immediately scores `0.5 + 0.18 = 0.68` before parse completeness is checked. The `min(confidence, 1.0)` clamp is never triggered, making it dead code. More importantly, the confidence formula has no documented calibration — it is not derived from inter-annotator agreement data or logistic regression on gold-standard labels.  
**Proposed Resolution:** Document that this formula is an initialization heuristic subject to replacement by calibration data in Phase 4 (Evaluation & Optimization). Add `# TODO(Phase 4): Replace with logistic regression on gold-standard Cohen's κ > 0.7 dataset` inline. The formula is acceptable as a prior but must not be presented as a calibrated confidence model.

---

### FINDING m-05

**Classification:** MINOR  
**Location:** Section 3.2 — Layer 2 batch prompt — `construct_batch_prompt()` and `parse_batch_response()`  
**Root Cause:** Batching multiple presupposition candidates into a single LLM prompt increases input tokens proportionally (20 candidates × ~150 tokens each = ~3000 tokens) but introduces a parsing challenge: the LLM must produce 20 structured responses in a single reply, and `parse_batch_response()` is undefined. If the LLM omits or reorders any item, the batch-to-candidate mapping breaks silently. The project has `JSONRecoveryEngine` (Community 93) with six recovery levels for malformed JSON, but this is not referenced.  
**Proposed Resolution:** Use `BatchProcessor`'s chunked processing with individual JSON-mode calls per candidate where LLM batch response parsing is unreliable. If true batching is required for cost efficiency, enforce a numbered JSON array schema and validate via `JSONRecoveryEngine`:

```python
# Batch prompt produces: [{"id": 0, "answer": "YES", "confidence": 95}, ...]
# Recovery via JSONRecoveryEngine if LLM omits array delimiters:
recovery_engine = JSONRecoveryEngine()
parsed = recovery_engine.recover(raw_response, schema=BATCH_RESPONSE_SCHEMA)
```

---

## PART IV — INFORMATIONAL FINDINGS

### FINDING I-01

**Classification:** INFORMATIONAL  
**Location:** Section 3.3 — `extract_presuppositions()` — "After SRL extraction, before sentiment analysis"  
**Root Cause:** The proposed pipeline ordering is correct. `SRLPipeline` (Community 44) uses a thread-safe singleton with double-checked locking and provides the `Doc` object with dependency parse attached. Presupposition extraction reads the parse without re-parsing. This is the correct reuse pattern.  
**Note:** `SRLPipeline.get_instance()` must be used to acquire the pipeline, not direct `spacy.load()`. The `SpacyModelManager` (Community 155) handles model lifecycle. Do not instantiate spaCy models independently.

---

### FINDING I-02

**Classification:** INFORMATIONAL  
**Location:** Section 3.1 — `Presupposition.span_start`, `span_end` — character offsets  
**Root Cause:** The `SRLSpan` model (Community 48) already defines "Character-level span representation with validation. Invariant: start_char ≤ end_char." The presupposition model should reuse `SRLSpan` for the trigger span to maintain consistency.

```python
from bb_paxdata.domain.models.srl import SRLSpan

class Presupposition(BaseModel):
    model_config = ConfigDict(frozen=True)
    # ...
    trigger_span: Optional[SRLSpan] = None  # replaces span_start + span_end
```

---

### FINDING I-03

**Classification:** INFORMATIONAL  
**Location:** Section 12.2 — "Enhancement 4: Neural Presupposition Detection"  
**Root Cause:** The graph confirms the project already tracks `TASK-X01` (Target-Stance Detection with DeBERTa-v3-base, Community 139) and a fine-tuned model pipeline. The neural enhancement path should reuse the fine-tuning infrastructure from TASK-X01 rather than designing a new training pipeline. The `ModelEvaluationEngine` and `BootstrapSignificanceTester` (Community 182) are already available for model comparison.

---

### FINDING I-04

**Classification:** INFORMATIONAL  
**Location:** Section 2.1 — Pipeline architecture diagram  
**Root Cause:** The `_process_single_file()` function is the 5th god node (87 edges), indicating it is the central dispatch point for the pipeline. Any integration of `PresuppositionService` into the pipeline must be routed through this function (or its stage equivalents in `CollectStage`). The report identifies the call site as "Main analysis pipeline (location TBD)" — it is not TBD. It is `_process_single_file()` in the file processing pipeline.

---

### FINDING I-05

**Classification:** INFORMATIONAL  
**Location:** Section 9.3 — API Documentation — proposed endpoints  
**Root Cause:** The GraphQL API uses `DataLoader` (Community 2: "N+1 problemini çözer") to batch `Analysis → Segment` and `Segment → Sentence` relations. Adding a REST endpoint at `GET /presuppositions/{session_id}` is inconsistent with the existing GraphQL API architecture. The `get_graphql_context()` function creates per-request `DataLoader` instances. Presupposition queries should be exposed via GraphQL resolver, not a separate REST endpoint.

---

## PART V — IMPLEMENTATION SPECIFICATION (CORRECTED)

### 5.1 Revised File Structure

```
src/bb_paxdata/
├── domain/
│   ├── models/
│   │   └── presupposition.py          # Pydantic frozen models (FINDING C-01, C-02)
│   ├── lexicons/
│   │   └── presupposition_triggers.py  # Language-aware lexicon (FINDING M-04)
│   └── services/
│       ├── presupposition_service.py   # Domain service (FINDING M-02)
│       └── presupposition_verifier.py  # LLM verifier via AIClientFactory (FINDING C-04)
tests/
├── unit/
│   ├── test_presupposition_models.py
│   ├── test_presupposition_extractor.py
│   └── test_presupposition_verifier.py
└── integration/
    └── test_presupposition_pipeline.py
```

### 5.2 Corrected Data Models

```python
# src/bb_paxdata/domain/models/presupposition.py

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from bb_paxdata.domain.models.srl import SRLSpan


class TriggerType(str, Enum):
    FACTIVE_VERB = "FACTIVE_VERB"
    IMPLICATIVE_VERB = "IMPLICATIVE_VERB"
    TEMPORAL_ADVERB = "TEMPORAL_ADVERB"
    TEMPORAL_MULTIWORD = "TEMPORAL_MULTIWORD"
    CHANGE_OF_STATE = "CHANGE_OF_STATE"
    DEFINITE_NP = "DEFINITE_NP"
    CLEFT_CONSTRUCTION = "CLEFT_CONSTRUCTION"


class VerificationMethod(str, Enum):
    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"


class Presupposition(BaseModel):
    model_config = ConfigDict(frozen=True)

    trigger_word: str
    trigger_type: TriggerType
    presupposed_content: str
    confidence: float
    segment_id: str
    speaker: str
    timestamp: Optional[float] = None
    trigger_span: Optional[SRLSpan] = None
    verification_method: Optional[VerificationMethod] = None
    llm_confidence: Optional[float] = None

    @field_validator("confidence", "llm_confidence", mode="before")
    @classmethod
    def validate_unit_interval(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Score {v!r} outside [0.0, 1.0]")
        return v


class PresuppositionExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    presuppositions: list[Presupposition] = Field(default_factory=list)
    total_triggers_found: int
    verified_count: int
    false_positive_filtered: int
    processing_time_ms: float
    language_detected: str = "en"
```

### 5.3 ServiceContainer Registration

```python
# In ServiceContainer (src/bb_paxdata/infrastructure/container.py):

@cached_property
def presupposition_service(self) -> "PresuppositionService":
    from bb_paxdata.domain.services.presupposition_service import PresuppositionService
    from bb_paxdata.domain.services.presupposition_verifier import PresuppositionVerifier
    from bb_paxdata.domain.lexicons.presupposition_triggers import PresuppositionLexicon

    verifier = PresuppositionVerifier(
        ai_client_factory=self.ai_client_factory,
        cache=self.cache_backend,
        batch_processor=self.batch_processor,
    )
    return PresuppositionService(
        verifier=verifier,
        lexicon=PresuppositionLexicon.load_default(),
        nlp_manager=self.spacy_model_manager,
        negation_detector=self.negation_detector,
        settings=self.settings.presupposition,
    )
```

### 5.4 AIAnalysisResult Extension

```python
# In src/bb_paxdata/domain/models/ai_analysis.py:
# Add to AIAnalysisResult (existing Pydantic model):

hidden_commitments: list[Presupposition] = Field(
    default_factory=list,
    description=(
        "Presuppositions extracted per Lewis (1979) / Beaver & Geurts (2014). "
        "Populated by PresuppositionService post-TASK-A01 SRL enrichment."
    ),
)

@computed_field
@property
def hidden_commitment_count(self) -> int:
    return len(self.hidden_commitments)

@computed_field
@property
def commitment_by_type(self) -> dict[str, int]:
    result: dict[str, int] = {}
    for p in self.hidden_commitments:
        result[p.trigger_type.value] = result.get(p.trigger_type.value, 0) + 1
    return result
```

---

## PART VI — REVISED SUCCESS CRITERIA

**Per-Type Precision:** ≥ 0.82 for FACTIVE_VERB, IMPLICATIVE_VERB, TEMPORAL_ADVERB, CHANGE_OF_STATE, DEFINITE_NP; ≥ 0.75 for CLEFT_CONSTRUCTION  
**Per-Type Recall:** ≥ 0.65 for all types; ≥ 0.50 for CLEFT_CONSTRUCTION  
**Macro-F1:** ≥ 0.72  
**Inter-annotator agreement (Phase 4):** Cohen's κ ≥ 0.70 (3 annotators, 100 segments)  
**Pipeline latency increase (rule-only):** < 2ms per segment (token iteration on pre-parsed Doc)  
**Pipeline latency increase (with LLM):** < 100ms per segment amortized over batch=20  
**LLM verification success rate:** ≥ 95% (measures BatchProcessor retry + JSONRecoveryEngine recovery)  
**Cache hit rate:** ≥ 40% after warm-up (verification results are permanent, not time-bounded)  
**PromptRegistry registration:** REQUIRED before Phase 2 completion  
**DataContractValidator schema update:** REQUIRED before Phase 3 integration test passes  
**ServiceContainer lazy registration:** REQUIRED before pipeline integration test passes  

---

**Report Version:** 2.0  
**Audit Commit:** `8d37ef99`  
**Graph Basis:** BB-PAXDATA · 8419 nodes · 15046 edges  
**Status:** Supersedes v1.0 — Ready for Implementation Phase 1  
REPORT_EOF
echo "Report written successfully"
wc -l /home/claude/upgraded_report.md