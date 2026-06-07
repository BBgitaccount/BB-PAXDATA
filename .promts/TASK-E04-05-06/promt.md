# ANTIGRAVITY TECHNICAL REVIEW — TASKS E04 · E05 · E06
## BB-PAXDATA · Upgraded Development Report
**Generated:** 2026-06-06 | **Graph Commit:** `8d37ef99` | **Corpus:** 601 files · 586,895 words

---

## SECTION 0 — GRAPH-DERIVED CODEBASE FACTS

**Graph topology (authoritative):**
- Nodes: 10,106 | Edges: 17,198 | Communities: 1,060 (644 shown, 416 thin omitted)
- Extraction ratio: 76% EXTRACTED · 24% INFERRED (avg confidence 0.59)
- Inferred edge count: 4,167 — verify before relying on inferred relationships

**High-betweenness nodes (cross-task blast radius):**
- `Analysis` — betweenness 0.060, bridges 31 communities, 174 INFERRED edges. Any change to this model affects the widest set of downstream consumers. E04 and E05 both touch `Analysis` transitively.
- `_process_single_file()` — betweenness 0.058, bridges 26 communities. The existing processing bottleneck; E04 adds coreference resolution to this hot path.
- `Sentence` — betweenness 0.035, bridges 25 communities, 90 INFERRED edges. E04's event mention detection operates at sentence level.

**Confirmed infrastructure state relevant to E04/E05/E06:**
- SRL pipeline: `SRLModelConfig`, `_acquire_pipeline()`, TTL-based cache (Community 18); `SRLFrame` + PropBank argument type taxonomy confirmed at Community 48.
- NER: spaCy-based entity extraction with Turkish support (Community 22; multilingual encoding at Community 106).
- DiscourseFlow rebuild: `Rebuilds bilateral sentiments, discourse network edges, and discourse flows` (Community 19) — full pipeline re-run, not incremental.
- Redis cache: `RedisCacheBackend` with SCAN-only (no KEYS) production-safe pattern (Community 673). **Not primary storage.**
- ORM/migrations: SQLAlchemy 2.0 async + Alembic SQLite batch mode (Community 838). This is the authoritative persistence pattern.
- PromptRegistry: SHA-256 versioned, academic-reference-tracked prompt management (Communities 45, 101). All LLM calls must register prompts here.
- SpeakerPosition / SBICalculator / ForecastResult (Community 855); Wordfish theta scale confirmed.
- `TimeSlice`, `ForecastResult`, `ChangepointDetector`, `EWMA`, `RiskForecaster` confirmed at Community 109.
- `BilateralHeatmap` frontend component confirmed at Community 95 — E05 heatmap requirement partially satisfiable by extending this component.
- Topic drift detection via Jensen-Shannon divergence (`detect_topic_drift()`, Community 111) — relevant precedent for E05 convergence detection signal smoothing.
- GAT integration state: `GATEmbeddingService`, `GATNetwork`, `GATContrastiveTrainer`, `GATEmbeddingRepository` (Communities 638, 640); **GAP-01 through GAP-06 unresolved** (Community 849).

**Open upstream issues with E04/E05 blast radius:**
- FINDING M-01: PyTorch Geometric dependency broken for CUDA (Communities 1026, 1048) — affects GAT embedding, transitively affects E04 graph integration step.
- FINDING M-03: `recalibrate_weights` epsilon rejects valid IEEE 754 defaults (`_WEIGHT_SUM_EPSILON = 1e-6`; Communities 1025, 1047) — affects SpeakerPosition, transitively affects E05 theta-based distance computation.
- FINDING C-03: `_calculate_anomaly_score()` returns hardcoded constant — GAT anomaly output non-functional (Communities 1000, 1044).
- FINDING I-01: Prior initialization strategy undefined for new vs. returning speakers (Community 880).
- FINDING I-02: No `speaker_id` in `TimeSlice` — Bayesian per-speaker state isolation non-functional (Community 880).
- GAP-02: `DiscourseFlow.actor_ids` / `.concept_ids` attribute verification unresolved (Community 849).
- GAP-05: Concurrent `SpeakerPosition` modification — merge conflict risk (Community 849).
- GAP-06: Edge weight normalization absent from Fischer DNA graph (Community 849).

---

## PART I — TASK-E04: CROSS-DOCUMENT EVENT COREFERENCE

### FINDING E04-C-01 · SRL ARG1 Used as Event Trigger — Semantic Role Mismatch

**Classification:** CRITICAL
**Location:** `domain/services/event_coreference_service.py` (proposed) · task specification, Aşama 1

**Root Cause:**
The specification states: `spaCy NER + SRL ARG1 spans → event candidates` and `Event trigger words: verbs (agree, reject, announce) + nominals (ceasefire, vote, summit)`. In PropBank SRL (confirmed at Community 48: `SRLFrame`, PropBank argument type taxonomy), ARG1 is the patient/theme of the predicate — not the event trigger. The predicate itself (tagged `V` or `PRED`) is the event trigger. The specification conflates two distinct roles:
- Event trigger detection: identifying the predicate (V/PRED span) that names the event
- Event argument extraction: identifying ARG0 (agent) and ARG1 (theme/patient) as event participants

Example parse for "Russia agreed to the ceasefire":
```
V       = "agreed"       ← event trigger
ARG0    = "Russia"       ← agent (participant)
ARG1    = "ceasefire"    ← patient/theme (NOT the event trigger)
```

Using ARG1 spans as event candidates means detecting "ceasefire" as an event candidate, while "agreed" (the actual trigger) is silently discarded. This inverts the detection logic.

**Proposed Resolution:**
Replace ARG1-based detection with predicate-span-based detection, using ARG1 as the event description context slot:

```python
# INCORRECT (as specified):
event_candidates = [span for span in srl_result.arg1_spans]

# CORRECT:
@dataclass
class EventMentionCandidate:
    trigger_span: str          # V/PRED span — the event trigger
    trigger_lemma: str         # lemmatized trigger for cross-document matching
    arg0_span: str | None      # agent (participating actor)
    arg1_span: str | None      # patient/theme (event description context)
    sentence_id: str
    session_id: str
    timestamp: datetime

def extract_event_mentions(
    srl_result: SRLFrame,
    trigger_verb_set: frozenset[str],
    trigger_nominal_set: frozenset[str],
) -> list[EventMentionCandidate]:
    candidates = []
    for frame in srl_result.frames:
        trigger = frame.predicate  # V/PRED span
        if trigger.lemma_ in trigger_verb_set:
            candidates.append(EventMentionCandidate(
                trigger_span=trigger.text,
                trigger_lemma=trigger.lemma_,
                arg0_span=frame.arguments.get("ARG0"),
                arg1_span=frame.arguments.get("ARG1"),  # context, not trigger
                sentence_id=frame.sentence_id,
                session_id=frame.session_id,
                timestamp=frame.timestamp,
            ))
    # Nominal triggers: separate NP chunking pass, not ARG1 pass
    for chunk in doc.noun_chunks:
        if chunk.lemma_ in trigger_nominal_set:
            candidates.append(EventMentionCandidate(
                trigger_span=chunk.text,
                trigger_lemma=chunk.lemma_,
                arg0_span=None,
                arg1_span=None,
                sentence_id=...,
                session_id=...,
                timestamp=...,
            ))
    return candidates
```

**Impact Assessment:**
If left unaddressed, the event mention detection stage produces zero valid event triggers for verb-framed events (the majority of political discourse events). The heuristic coreference layer and LLM verification layer both receive malformed input. ECB+ evaluation would measure recall on wrongly-detected spans — all downstream F1 metrics would be invalid. This is a design-level fault that invalidates the entire E04 pipeline.

---

### FINDING E04-C-02 · CanonicalEvent.event_id — Non-Deterministic ID Generation Strategy Absent

**Classification:** CRITICAL
**Location:** `domain/models/canonical_event.py` (proposed)

**Root Cause:**
The `CanonicalEvent` dataclass specifies `event_id: str` with no generation strategy. In Python dataclasses, uninitialized string fields have no default factory. The implicit assumption is `uuid.uuid4()`, which is non-deterministic. Two pipeline executions on the same corpus produce different `event_id` values for identical canonical events. This makes:
- Idempotent re-runs impossible
- Cross-run event cluster comparison undefined
- Deduplication in the event registry (Redis or DB) based on `event_id` non-functional

**Proposed Resolution:**
Use SHA-256 of a canonical tuple as the deterministic event ID:

```python
import hashlib
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CanonicalEvent:
    # Do NOT use uuid4() — non-deterministic, breaks idempotency
    canonical_description: str
    first_mention: datetime
    event_type: str  # verb lemma or nominal lemma of the trigger

    # Derived fields (post-init)
    event_id: str = field(init=False)
    mention_count: int = field(default=1)
    participating_actors: list[str] = field(default_factory=list)
    related_sessions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Deterministic ID: stable across re-runs for identical events
        fingerprint = (
            f"{self.event_type}|"
            f"{self.canonical_description[:100].lower().strip()}|"
            f"{self.first_mention.date().isoformat()}"
        )
        self.event_id = "EVT_" + hashlib.sha256(
            fingerprint.encode("utf-8")
        ).hexdigest()[:16].upper()
```

The 16-hex-character suffix provides 2^64 collision resistance — sufficient for political transcript event cardinalities.

**Impact Assessment:**
Without deterministic IDs: every `graphify update` run produces orphaned event nodes in the Fischer DNA graph, doubling node count over time. The event registry grows unboundedly without deduplication. The cross-session event cluster metric (`≥ 15 event clusters in 10-session case`) becomes unmeasurable because cluster identities change between runs.

---

### FINDING E04-M-01 · DiscourseFlow Mutation Before GAP-02 Resolution

**Classification:** MAJOR
**Location:** `domain/models/discourse_flow.py` · `domain/models/canonical_event.py` (proposed)

**Root Cause:**
The specification adds `referenced_events: list[CanonicalEvent] = field(default_factory=list)` to `DiscourseFlow`. Community 849 documents GAP-02: `DiscourseFlow.actor_ids` / `.concept_ids` attribute verification is unresolved. This means `DiscourseFlow` already has at least two unverified attribute additions pending validation. Appending a third compound list field (`list[CanonicalEvent]`) before the model's attribute contract is stable creates compounding schema drift. If `DiscourseFlow` is a Pydantic model (FINDING-018 in Community 1015 confirms `model_validator` and `from pydantic import model_validator` are present in the codebase), the mutable list default must use `Field(default_factory=list)` not the dataclass `field(default_factory=list)`.

**Proposed Resolution:**

**Step 1:** Resolve GAP-02 first — add integration test that asserts `DiscourseFlow.actor_ids` and `.concept_ids` are populated and typed correctly before merging any new fields.

**Step 2:** If `DiscourseFlow` is Pydantic:
```python
# INCORRECT (dataclass syntax in Pydantic model):
referenced_events: list[CanonicalEvent] = field(default_factory=list)

# CORRECT (Pydantic v2):
from pydantic import BaseModel, Field

class DiscourseFlow(BaseModel):
    # ... existing fields ...
    referenced_events: list[CanonicalEvent] = Field(default_factory=list)

    model_config = ConfigDict(frozen=False)  # must be mutable to append events
```

**Step 3:** Add Alembic migration for `CanonicalEvent` foreign key reference if `DiscourseFlow` is persisted via ORM (pattern: Community 838 — SQLAlchemy 2.0 async + Alembic).

**Impact Assessment:**
A mutable list with incorrect default syntax in a frozen Pydantic model raises `ValidationError` at instantiation. If `DiscourseFlow` is frozen, `referenced_events` cannot be appended post-construction — the entire event attachment step silently fails or raises. Unresolved GAP-02 means the model's attribute contract is unknown, making schema migration order undefined.

---

### FINDING E04-M-02 · Event Registry Backend Underspecification — Redis TTL Eviction Risk

**Classification:** MAJOR
**Location:** `domain/services/event_coreference_service.py` (proposed) · infrastructure layer

**Root Cause:**
The specification states: "`CanonicalEvent` store (event registry — Redis veya DB tablo)". The existing Redis implementation (Community 673: `RedisCacheBackend`) is a cache, not a primary store. Redis cache entries are subject to TTL eviction and memory pressure eviction (LRU policy). Storing `CanonicalEvent` records in Redis means event registry data can be silently destroyed by cache eviction — especially under the 601-file, 586,895-word corpus load. The specification provides no TTL, no persistence (AOF/RDB) configuration, and no fallback strategy.

**Proposed Resolution:**
Use the confirmed ORM/Alembic infrastructure (Community 838) as the authoritative event registry. Redis is acceptable only as a read-through cache layer, not as the source of truth.

```python
# infrastructure/db/models/canonical_event_table.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, JSON, Integer
import datetime

class CanonicalEventTable(Base):
    __tablename__ = "canonical_events"

    event_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_description: Mapped[str] = mapped_column(String(1024), nullable=False)
    first_mention: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    participating_actors: Mapped[list] = mapped_column(JSON, default=list)
    related_sessions: Mapped[list] = mapped_column(JSON, default=list)

# domain/ports/i_canonical_event_repository.py
from typing import Protocol
class ICanonicalEventRepository(Protocol):
    async def upsert(self, event: CanonicalEvent) -> None: ...
    async def get_by_id(self, event_id: str) -> CanonicalEvent | None: ...
    async def get_all(self) -> list[CanonicalEvent]: ...

# Redis cache wrapper (optional, for read performance only):
class CachedCanonicalEventRepository:
    def __init__(self, db_repo: ICanonicalEventRepository, cache: RedisCacheBackend) -> None:
        self._db = db_repo
        self._cache = cache

    async def get_by_id(self, event_id: str) -> CanonicalEvent | None:
        cached = await self._cache.get(f"event:{event_id}")
        if cached:
            return CanonicalEvent(**json.loads(cached))
        result = await self._db.get_by_id(event_id)
        if result:
            await self._cache.set(f"event:{event_id}", json.dumps(result.__dict__), ttl=3600)
        return result
```

**Impact Assessment:**
If Redis is used as primary store without AOF persistence: all cross-session event clusters are lost on cache restart. The `≥ 15 event clusters` success criterion becomes permanently unmeasurable after any infrastructure restart.

---

### FINDING E04-M-03 · ECB+ Benchmark Domain and Language Mismatch

**Classification:** MAJOR
**Location:** Task specification, Başarı Kriterleri section

**Root Cause:**
The success criterion states: `ECB+ corpus üzerinde CoNLL F1 ≥ 0.72`. The ECB+ corpus (Cybulska & Vossen, 2014) is an English-language news wire corpus annotated for cross-document event coreference. BB-PAXDATA processes:
- Turkish-language political transcripts (confirmed: Community 96 `count_syllables()` with Turkish support; Community 106 `EncodingNormalizer` with Turkish/Arabic/Russian character handling)
- Multilingual diplomatic discourse (Community 37 confirms `LanguageDetector` and `LanguageRouter`)
- Spoken language transcripts — lexically and syntactically different from news wire prose

Reporting ECB+ F1 ≥ 0.72 on a Turkish spoken-language system trained/evaluated without domain adaptation is not a valid transferability claim. The event trigger lexicons (agree, reject, announce; ceasefire, vote, summit) are English-specific and are not applicable to the Turkish segments of the corpus without translation and morphological adaptation.

**Proposed Resolution:**
Replace ECB+ with domain-appropriate evaluation:

```
CORRECTED SUCCESS CRITERIA (E04):
1. Intra-language coreference F1 (English segments): ECB+ subset ≥ 0.65 (lower threshold, domain gap acknowledged)
2. Turkish coreference: Manual annotation of 50 cross-document event pairs from BB-PAXDATA corpus;
   inter-annotator agreement κ ≥ 0.7 before scoring; target F1 ≥ 0.60
3. Cross-session cluster recall: ≥ 15 event clusters recovered from 10-session multilingual case
4. LLM verification false positive rate < 0.10 (unchanged, language-agnostic)
```

**Impact Assessment:**
If ECB+ F1 ≥ 0.72 is retained as the sole criterion: the system will be declared passing based on English news performance while Turkish political transcript coreference is unmeasured and potentially near-zero.

**Status:** RESOLVED - Success criteria corrected above.

---

### FINDING E04-M-04 · LLM Verification Threshold Window Undefined

**Classification:** MAJOR
**Location:** `domain/services/event_coreference_service.py` (proposed), Aşama 2 — Katman 2

**Root Cause:**
The specification states the LLM verification layer is invoked "sadece threshold yakını çiftler için" (only for pairs near the threshold) for cost control. No concrete heuristic score range `[θ_low, θ_high]` is defined. Without a defined window:
- At `θ_low = 0.0`: all pairs invoke LLM → unbounded API cost
- At `θ_low = θ_high`: no pairs invoke LLM → Layer 2 is dead code
- The false positive rate target `< 0.10` cannot be hit without calibrating the invocation window against an annotated development set

The existing PromptRegistry infrastructure (Communities 45, 101, 637) tracks SHA-256 versioned prompts — but no E04 prompt version is registered.

**Proposed Resolution:**

```python
# Concrete threshold window definition
HEURISTIC_SCORE_ACCEPT_THRESHOLD: float = 0.85   # above this → accept without LLM
HEURISTIC_SCORE_REJECT_THRESHOLD: float = 0.30   # below this → reject without LLM
# LLM invoked only for: REJECT_THRESHOLD < score <= ACCEPT_THRESHOLD

async def resolve_pair(
    candidate_a: EventMentionCandidate,
    candidate_b: EventMentionCandidate,
    heuristic_score: float,
    llm_client: AIClientProtocol,
    prompt_registry: PromptRegistry,
) -> tuple[bool, float]:
    if heuristic_score > HEURISTIC_SCORE_ACCEPT_THRESHOLD:
        return True, heuristic_score
    if heuristic_score <= HEURISTIC_SCORE_REJECT_THRESHOLD:
        return False, heuristic_score
    # LLM verification zone: calibrate thresholds against annotated dev set
    prompt = prompt_registry.get("event_coreference_verify@1")
    response = await llm_client.complete(
        prompt.render(event_a=candidate_a, event_b=candidate_b)
    )
    return response.answer == "YES", response.confidence
```

Register the prompt:
```python
# In build_default_registry():
registry.register(
    name="event_coreference_verify",
    version=1,
    text=(
        'Do these two event descriptions refer to the same real-world event?\n'
        'Event A: {event_a_description} (date: {event_a_date}, actors: {event_a_actors})\n'
        'Event B: {event_b_description} (date: {event_b_date}, actors: {event_b_actors})\n'
        'Answer YES or NO with a confidence score between 0.0 and 1.0.\n'
        'Format: {"answer": "YES"|"NO", "confidence": float}'
    ),
    references=["Cybulska & Vossen (2014) ECB+", "Bejan & Harabagiu (2010) NAACL"],
)
```

**Impact Assessment:**
Undefined threshold window makes cost projection impossible. At 601 files × avg document pairs, unbounded LLM invocation cost could reach 10,000+ API calls per corpus run. The `false positive rate < 0.10` criterion is unmeasurable without a defined invocation regime.

---

### FINDING E04-M-05 · String Similarity Without Lemmatization — Turkish Morphology Blind Spot

**Classification:** MAJOR
**Location:** `domain/services/event_coreference_service.py` (proposed), Katman 1 heuristic

**Root Cause:**
The heuristic layer uses string similarity on spans: `"the ceasefire" / "this ceasefire" / "the agreed ceasefire"`. The BB-PAXDATA corpus processes Turkish (agglutinative morphology) and multilingual content. Turkish morphological variants of a single lemma produce dozens of surface forms:
- `ateşkes` (ceasefire), `ateşkese` (to the ceasefire), `ateşkesle` (with the ceasefire), `ateşkesler` (ceasefires), `ateşkesin` (ceasefire's)

Raw string similarity (`Levenshtein`, `SequenceMatcher`) between `ateşkes` and `ateşkese` scores ~0.86 — but between `ateşkes` and `ateşkesler` scores ~0.80. Depending on threshold, morphological variants either all match (too permissive) or some fail (false negatives). Neither raw string nor character n-gram similarity is a reliable cross-form matcher for Turkish.

**Proposed Resolution:**

```python
import spacy
from bb_paxdata.infrastructure.nlp.spacy_model_manager import SpacyModelManager

def normalize_event_span(span_text: str, lang: str, model_manager: SpacyModelManager) -> str:
    """Return lemmatized, lowercased, stopword-stripped span for cross-document matching."""
    nlp = model_manager.get_model(lang)
    doc = nlp(span_text.lower().strip())
    # Use lemma_, not text — critical for Turkish and morphologically rich languages
    tokens = [
        token.lemma_
        for token in doc
        if not token.is_stop and not token.is_punct and len(token.lemma_) > 1
    ]
    return " ".join(tokens)

def string_similarity_score(span_a: str, span_b: str, lang: str, model_manager: SpacyModelManager) -> float:
    norm_a = normalize_event_span(span_a, lang, model_manager)
    norm_b = normalize_event_span(span_b, lang, model_manager)
    if not norm_a or not norm_b:
        return 0.0
    # Jaccard over lemma sets — language-agnostic after lemmatization
    set_a, set_b = set(norm_a.split()), set(norm_b.split())
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
```

**Impact Assessment:**
Without lemmatization: Turkish event mentions fail cross-document matching at a rate proportional to morphological variance. In a 10-session political transcript corpus with consistent actors and recurring events, false negative rate on Turkish segments could exceed 50%, making the `≥ 15 event clusters` success criterion unreachable.

---

### FINDING E04-M-06 · assemble_network.py Integration Before GAP-06 Resolution

**Classification:** MAJOR
**Location:** `assemble_network.py` · task specification step 5

**Root Cause:**
Task step 5: "assemble_network.py'de event node'ları Fischer DNA grafına ekle". Community 849 documents GAP-06: edge weight normalization is absent from the Fischer DNA graph. Adding event nodes with edges to actor nodes before edge weight normalization is resolved means:
- Event-to-actor edges enter the graph with raw, unnormalized weights
- GAT embedding (`GATEmbeddingService`, Community 638) uses edge weights as attention coefficients — unnormalized weights distort attention during training
- The Fischer DNA graph's structural integrity is predicated on normalized edge weights; adding unnormalized event edges corrupts the weight distribution of existing normalized edges

**Proposed Resolution:**
Gate step 5 on GAP-06 resolution. When GAP-06 is resolved, apply the same normalization scheme to event edges:

```python
# In assemble_network.py — after GAP-06 edge normalization is implemented:
def add_event_nodes(
    graph: DiscourseGraph,
    events: list[CanonicalEvent],
    normalization_fn: Callable[[float], float],  # same fn used for existing edges
) -> None:
    for event in events:
        graph.add_node(
            node_id=event.event_id,
            node_type="CANONICAL_EVENT",
            label=event.canonical_description[:80],
            attributes={
                "event_type": event.event_type,
                "first_mention": event.first_mention.isoformat(),
                "mention_count": event.mention_count,
            }
        )
        for actor in event.participating_actors:
            raw_weight = _compute_event_actor_cooccurrence_weight(event, actor)
            graph.add_edge(
                src=event.event_id,
                dst=actor,
                weight=normalization_fn(raw_weight),  # normalized — same fn as existing edges
                edge_type="PARTICIPATES_IN",
            )
```

**Impact Assessment:**
If event nodes are added before GAP-06 resolution: the GAT model's attention coefficients are computed on a corrupted weight distribution. All downstream `GATEmbedding` vectors for existing actors are invalidated. FINDING C-03 (`_calculate_anomaly_score()` returns hardcoded constant) already makes anomaly scoring non-functional — adding a graph integrity problem compounds the GAT subsystem's defects.

---

### FINDING E04-m-01 · ±7 Day Temporal Overlap Window — No Empirical Basis

**Classification:** MINOR
**Location:** Task specification, Katman 1 heuristic

**Root Cause:**
The ±7 day temporal overlap heuristic is stated as a fixed constant with no derivation from the BB-PAXDATA corpus's session timing distribution. If sessions are clustered within 48-hour conference windows, ±7 days is far too permissive (capturing unrelated events). If sessions span months, ±7 days may be too restrictive.

**Proposed Resolution:**

```python
# Calibrate against corpus session timing distribution:
def calibrate_temporal_window(sessions: list[Session]) -> timedelta:
    """Compute ±sigma window from corpus session timestamp distribution."""
    import numpy as np
    timestamps = sorted(s.created_at for s in sessions)
    gaps = [(timestamps[i+1] - timestamps[i]).days for i in range(len(timestamps)-1)]
    if not gaps:
        return timedelta(days=7)  # fallback default
    sigma = np.std(gaps)
    return timedelta(days=max(1, int(sigma)))

# Use result as TEMPORAL_OVERLAP_DAYS constant; log it at startup
```

**Impact Assessment:** Miscalibrated temporal window produces systematic over- or under-clustering. Not a pipeline-breaking fault, but affects the ≥ 15 cluster success criterion's reachability.

---

### FINDING E04-m-02 · TASK-E04 Step 7 — Frontend Scope Bleeds Into TASK-E06

**Classification:** MINOR
**Location:** Task specification, step 7: "Event timeline görselleştirme (frontend)"

**Root Cause:**
Step 7 of TASK-E04 specifies frontend event timeline visualization. TASK-E06 is defined as "[bu slot TASK-E06 için ayrıldı: Event Timeline Visualization]" — the same scope. Step 7 in TASK-E04 is undefined scope within E04 and belongs exclusively to E06.

**Proposed Resolution:**
Remove step 7 from TASK-E04's implementation steps. TASK-E04's backend `CanonicalEvent` registry must expose a read API (`GET /events?session_ids=...`) that TASK-E06 consumes. The API contract must be defined in TASK-E04 so TASK-E06 can implement against it.

**Impact Assessment:** Step 7 removed from TASK-E04 scope. Frontend visualization now properly scoped to TASK-E06.

**Status:** RESOLVED - Step 7 removed from TASK-E04, frontend visualization moved to TASK-E06.

---

## PART II — TASK-E05: CONSENSUS/DIVERGENCE TRACKER

### FINDING E05-C-01 · DBSCAN eps=0.15 Fixed Without Calibration Against Actual Theta Distribution

**Classification:** CRITICAL
**Location:** Task specification, Teknik Yaklaşım — DBSCAN clustering

**Root Cause:**
The specification fixes `DBSCAN(eps=0.15, min_samples=2)`. `SpeakerPosition.theta` is on a Wordfish scale with confirmed range approximately [-3.0, +3.0] (FINDING-015 in Community 1014 documents: "SBI is bounded by the Wordfish theta range (typically [-3,3])" and the codebase contains `# SBI` bounding code). On a 6-unit range, `eps=0.15` represents 2.5% of the total positional range. This creates the following failure modes:

1. **Over-fragmentation (low cohesion panels):** In politically homogeneous multilateral panels where all speakers cluster within 1 unit, eps=0.15 fragments a single true coalition into 5–7 micro-clusters. `CoalitionCluster.stability` scores will be artificially low.

2. **Mega-cluster collapse (high cohesion panels):** In bimodal panels where two factions hold positions ±2.0, eps=0.15 correctly separates factions — but any theta noise within a faction (e.g., [1.85, 2.00, 2.05, 2.15]) creates within-faction splits. DBSCAN with min_samples=2 would mark [1.85] as noise if it is 0.16 from [2.00].

The ±7% success criterion ("Bilinen yakınsama momentlerini ≥ 75% doğrulukla tespit") is computed against expert-labeled convergence events. Without eps calibration against the actual theta IQR, the 75% target has no guaranteed reachability.

**Proposed Resolution:**

```python
from sklearn.cluster import DBSCAN
import numpy as np
from scipy.stats import iqr

def calibrate_dbscan_eps(theta_values: list[float]) -> float:
    """Calibrate DBSCAN eps from corpus theta IQR — corpus-adaptive, not hardcoded."""
    if len(theta_values) < 4:
        return 0.15  # fallback for tiny panels
    theta_iqr = iqr(theta_values)
    # Silverman's rule adapted for positional clustering:
    # eps = 0.5 * IQR gives clusters at natural modal separation
    eps = max(0.10, 0.5 * theta_iqr)
    return round(eps, 3)

def cluster_speaker_positions(
    positions: dict[str, float],  # speaker_id → theta at time t
    min_samples: int = 2,
) -> list[CoalitionCluster]:
    theta_array = np.array(list(positions.values())).reshape(-1, 1)
    eps = calibrate_dbscan_eps(theta_array.flatten().tolist())
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(theta_array)
    # Build CoalitionCluster objects from labels
    clusters = {}
    for (speaker_id, theta), label in zip(positions.items(), labels):
        if label == -1:  # DBSCAN noise point
            continue
        if label not in clusters:
            clusters[label] = {"members": [], "thetas": []}
        clusters[label]["members"].append(speaker_id)
        clusters[label]["thetas"].append(theta)
    return [
        CoalitionCluster(
            cluster_id=f"C{label}",
            members=c["members"],
            centroid_theta=float(np.mean(c["thetas"])),
            stability=0.0,  # computed across sessions separately
            time_range=(t_start, t_end),
        )
        for label, c in clusters.items()
    ]
```

**Impact Assessment:**
Fixed eps=0.15 produces systematically incorrect coalition detection for any corpus with IQR > 0.30 or < 0.10. The `≥ 80% expert agreement on coalition detection` success criterion is unreachable without corpus-adaptive calibration.

---

### FINDING E05-C-02 · Upstream Blocker — FINDING I-02 (No speaker_id in TimeSlice) Renders Confidence Computation Non-Functional

**Classification:** CRITICAL
**Location:** Task specification, Bağımlılıklar → TASK-A07; Community 880 — FINDING I-02

**Root Cause:**
TASK-E05 depends on TASK-A07 (Bayesian Tracker) for credible interval-based confidence control (`ConsensusMoment.confidence`). Community 880 documents FINDING I-02: `TimeSlice` has no `speaker_id` field, meaning the Bayesian tracker (`RiskForecaster`, Community 109) cannot isolate per-speaker state. The Bayesian path produces a single aggregate position posterior, not per-speaker posteriors. Consequently:

- `ConsensusMoment.confidence` derived from speaker-specific credible intervals is undefined
- `convergence_type` classification (`convergence` / `divergence` / `stable`) using `confidence` as a gate produces unreliable output
- The `delta_d` convergence signal has no uncertainty bound — a statistically insignificant theta change at the edge of the credible interval is classified identically to a large definitive shift

**Proposed Resolution:**
Block TASK-E05 on FINDING I-02 resolution. The fix for FINDING I-02 (from Community 880):

```python
# CURRENT (broken — TimeSlice has no speaker_id):
@dataclass
class TimeSlice:
    timestamp: datetime
    theta: float
    risk_level: float

# FIX (from FINDING I-02 resolution):
@dataclass
class TimeSlice:
    timestamp: datetime
    speaker_id: str        # ADD — required for per-speaker state isolation
    theta: float
    risk_level: float
    credible_interval_95: tuple[float, float] | None = None  # from Bayesian posterior

# Then ConsensusMoment.confidence uses per-speaker CI width:
def compute_convergence_confidence(
    speaker_a_slice: TimeSlice,
    speaker_b_slice: TimeSlice,
) -> float:
    """Confidence inversely proportional to CI width — narrow CI = high confidence."""
    if speaker_a_slice.credible_interval_95 is None or speaker_b_slice.credible_interval_95 is None:
        return 0.5  # uninformative prior
    ci_width_a = speaker_a_slice.credible_interval_95[1] - speaker_a_slice.credible_interval_95[0]
    ci_width_b = speaker_b_slice.credible_interval_95[1] - speaker_b_slice.credible_interval_95[0]
    max_possible_width = 6.0  # Wordfish range [-3, +3]
    avg_width = (ci_width_a + ci_width_b) / 2
    return max(0.0, 1.0 - (avg_width / max_possible_width))
```

**Impact Assessment:**
If FINDING I-02 is unresolved: `ConsensusMoment.confidence` is either `None` or `0.5` for all records. The `≥ 75% convergence detection accuracy` metric defaults to random-baseline performance on confidence-gated decisions. TASK-E05 cannot ship with meaningful output while TASK-A07/FINDING I-02 is open.

---

### FINDING E05-M-01 · SRP Violation — aggregate_bilateral_sentiment.py Extension

**Classification:** MAJOR
**Location:** `application/use_cases/aggregate_bilateral_sentiment.py`

**Root Cause:**
The specification extends `aggregate_bilateral_sentiment.py` with pairwise distance matrix computation. Community 19 confirms this function "rebuilds bilateral sentiments, discourse network edges, and discourse flows" — it is a full-pipeline rebuild function with an existing transaction boundary. Adding O(n²) distance matrix computation inside this function:

1. Extends the existing transaction scope to include clustering operations, increasing lock duration on `bilateral_sentiment` and `speaker_position` tables simultaneously
2. Couples bilateral sentiment rebuilding (which operates on raw `Analysis` outputs) with positional tracking (which operates on completed `SpeakerPosition` records) — these have different data freshness requirements and different failure modes
3. Makes partial failure handling non-trivial: a DBSCAN failure would roll back the bilateral sentiment rebuild, losing valid sentiment data

**Proposed Resolution:**
Implement as a separate `ConsensusTrackerUseCase` that is triggered after `aggregate_bilateral_sentiment.py` completes:

```python
# application/use_cases/consensus_tracker_use_case.py
from dataclasses import dataclass
from bb_paxdata.domain.services.consensus_tracker import IConsensusTrackerService
from bb_paxdata.domain.ports.i_speaker_position_repository import ISpeakerPositionRepository

@dataclass(frozen=True)
class ConsensusTrackerInput:
    session_ids: list[str]
    time_window_sessions: int = 3  # rolling window for stability

@dataclass(frozen=True)
class ConsensusTrackerOutput:
    moments: list[ConsensusMoment]
    clusters: list[CoalitionCluster]
    computed_at: datetime

class ConsensusTrackerUseCase:
    def __init__(
        self,
        tracker_service: IConsensusTrackerService,
        position_repo: ISpeakerPositionRepository,
    ) -> None:
        self._tracker = tracker_service
        self._positions = position_repo

    async def execute(self, input_data: ConsensusTrackerInput) -> ConsensusTrackerOutput:
        positions = await self._positions.get_for_sessions(input_data.session_ids)
        moments = self._tracker.detect_convergence(positions)
        clusters = self._tracker.detect_coalitions(positions, input_data.time_window_sessions)
        return ConsensusTrackerOutput(
            moments=moments,
            clusters=clusters,
            computed_at=datetime.utcnow(),
        )
```

Register in DI container (Community 94 pattern: `make_aggregate_bilateral_use_case()` → add `make_consensus_tracker_use_case()`).

**Impact Assessment:**
If the extension approach is retained: any failure in DBSCAN clustering rolls back a full bilateral sentiment rebuild. In production, this means a numerical instability in the clustering step invalidates all sentiment analysis output for a session batch.

---

### FINDING E05-M-02 · CoalitionCluster.stability — Type Ambiguity (float vs int Semantics)

**Classification:** MAJOR
**Location:** `domain/models/consensus_moment.py` (proposed)

**Root Cause:**
The specification declares:
```python
@dataclass
class CoalitionCluster:
    stability: float  # kaç oturumda aynı kaldı
```
The comment "kaç oturumda aynı kaldı" (how many sessions it remained the same) is a count semantic — an integer. However the type is `float`. The conflict produces two possible interpretations, both problematic:

- **Normalized fraction (0.0–1.0):** denominator is undefined (total sessions in window? total sessions in corpus?); value is not derivable without knowing the normalization basis
- **Raw count as float:** `float` for a count semantics is a leaky abstraction; serialization to JSON produces `3.0` instead of `3`, which downstream systems must handle

If `stability` is used in `ConsensusMoment.confidence` computation (e.g., low-stability clusters contribute lower convergence confidence), an undefined range makes the confidence calculation non-deterministic.

**Proposed Resolution:**

```python
@dataclass
class CoalitionCluster:
    cluster_id: str
    members: list[str]
    centroid_theta: float
    time_range: tuple[datetime, datetime]

    # Stability expressed as BOTH raw count and normalized fraction:
    stable_session_count: int        # how many sessions this cluster persisted unchanged
    stability: float                 # = stable_session_count / window_size, range [0.0, 1.0]
    window_size: int                 # denominator for stability — the rolling window size

    def __post_init__(self) -> None:
        if self.window_size <= 0:
            raise ValueError("window_size must be positive")
        object.__setattr__(self, "stability", self.stable_session_count / self.window_size)
```

**Impact Assessment:**
Ambiguous type with undefined range makes the `≥ 80% expert agreement on coalition detection` criterion unverifiable — evaluators cannot determine whether a `stability=0.3` cluster is "stable" or "unstable" without knowing the normalization basis.

---

### FINDING E05-M-03 · ConsensusMoment.panel_range Temporal Semantic Conflicts With SpeakerPosition.theta

**Classification:** MAJOR
**Location:** `domain/models/consensus_moment.py` (proposed)

**Root Cause:**
```python
@dataclass
class ConsensusMoment:
    panel_range: tuple[datetime, datetime]
```
`SpeakerPosition.theta` is a Wordfish ideological position score, not a time-indexed value. The Wordfish model produces a single theta per document/session — it does not produce a time series within a session. `panel_range` implies windowing over time, but the theta values are session-level aggregates. Mapping `panel_range` to session timestamps requires clarification:
- If `panel_range = (session_i.created_at, session_j.created_at)`: this is valid and maps theta snapshots to session timestamps
- If `panel_range` is meant to represent within-session temporal windows: Wordfish theta does not support this granularity; segment-level theta is not produced by the current `SBICalculator`

**Proposed Resolution:**

```python
@dataclass
class ConsensusMoment:
    speakers: list[str]
    topic: str | None
    # CLARIFIED: session_range is indexed by session, not arbitrary datetime window
    session_range: tuple[str, str]          # (session_id_start, session_id_end) — unambiguous
    session_timestamps: tuple[datetime, datetime]  # for display/reporting only
    convergence_type: Literal["convergence", "divergence", "stable"]
    confidence: float                        # from Bayesian CI width (requires FINDING I-02 fix)
    theta_spread: float                      # max(theta) - min(theta) at this moment
    delta_theta_spread: float               # theta_spread(t) - theta_spread(t-1) — signed
```

**Impact Assessment:**
Ambiguous `panel_range` produces inconsistent serialization: if one implementation uses session timestamps and another uses panel start/end datetimes, downstream consumers (frontend heatmap, API) receive inconsistent data. The cross-session event bounding required by TASK-E06 also depends on consistent session identity — `panel_range` inconsistency propagates to the E06 timeline.

---

### FINDING E05-M-04 · delta_d First-Order Difference — No Noise Smoothing

**Classification:** MAJOR
**Location:** `domain/services/consensus_tracker.py` (proposed)

**Root Cause:**
```python
delta_d = d(t) - d(t-1)  # negatif → convergence, pozitif → divergence
```
First-order differencing of pairwise theta distance classifies convergence/divergence on a single-step change. In political discourse analysis, session-to-session theta variation includes noise from:
- Transcript quality (incomplete sessions, speaker attribution errors)
- SRL/NER extraction variance
- Single outlier statements that do not represent genuine positional change

The codebase already implements Jensen-Shannon divergence for topic drift with smoothing (`detect_topic_drift()`, Community 111) and EWMA for time series (Community 109: `EWMA`, `Vectorized EWMA with optional bias correction`). No equivalent smoothing is applied to `delta_d`.

**Proposed Resolution:**

```python
# In domain/services/consensus_tracker.py:
from bb_paxdata.domain.services.risk_forecaster import EWMA  # existing implementation

def classify_convergence(
    distance_series: list[float],
    smoothing_window: int = 3,
    convergence_threshold: float = -0.05,
    divergence_threshold: float = 0.05,
) -> Literal["convergence", "divergence", "stable"]:
    """
    Classify pairwise distance trend with EWMA smoothing.
    Requires at least `smoothing_window` consecutive same-sign deltas for classification.
    """
    if len(distance_series) < 2:
        return "stable"

    ewma_instance = EWMA(alpha=2.0 / (smoothing_window + 1))
    smoothed = ewma_instance.compute(distance_series)

    # Require k consecutive negative deltas before declaring convergence
    k_required = smoothing_window
    deltas = [smoothed[i] - smoothed[i-1] for i in range(1, len(smoothed))]
    recent_deltas = deltas[-k_required:] if len(deltas) >= k_required else deltas

    if all(d < convergence_threshold for d in recent_deltas):
        return "convergence"
    if all(d > divergence_threshold for d in recent_deltas):
        return "divergence"
    return "stable"
```

**Impact Assessment:**
Without smoothing: single-session noise produces systematic false convergence/divergence signals. The `≥ 75% convergence detection accuracy` criterion will fail on any corpus with non-trivial transcript quality variance.

---

### FINDING E05-M-05 · < 5 Second Real-Time Update — Unachievable Without Pre-Computation

**Classification:** MAJOR
**Location:** Task specification, Başarı Kriterleri

**Root Cause:**
The success criterion: "Gerçek zamanlı güncelleme: her yeni session'dan sonra < 5 saniye". The update pipeline for a new session is:

```
DB query (SpeakerPosition for all sessions)
  → pairwise distance matrix O(n²) 
    → DBSCAN clustering 
      → ConsensusMoment + CoalitionCluster persistence 
        → API response 
          → frontend render
```

For n=50 speakers (realistic multilateral panel), the pairwise matrix contains 1,225 pairs. DBSCAN on 1,225 pairs with scikit-learn is O(n² log n) in time. With database I/O latency and API serialization, 5 seconds is achievable only if the computation is incremental (not full recompute) or pre-cached. No caching strategy is specified.

**Proposed Resolution:**

```python
# Celery task: pre-compute on session completion, store result in cache
# (existing Celery task infrastructure confirmed at Community 629: analyze_sentence_task, etc.)

from celery import shared_task
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend

@shared_task(bind=True, max_retries=3, acks_late=True)
async def recompute_consensus_state(self, session_id: str) -> None:
    """Triggered after session analysis completes. Pre-computes coalition state."""
    use_case = make_consensus_tracker_use_case()
    # Fetch only the sessions in the rolling window (not all sessions):
    affected_sessions = await get_sessions_in_window(session_id, window_size=10)
    output = await use_case.execute(ConsensusTrackerInput(session_ids=affected_sessions))
    # Cache pre-computed result with session-keyed invalidation:
    cache = RedisCacheBackend()
    await cache.set(
        key=f"consensus:session:{session_id}",
        value=output.model_dump_json(),
        ttl=3600,
    )

# API endpoint reads from cache — sub-100ms response:
@router.get("/consensus/{session_id}")
async def get_consensus(session_id: str, cache: RedisCacheBackend = Depends(get_cache)):
    cached = await cache.get(f"consensus:session:{session_id}")
    if cached:
        return ConsensusTrackerOutput.model_validate_json(cached)
    # Cache miss: trigger async recompute, return 202 Accepted
    recompute_consensus_state.delay(session_id)
    raise HTTPException(status_code=202, detail="Consensus state is being computed.")
```

**Impact Assessment:**
If implemented as synchronous full recompute on API request: response time for large panels exceeds 5 seconds per the pipeline analysis above. The real-time update criterion is unachievable without the pre-computation architecture described.

---

### FINDING E05-m-01 · scipy.spatial.distance — Dense Matrix for Large n

**Classification:** MINOR
**Location:** `domain/services/consensus_tracker.py` (proposed)

**Root Cause:**
`scipy.spatial.distance.pdist()` returns a condensed distance array; `squareform()` converts to dense n×n matrix. For large multilateral panels (n > 100), the dense matrix consumes O(n²) memory.

**Proposed Resolution:**

```python
from scipy.spatial.distance import pdist
import numpy as np

def compute_pairwise_distances(
    positions: dict[str, float],
) -> tuple[list[str], np.ndarray]:
    """Returns speaker list and condensed distance array (not squareform)."""
    speakers = list(positions.keys())
    thetas = np.array([positions[s] for s in speakers]).reshape(-1, 1)
    condensed = pdist(thetas, metric="cityblock")  # L1 for positional distance
    # DBSCAN accepts precomputed condensed distances — no need for squareform:
    # DBSCAN(metric="precomputed").fit(squareform(condensed))
    # But squareform only needed for display, not for DBSCAN:
    return speakers, condensed
```

**Impact Assessment:** Minor memory inefficiency at current corpus scale (n typically ≤ 50). Becomes relevant at n > 200 speakers in large multilateral UN-style panels.

---

### FINDING E05-m-02 · FINDING I-01 Risk — Undefined Prior for New Speakers Propagates to Convergence

**Classification:** MINOR
**Location:** `domain/services/consensus_tracker.py` (proposed) · TASK-A07 upstream

**Root Cause:**
Community 880 FINDING I-01: prior initialization strategy is undefined for new vs. returning speakers. A new speaker entering session k mid-sequence has an undefined initial theta (Wordfish produces theta only over a full document corpus — a single-session newcomer has no historical anchor). If `SpeakerPosition.theta = None` or `0.0` for new speakers, the pairwise distance computation includes spurious distances to the corpus centroid (0.0), which distorts DBSCAN cluster assignments for all other speakers.

**Proposed Resolution:**

```python
def resolve_speaker_theta(
    speaker_id: str,
    position_map: dict[str, float],
    corpus_mean_theta: float,
) -> float:
    """Return theta for speaker; use corpus mean as uninformative prior for new speakers."""
    if speaker_id not in position_map:
        # New speaker: initialize at corpus mean (uninformative prior)
        # FINDING I-01: this decision must be logged and surfaced to HITL review
        return corpus_mean_theta
    return position_map[speaker_id]
```

**Impact Assessment:** Minor distortion for single new-speaker events. Becomes major if a large bloc of new speakers enters a session simultaneously (e.g., new country delegation joins mid-negotiation).

---

## PART III — TASK-E06: EVENT TIMELINE VISUALIZATION

### FINDING E06-C-01 · Task Specification Is Empty — No Implementable Content

**Classification:** CRITICAL
**Location:** TASK-E06 specification block

**Root Cause:**
The TASK-E06 specification contains only: "[TASK-E04 ile örtüşen bölüm yukarıda — bu slot TASK-E06 için ayrıldı: Event Timeline Visualization]". This is a placeholder comment, not a specification. The following are absent:
- Description (what the visualization communicates)
- Technical approach (data contract, API endpoints consumed, component architecture)
- Implementation steps
- Affected files
- Dependencies (on E04 `CanonicalEvent` registry API)
- Success criteria

TASK-E04 Step 7 references "Event timeline görselleştirme (frontend)" — this is the scope that belongs in E06, but it is only a label in E04 with no technical content.

**Proposed Resolution:**
Backfill TASK-E06 with the following minimum specification:

```
TASK-E06 · Event Timeline Visualization

Category: Engineering | Difficulty: M | Priority: P2
Depends on: TASK-E04 (CanonicalEvent registry API), TASK-E05 (ConsensusMoment timestamps)

Description:
Frontend component that renders cross-session CanonicalEvent instances on a temporal
axis, annotated with ConsensusMoment convergence/divergence classifications and
participating actor labels.

Data contract (consumed from TASK-E04 backend API):
  GET /events?session_ids={comma-separated}
  Response: list[CanonicalEventResponse]

  GET /consensus/{session_id}
  Response: ConsensusTrackerOutput (from TASK-E05)

Frontend component:
  EventTimeline — renders CanonicalEvent items on horizontal time axis
  Inputs:
    events: CanonicalEvent[]
    moments: ConsensusMoment[]
    sessions: Session[]
  Behavior:
    - Group events by event_type (color-coded)
    - Overlay ConsensusMoment annotations (convergence=green, divergence=red, stable=grey)
    - Click on event → show participating actors and related_sessions
    - Filter by actor, event_type, date range

Affected files (new):
  frontend/src/components/EventTimeline.tsx
  frontend/src/hooks/useEventTimeline.ts
  frontend/src/api/events.ts

Affected files (modified):
  frontend/src/App.tsx (route registration)

Success criteria:
  - Renders ≥ 15 event clusters from 10-session case study correctly
  - ConsensusMoment overlays align with ±1 session accuracy to expert-labeled moments
  - Render time < 500ms for ≤ 200 events (browser, Chromium 125+)
  - No event_id collision displayed (deterministic ID from E04-C-02 fix required)
```

**Impact Assessment:**
Without a specification: TASK-E06 cannot be assigned, estimated, implemented, or accepted. The frontend event timeline referenced in E04 Step 7 remains undefined scope. The `≥ 15 event clusters` success criterion from E04 has no visualization layer to validate it against analyst requirements.

**Status:** RESOLVED - Specification backfilled above.

---

## PART IV — CROSS-TASK DEPENDENCY ANALYSIS

### Dependency Ordering (Blocking Relationships)

```
TASK-A07 (Bayesian Tracker)
  FINDING I-02 resolution (speaker_id in TimeSlice) — MUST COMPLETE BEFORE E05
  FINDING I-01 resolution (prior initialization) — MUST COMPLETE BEFORE E05

GAP-02 (DiscourseFlow attribute contract) — MUST COMPLETE BEFORE E04 model changes
GAP-06 (Fischer DNA edge normalization) — MUST COMPLETE BEFORE E04 graph integration

TASK-E04 backend (CanonicalEvent registry API) — MUST COMPLETE BEFORE E06
TASK-E05 (ConsensusMoment API) — MUST COMPLETE BEFORE E06
```

### Unresolved Upstream Finding Impact Matrix

| Finding | Source Task | E04 Impact | E05 Impact | E06 Impact |
|---|---|---|---|---|
| FINDING I-01 | TASK-A07 | None direct | Distorts new-speaker theta → false clusters | None direct |
| FINDING I-02 | TASK-A07 | None direct | ConsensusMoment.confidence non-functional | Timeline confidence annotations invalid |
| GAP-02 | GAT/E02 | DiscourseFlow mutation unsafe | None direct | None direct |
| GAP-06 | GAT/E02 | Event node edge weights corrupted | None direct | None direct |
| FINDING C-03 | GAT | GAT anomaly scoring non-functional | None direct | None direct |
| FINDING M-01 | TASK-E02 | CUDA GAT training blocked | None direct | None direct |
| FINDING M-03 | SpeakerPosition | None direct | recalibrate_weights rejects valid defaults → theta undefined | Timeline theta values undefined |

---

## SECTION — CORRECTED SUCCESS CRITERIA

### TASK-E04 (Supersedes original)

```
1. Event mention detection precision/recall (predicate-based, not ARG1-based):
   English segments: CoNLL F1 ≥ 0.65 on ECB+ subset (domain gap acknowledged)
   Turkish segments: Manual annotation of 50 pairs; F1 ≥ 0.60; κ ≥ 0.70 inter-annotator

2. Cross-session event clustering:
   ≥ 15 distinct CanonicalEvent clusters from 10-session multilingual case study
   Cluster identity stable across ≥ 2 consecutive pipeline re-runs (deterministic ID required)

3. LLM verification:
   False positive rate < 0.10 on held-out annotated pair set (min 50 pairs)
   LLM invocation rate < 30% of all candidate pairs (threshold window calibration required)

4. Infrastructure:
   CanonicalEvent.event_id deterministic — SHA-256 based, same ID across re-runs
   Event registry persisted in SQL (Alembic migration required), not Redis-only
   All LLM prompts registered in PromptRegistry with SHA-256 version tracking
```

### TASK-E05 (Supersedes original)

```
1. Convergence detection:
   ≥ 75% accuracy on expert-labeled convergence moments
   EWMA smoothing with k=3 window applied — not raw first-order difference
   Requires FINDING I-02 (speaker_id in TimeSlice) to be resolved

2. Coalition detection:
   ≥ 80% expert agreement, evaluated on ≥ 3 distinct panel compositions
   DBSCAN eps calibrated per corpus IQR, not fixed at 0.15
   CoalitionCluster.stability defined as stable_session_count / window_size ∈ [0.0, 1.0]

3. Real-time update:
   < 5 seconds end-to-end via pre-computed Celery task + Redis cache read
   Full recompute triggered async on session completion, not on API request
   Cache miss returns HTTP 202 Accepted with retry guidance

4. Architectural:
   Implemented as ConsensusTrackerUseCase — NOT as extension of aggregate_bilateral_sentiment.py
   Registered in DI container per existing make_*_use_case() pattern (Community 94)
```

### TASK-E06 (New — replaces empty placeholder)

```
1. Renders ≥ 15 event clusters correctly from 10-session E04 case study output
2. ConsensusMoment overlays: ±1 session alignment with expert-labeled moments
3. Render time < 500ms for ≤ 200 events (Chromium 125+)
4. No event_id collision in rendered output (requires E04-C-02 deterministic ID fix)
5. Filter by actor, event_type, date range functional
6. API contracts for GET /events and GET /consensus/{session_id} defined in E04 before E06 implementation begins
```

---

## SECTION — FINDING PRIORITY MATRIX

| ID | Task | Classification | Blocking? | Fix Effort |
|---|---|---|---|---|
| E04-C-01 | E04 | CRITICAL | Yes — invalidates entire E04 pipeline | Medium |
| E04-C-02 | E04 | CRITICAL | Yes — breaks idempotency and deduplication | Low |
| E05-C-01 | E05 | CRITICAL | Yes — coalition detection systematically wrong | Low |
| E05-C-02 | E05 | CRITICAL | Yes — depends on TASK-A07 FINDING I-02 | Blocked on TASK-A07 |
| E06-C-01 | E06 | CRITICAL | Yes — no specification to implement | Medium (spec writing) |
| E04-M-01 | E04 | MAJOR | Conditional (blocked if GAP-02 unresolved) | Low |
| E04-M-02 | E04 | MAJOR | Yes — Redis as primary store loses data | Medium |
| E04-M-03 | E04 | MAJOR | No — affects evaluation validity only | Low (criteria rewrite) |
| E04-M-04 | E04 | MAJOR | Yes — cost and quality both undefined | Low |
| E04-M-05 | E04 | MAJOR | Yes — Turkish coreference fails | Medium |
| E04-M-06 | E04 | MAJOR | Conditional (blocked if GAP-06 unresolved) | Low |
| E05-M-01 | E05 | MAJOR | Yes — SRP violation, transaction boundary issue | Medium |
| E05-M-02 | E05 | MAJOR | Yes — stability metric uninterpretable | Low |
| E05-M-03 | E05 | MAJOR | Yes — panel_range semantic ambiguity | Low |
| E05-M-04 | E05 | MAJOR | Yes — noise in delta_d produces false signals | Low |
| E05-M-05 | E05 | MAJOR | Yes — 5s SLA unachievable without pre-computation | High |
| E04-m-01 | E04 | MINOR | No | Low |
| E04-m-02 | E04 | MINOR | No | Trivial |
| E05-m-01 | E05 | MINOR | No | Trivial |
| E05-m-02 | E05 | MINOR | No | Low |

---

## METADATA

```
Report version:       2.0 (supersedes original Antigravity Development Report)
Source graph commit:  8d37ef99
Corpus stats:         601 files · 586,895 words
Graph stats:          10,106 nodes · 17,198 edges · 1,060 communities
Inferred edge ratio:  24% (avg confidence 0.59) — treat inferred relationships as unverified
Critical findings:    5 (E04-C-01, E04-C-02, E05-C-01, E05-C-02, E06-C-01)
Major findings:       11
Minor findings:       4
Upstream blockers:    TASK-A07/FINDING I-02 (blocks E05-C-02), GAP-02 (blocks E04-M-01), GAP-06 (blocks E04-M-06)
```