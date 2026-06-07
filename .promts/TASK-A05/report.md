# TECHNICAL DEVELOPMENT REPORT: TASK-A05 — STRATEGIC NARRATIVE ANALYSIS
**Report Version:** 2.0 (Supersedes original task_a05_developer_report.md)
**Codebase Revision:** BB-PAXDATA commit `8d37ef99`
**Graph Source:** Graphify GRAPH_REPORT.md (558 files · 8419 nodes · 15046 edges · 878 communities)
**Graph Extraction Quality:** 75% EXTRACTED · 25% INFERRED (3793 inferred edges at avg confidence 0.59)
**Target:** Antigravity downstream code generation agent

---

## SECTION 0: CODEBASE STATE — STRUCTURAL PRECONDITIONS

Graph-confirmed god nodes relevant to TASK-A05 integration surface:
- `Analysis`: 171 edges — cross-community bridge between Communities 1, 6, 8, 15, 27, 36, 57, 60, 75, 78, 142, 168, 173, 174, 224, 473, 492, 636, 653, 671, 696, 714, 716, 726. 157 of its edges are INFERRED (confidence ~0.59). Any new method that consumes `Analysis` must be verified against the actual domain model fields, not inferred graph connections.
- `Segment`: 122 edges — 108 INFERRED. Field names on `Segment` accessed by A05 code (`source_text`, `entities`, `speaker_id`) require explicit schema verification before implementation.
- `BilateralSentimentTable`: 58 edges — resident in Community 1 (66-node cluster, cohesion 0.16). NOT the same object as the domain `BilateralSentiment`. The A05 spec targets `DiscourseFlowTable` for persistence but routes narrative fields through `BilateralSentiment` at pipeline stage execution time.
- `CrossAnomalyServiceImpl`: Community 74 (26 nodes, cohesion 0.07). Existing detection logic uses pairwise SRL frame comparison and negation cue scoring. The proposed `detect_narrative_clashes()` is additive to this class.
- `SBICalculator`: Community 60 (14 nodes, cohesion 0.10). Wordfish EM algorithm and SpeakerPosition already implemented. TASK-A07 downstream dependency declared in Section 6 of the spec must account for this existing SBI infrastructure to avoid duplication.
- Graph Knowledge Gap: 552 isolated nodes confirmed. Namespace conflicts in new module names (`narrative_salience_tracker`, `narrative_classifier_stage`) cannot be ruled out without explicit `grep -r "NarrativeSalienceTracker\|NarrativeClassifierStage"` on source tree.

---

## SECTION 1: THEORETICAL MODEL — IMPLEMENTATION FIDELITY ASSESSMENT

### FINDING T-01
**Classification:** informational
**Location:** Section 1 — Mathematical Model of Narrative Salience
**Root Cause:** The salience formula `S_A(L, t) = sum(Freq(d,L) × Phi(d) × Omega(d))` defines a cross-document aggregation producing an unbounded raw score, then maps to [0,1] via sigmoid. The implementation in `NarrativeSalienceTracker.compute_salience()` operates on a single document at a time (one `Analysis` object), computing a per-document salience rather than the actor-level temporal aggregate `S_A(L, t)` specified in the formula. No aggregator accumulates per-actor, per-layer, per-session sums across the panel.
**Proposed Resolution:** Either (a) rename the method `compute_per_document_salience()` and document that `S_A(L, t)` requires a separate aggregation pass over all `Analysis` objects for actor `A` in time window `t`, or (b) implement the actor-level aggregation in a dedicated `NarrativeSalienceAggregator` service that calls `compute_salience()` per document and sums results. Option (b) is required to correctly feed TASK-A07 Bayesian priors.
**Impact Assessment:** Leaving this unaddressed means TASK-A07 receives per-document salience scores instead of actor-level temporal aggregates, producing incorrect Bayesian position updates. Medium severity on downstream correctness.

### FINDING T-02
**Classification:** informational
**Location:** Section 1 — Counter-Narrative Detection Algorithm
**Root Cause:** The conflict formula `Conflict(A, B, topic, t) = Stance_A(topic) × Stance_B(topic) < 0` requires a `Stance` scalar per actor per topic. No `Stance` field or service exists in the current domain model based on graph inspection. The proposed `detect_narrative_clashes()` in Section 4.2 does not compute stances — it uses `rel.avg_sentiment` as a proxy and does not check for topic alignment between actors.
**Proposed Resolution:** Either formally substitute `Stance_A(topic) ≈ avg_sentiment` (document the approximation explicitly) or defer counter-narrative detection implementation until a `StanceResolver` service is available. If using the substitution, the threshold `< -0.3` used in `detect_narrative_clashes()` should be externalized to `Settings` for tuning parity with other anomaly thresholds.
**Impact Assessment:** Informal until TASK-A07 requires high-fidelity stance vectors. The approximation is operationally adequate for Phase 2.

---

## SECTION 2: DATABASE & DOMAIN SCHEMA — DEFECTS

### FINDING D-01
**Classification:** critical
**Location:** `src/bb_paxdata/domain/models/discourse_flow.py` — Section 2.2
**Root Cause:** Invalid Pydantic v2 syntax. The blueprint writes:
```python
class DiscourseFlow(BaseModel):
    model_config = model_config(frozen=True)
```
`model_config` is used as both the class attribute name and the imported function/callable. In Pydantic v2, `model_config` is a reserved class attribute that must be assigned a `ConfigDict` instance. The above code will raise `NameError: name 'model_config' is not defined` if `model_config` is not imported, or silently produce a recursive self-assignment if it is. The correct import and usage:
```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from bb_paxdata.domain.enums.country_enums import NarrativeLayer

class DiscourseFlow(BaseModel):
    model_config = ConfigDict(frozen=True)

    # ... existing fields ...
    narrative_layer: Optional[NarrativeLayer] = Field(
        default=None,
        description="Miskimmon et al. (2013) narrative layer classification"
    )
    narrative_target_actor: Optional[str] = Field(
        default=None,
        description="The country or actor target of this narrative segment"
    )
    narrative_salience: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Per-document narrative salience score (see FINDING T-01)"
    )
```
**Proposed Resolution:** Replace `model_config = model_config(frozen=True)` with `model_config = ConfigDict(frozen=True)` and add `from pydantic import ConfigDict` to the import block. Apply the same verification to `BilateralSentiment` — the three new fields (`narrative_layer`, `narrative_target_actor`, `narrative_salience`) must also be added to the `BilateralSentiment` domain model for the pipeline stage enrichment to be non-destructive (see FINDING P-01).
**Impact Assessment:** Syntactic defect — module import fails at startup if not corrected. Blocks all A05 functionality.

### FINDING D-02
**Classification:** major
**Location:** `alembic/versions/xxxx_add_narrative_to_discourse_flows.py` — Section 2.4
**Root Cause:** The migration script is not idempotent. `op.add_column()` raises `OperationalError: duplicate column name` if the migration is re-run against a database where columns already exist. SQLite does not support `ADD COLUMN IF NOT EXISTS`. Additionally, `server_default='0.0'` is a string literal used as a SQL expression for a `Float` column — while valid in SQLite, this is not portable to PostgreSQL (future migration target). The `nullable=False` constraint on `narrative_salience` with `server_default='0.0'` on an existing table will backfill all existing rows with `0.0`, which is correct, but the migration provides no rollback safety net for the `narrative_salience` column if production data has been written between upgrade and a required downgrade.
**Proposed Resolution:**
```python
# alembic/versions/xxxx_add_narrative_to_discourse_flows.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("discourse_flows")}

    if "narrative_layer" not in existing_cols:
        op.add_column(
            "discourse_flows",
            sa.Column("narrative_layer", sa.String(length=50), nullable=True)
        )
    if "narrative_target_actor" not in existing_cols:
        op.add_column(
            "discourse_flows",
            sa.Column("narrative_target_actor", sa.String(length=100), nullable=True)
        )
    if "narrative_salience" not in existing_cols:
        op.add_column(
            "discourse_flows",
            sa.Column(
                "narrative_salience",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.0")
            )
        )

def downgrade():
    with op.batch_alter_table("discourse_flows") as batch_op:
        batch_op.drop_column("narrative_salience")
        batch_op.drop_column("narrative_target_actor")
        batch_op.drop_column("narrative_layer")
```
Note: `batch_alter_table` is required for SQLite column drops since SQLite does not support `DROP COLUMN` natively; Alembic's batch mode recreates the table.
**Impact Assessment:** Without idempotency guard, CI/CD pipelines that run migrations on pre-existing databases will fail. The `batch_op` fix is required for SQLite downgrade correctness.

### FINDING D-03
**Classification:** major
**Location:** `src/bb_paxdata/domain/enums/country_enums.py` — Section 2.1
**Root Cause:** The spec introduces `NarrativeLayer` as `StrEnum`. Community 0 in the graph contains all existing domain enums: `AnomalySeverity`, `AppraisalAttitude`, `BlocType`, `DemandType`, `DiplomaticTone`, `DkiStance`, `DynamicEvent`. These use the standard `Enum` or string-valued `Enum` pattern, not Python 3.11+ `StrEnum`. The distinction matters: `StrEnum` makes the enum member itself the string value (`NarrativeLayer.SYSTEM == "system"` is `True`), whereas standard `Enum` requires `.value` access. If any existing serialization path (SQLAlchemy ORM mapper, Pydantic validator, JSON encoder) uses `.value` on enum members uniformly, introducing `StrEnum` creates a dual-behavior inconsistency. The `to_domain()` and `from_domain()` methods in Section 2.3 already use `entity.narrative_layer.value` in `from_domain()` and `NarrativeLayer(self.narrative_layer)` in `to_domain()` — this is consistent with standard Enum behavior and NOT with StrEnum (where `.value` is redundant but not harmful).
**Proposed Resolution:** Replace `StrEnum` with `str, Enum` mixed inheritance to match the project's existing enum pattern:
```python
# src/bb_paxdata/domain/enums/country_enums.py
from enum import Enum

class NarrativeLayer(str, Enum):
    SYSTEM = "system"
    IDENTITY = "identity"
    ISSUE = "issue"
```
This preserves string-equality semantics while using the same base pattern as other enums in Community 0. `StrEnum` should only be adopted if the project standardizes on it across ALL enums in a dedicated refactor.
**Impact Assessment:** Silent behavioral inconsistency in serialization paths. String comparisons in `detect_narrative_clashes()` (`layer == NarrativeLayer.IDENTITY`) will work correctly with both patterns, but Pydantic model validation and SQLAlchemy `.value` mappings will behave differently under `StrEnum`.

---

## SECTION 3: COMPONENT IMPLEMENTATION — DEFECTS

### FINDING P-01
**Classification:** critical
**Location:** `src/bb_paxdata/application/pipeline/stages/narrative_classifier_stage.py` — Section 3.2, `process_analysis()` method
**Root Cause:** `model_copy(update={...})` on a frozen Pydantic v2 model does not add fields that are absent from the model's schema. If `BilateralSentiment` does not declare `narrative_layer`, `narrative_target_actor`, and `narrative_salience` as fields, the `update` dict entries for those keys are silently discarded. The enriched `sentiment.model_copy(update={"narrative_layer": predicted_layer, ...})` returns the original object unchanged with no exception raised.

This is confirmed by Pydantic v2 behavior: `model_copy(update=extra_dict)` raises `ValueError` only if the model has `model_config = ConfigDict(extra='forbid')`. With `extra='ignore'` (Pydantic default) or on frozen models without extra configuration, unknown keys in `update` are dropped without warning.

The downstream `NetworkAssemblyStage` diff in Section 4.1 reads `getattr(sentiment, "narrative_layer", None)` — this `getattr` with a default of `None` will always return `None` if the field was never added to `BilateralSentiment`, masking the data loss entirely.

**Proposed Resolution:** Add the three narrative fields to `BilateralSentiment`:
```python
# src/bb_paxdata/domain/models/bilateral_sentiment.py
from typing import Optional
from pydantic import ConfigDict, Field
from bb_paxdata.domain.enums.country_enums import NarrativeLayer

class BilateralSentiment(BaseModel):
    model_config = ConfigDict(frozen=True)

    # ... existing fields ...
    narrative_layer: Optional[NarrativeLayer] = Field(
        default=None,
        description="Narrative layer assigned by NarrativeClassifierStage"
    )
    narrative_target_actor: Optional[str] = Field(
        default=None,
        description="Resolved narrative target actor"
    )
    narrative_salience: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Per-document narrative salience score"
    )
```
No DB migration is required for `BilateralSentimentTable` if these are pipeline-only fields that are consumed by `NetworkAssemblyStage` and then persisted to `DiscourseFlowTable`. However, if `BilateralSentiment` objects are ever persisted independently (Community 1 confirms `BilateralSentimentTable` as a persistent ORM model), a separate migration for `bilateral_sentiments` table is required.
**Impact Assessment:** All narrative enrichment silently no-ops without this fix. TASK-A05 produces zero analytical output. TASK-A07 receives null narrative data. This is the highest-severity defect in the spec.

### FINDING P-02
**Classification:** critical
**Location:** `src/bb_paxdata/domain/services/narrative_salience_tracker.py` — `calculate_speech_act_modifier()`, Section 3.1
**Root Cause:** The method checks `if speech_act.is_coercive` but `is_coercive` is not defined in the `SpeechActClassification` model as specified anywhere in the codebase graph. The test fixture in Section 5 passes `force_modifier="strongly"` to trigger the coercive path, implying `is_coercive` is expected to be derived from `force_modifier`. If `SpeechActClassification` does not declare `is_coercive` as either a stored field or a `@computed_field` / `@property`, the `AttributeError` is raised at runtime on any `SpeechActClassification` instance where `speech_act.is_coercive` is accessed.

Additionally, the test `test_narrative_salience_calculation()` will pass even if the coercive boost path is never reached, because the assertion `assert score_2 > score_1` is satisfied by the base `DIRECTIVE` modifier alone (score_2 uses `confidence=0.9` vs score_1's `ASSERTIVE` type which receives no modifier boost). The test does not isolate whether the `is_coercive` branch specifically executed.

**Proposed Resolution:**
```python
# Option A: Add is_coercive as a computed_field on SpeechActClassification
# src/bb_paxdata/domain/models/speech_act.py
from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional

COERCIVE_FORCE_MODIFIERS: frozenset[str] = frozenset({
    "strongly", "firmly", "categorically", "unconditionally", "immediately"
})

class SpeechActClassification(BaseModel):
    model_config = ConfigDict(frozen=True)
    primary_type: SpeechActType
    confidence: float
    force_modifier: Optional[str] = None

    @computed_field
    @property
    def is_coercive(self) -> bool:
        return (
            self.force_modifier is not None
            and self.force_modifier.lower() in COERCIVE_FORCE_MODIFIERS
        )
```
```python
# Option B: Inline the check in calculate_speech_act_modifier() without attribute dependency
def calculate_speech_act_modifier(self, speech_act: Optional[SpeechActClassification]) -> float:
    if not speech_act:
        return 1.0
    COERCIVE_MODIFIERS = frozenset({"strongly", "firmly", "categorically", "unconditionally"})
    is_coercive = (
        speech_act.force_modifier is not None
        and speech_act.force_modifier.lower() in COERCIVE_MODIFIERS
    )
    if speech_act.primary_type in (SpeechActType.DIRECTIVE, SpeechActType.DECLARATIVE):
        modifier = 1.0 + (self.speech_act_weight * speech_act.confidence)
        if is_coercive:
            modifier += 0.15
        return modifier
    return 1.0
```
Option B is preferred: it eliminates the cross-model dependency and makes the coercive detection logic self-contained in the tracker service.
**Impact Assessment:** `AttributeError` on every `SpeechActClassification` instance that lacks `is_coercive`. All salience computation fails at the modifier step. The test suite does not catch this because the test fixture happens to produce a correct ordering without the coercive branch executing.

### FINDING P-03
**Classification:** major
**Location:** `src/bb_paxdata/domain/services/narrative_salience_tracker.py` — `compute_salience()`, line `import math`
**Root Cause:** `import math` is placed inside the function body. This is a standard library module and incurs a dictionary lookup in `sys.modules` on every call to `compute_salience()`. While Python caches the lookup after the first import, the idiom violates PEP 8 §Imports ("Imports are always put at the top of the file") and makes static analysis tools (mypy, pylint) unable to verify the import statically.
**Proposed Resolution:**
```python
# Module-level, before class definition
import math
import structlog
from typing import Sequence, Optional
# ... rest of imports
```
Remove `import math` from inside `compute_salience()`.
**Impact Assessment:** Minor performance (negligible in practice). Static analysis false negatives. Code style inconsistency with rest of codebase.

### FINDING P-04
**Classification:** major
**Location:** `src/bb_paxdata/domain/services/narrative_salience_tracker.py` — `compute_salience()`, sigmoid formula
**Root Cause:** The sigmoid compression formula:
```python
salience_score = 2.0 / (1.0 + math.exp(-raw_score / 3.0)) - 1.0
```
produces a severely biased low-salience distribution for the expected input range. For typical inputs:
- `base_frequency=1`, `frame_alignment=0.8`, `speech_act_mod=1.0` → `raw_score=0.8` → `salience=0.130`
- `base_frequency=2`, `frame_alignment=0.8`, `speech_act_mod=1.25` → `raw_score=2.0` → `salience=0.314`
- `base_frequency=3`, `frame_alignment=0.8`, `speech_act_mod=1.25` → `raw_score=3.0` → `salience=0.462`

The [0.5, 1.0] range of the output is only reachable at `raw_score > 3.5`. With keyword-count-based `base_frequency` capped by vocabulary size (10 keywords per layer in the `narrative_keywords` dict), the theoretical maximum `raw_score ≈ 10 × 1.0 × 1.4 = 14`, which yields `salience=0.976`. The lower bound `frame_alignment = max(0.5, dominant_score)` prevents collapse to zero but compresses most real-world outputs into [0.1, 0.5].

The anomaly detection threshold in `detect_narrative_clashes()` requires `salience > 0.6` to trigger. Given the above distribution, only very high keyword density segments (7+ keyword matches) will exceed this threshold. This is likely too restrictive for real diplomatic text.
**Proposed Resolution:** Either (a) calibrate `scale=3.0` against a sample panel dataset and replace with an empirically determined value, or (b) use min-max normalization within a session rather than a fixed sigmoid. Expose the scale parameter as a constructor argument:
```python
def __init__(
    self,
    speech_act_weight: float = 0.25,
    sigmoid_scale: float = 1.5  # Reduced from 3.0 to increase sensitivity
) -> None:
    self.speech_act_weight = speech_act_weight
    self.sigmoid_scale = sigmoid_scale

# In compute_salience():
salience_score = 2.0 / (1.0 + math.exp(-raw_score / self.sigmoid_scale)) - 1.0
```
A scale of `1.5` produces `salience=0.462` at `raw_score=1.0` and `salience=0.761` at `raw_score=2.0`, which is more calibrated to the expected input density.
**Impact Assessment:** With `scale=3.0`, the `detect_narrative_clashes()` threshold of `0.6` will almost never trigger for typical single-sentence inputs. TASK-A05 anomaly detection is functionally dead at default settings without this fix.

### FINDING P-05
**Classification:** major
**Location:** `src/bb_paxdata/domain/services/narrative_salience_tracker.py` — `calculate_speech_act_modifier()` docstring vs implementation
**Root Cause:** The docstring states "Assertive/Directive increase weight" but the implementation only boosts `DIRECTIVE` and `DECLARATIVE`. `SpeechActType.ASSERTIVE` receives no modifier (returns `1.0`). This is a semantic inconsistency between documentation and code. If `ASSERTIVE` is intentionally excluded, the docstring must be corrected. If `ASSERTIVE` should receive a modifier, the condition must be updated.
**Proposed Resolution — if ASSERTIVE intended:**
```python
BOOSTED_TYPES = frozenset({
    SpeechActType.DIRECTIVE,
    SpeechActType.DECLARATIVE,
    SpeechActType.ASSERTIVE,
})
if speech_act.primary_type in BOOSTED_TYPES:
    modifier = 1.0 + (self.speech_act_weight * speech_act.confidence)
    ...
```
**Proposed Resolution — if ASSERTIVE intentionally excluded:**
```python
# Docstring correction:
"""Computes speech act multiplier Omega(d). Directive and Declarative types increase weight.
ASSERTIVE types receive no modifier (returns 1.0).
Reference: Searle (1969) speech act taxonomy as applied in TASK-A04."""
```
**Impact Assessment:** Incorrect behavior depending on intended semantics. Docstring mismatch causes incorrect assumptions in TASK-A07 downstream when assertive statements carry narrative weight in the theoretical model.

### FINDING P-06
**Classification:** major
**Location:** `src/bb_paxdata/application/pipeline/stages/narrative_classifier_stage.py` — `classify_segment_layer()`, default fallback
**Root Cause:** When no keyword matches are found (`sum(scores.values()) == 0`), the classifier defaults to `NarrativeLayer.ISSUE`. This is an undocumented design decision with no theoretical justification cited. In Miskimmon et al. (2013), issue narratives are the most specific and concrete layer — defaulting to ISSUE for zero-signal text (e.g., formal procedural speech with no geopolitical content) will inflate ISSUE salience counts and potentially trigger false counter-narrative clashes via `detect_narrative_clashes()`.
**Proposed Resolution:** Return `None` for zero-signal text and propagate this upstream:
```python
def classify_segment_layer(self, text: str) -> Optional[NarrativeLayer]:
    """Returns None if no narrative layer signal is detected."""
    normalized_text = text.lower()
    scores = {layer: 0 for layer in NarrativeLayer}

    for layer, keywords in self.narrative_keywords.items():
        for kw in keywords:
            if kw in normalized_text:
                scores[layer] += 1

    if sum(scores.values()) == 0:
        return None  # No narrative signal; do not assign layer

    return max(scores, key=scores.get)
```
Update `process_analysis()` to skip enrichment when `predicted_layer is None`:
```python
predicted_layer = self.classify_segment_layer(analysis.source_text)
if predicted_layer is None:
    return analysis  # No narrative signal; return unchanged
```
**Impact Assessment:** Without this fix, every segment in the pipeline receives a narrative layer assignment regardless of analytical validity. Downstream aggregation (TASK-A07) will operate on noise-inflated ISSUE counts.

---

## SECTION 4: SERVICE INTEGRATION — DEFECTS

### FINDING I-01
**Classification:** critical
**Location:** `src/bb_paxdata/infrastructure/nlp/cross_anomaly_service_impl.py` — `detect_narrative_clashes()`, Section 4.2
**Root Cause:** `ContradictionResult` is instantiated with hardcoded zeros for semantically meaningful fields:
```python
result = ContradictionResult(
    ...
    n_sentences=len(analysis.segments),   # BUG: hardcoded as 0 in spec
    m1=0.0,
    m2=0.0,
    theta=0.0,
    window=0.0,
    ...
)
```
`n_sentences=0` is demonstrably incorrect — `analysis.segments` contains the actual segment list. The `m1`, `m2`, `theta`, `window` fields semantically correspond to metric values in the existing `ContradictionResult` schema (used by other `CrossAnomalyServiceImpl` methods). Populating them with zeros means any downstream consumer that reads these fields from a narrative-clash result will receive invalid data.
**Proposed Resolution:**
```python
bilaterals = analysis.bilateral_metrics or []
clash_detected = False
description = ""
boost = 0.0
clash_from = None
clash_to = None
clash_salience = 0.0

for rel in bilaterals:
    if rel.avg_sentiment < -0.3:
        layer = getattr(rel, "narrative_layer", None)
        salience = getattr(rel, "narrative_salience", 0.0)
        if layer == NarrativeLayer.IDENTITY and salience > 0.6:
            if not clash_detected:  # Capture first and continue to accumulate
                clash_from = rel.from_country
                clash_to = rel.to_country
                clash_salience = salience
            clash_detected = True
            boost += salience * self.COUNTER_NARRATIVE_BOOST

# Do NOT break early — accumulate all clashing bilaterals
boost = round(min(boost, 1.5), 6)
is_anomaly = boost > threshold

return ContradictionResult(
    score=boost,
    threshold=threshold,
    is_anomaly=is_anomaly,
    anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
    n_sentences=len(analysis.segments or []),
    m1=clash_salience,
    m2=float(len([
        r for r in bilaterals
        if getattr(r, "narrative_layer", None) == NarrativeLayer.IDENTITY
    ])),
    theta=threshold,
    window=float(len(bilaterals)),
    metadata={
        "narrative_clash": clash_detected,
        "clash_actor_from": clash_from,
        "clash_actor_to": clash_to,
        "description": (
            f"STRATEGIC NARRATIVE CLASH: Actor '{clash_from}' deflected confrontation "
            f"from '{clash_to}' via IDENTITY pivot. Salience: {clash_salience:.4f}."
        ) if clash_detected else "",
        "boost": boost
    }
)
```
**Impact Assessment:** `ContradictionResult` with `n_sentences=0` violates the data contract consumed by HITL queue prioritization logic (Community 16 shows `get_consensus_distribution()` and `get_priority_distribution()`). False-zero `n_sentences` corrupts per-sentence anomaly rate metrics displayed in the admin panel.

### FINDING I-02
**Classification:** major
**Location:** `src/bb_paxdata/infrastructure/nlp/cross_anomaly_service_impl.py` — `detect_narrative_clashes()`, loop control
**Root Cause:** The original spec uses `break` after the first detected clash:
```python
if layer == NarrativeLayer.IDENTITY and salience > 0.6:
    clash_detected = True
    boost += salience * self.COUNTER_NARRATIVE_BOOST
    description = (...)
    break
```
This means only the first `BilateralSentiment` in `analysis.bilateral_metrics` satisfying the condition is detected. Iteration order of `analysis.bilateral_metrics` is not guaranteed to be deterministic (depends on insertion order in `process_analysis()`). If a panel has three bilateral pairs of which two exhibit identity-pivot clashes, only the one that appears first in the list is detected. This is a non-deterministic truncation defect.
**Proposed Resolution:** Remove `break` and accumulate all qualifying clashes as shown in FINDING I-01's proposed resolution.
**Impact Assessment:** False-negative clash detection in multi-actor panels. Severity scales with number of diplomatic actors in the analyzed panel.

### FINDING I-03
**Classification:** major
**Location:** `src/bb_paxdata/application/pipeline/stages/assemble_network.py` — Section 4.1, diff block
**Root Cause:** The diff uses `getattr(sentiment, "narrative_layer", None)` with a `None` default for all three narrative fields. If FINDING P-01 is unresolved (fields not added to `BilateralSentiment`), this silently passes `None` / `0.0` values into `DiscourseFlow` persistence. There is no assertion or warning log that would surface the data loss. The `srl_update.update(narrative_update)` call will overwrite any existing SRL-derived values only if `narrative_update` contains a key that was already in `srl_update` — this is unlikely for the narrative keys but represents an undocumented ordering dependency.
**Proposed Resolution:**
```python
# Replace getattr with explicit attribute access after verifying BilateralSentiment schema
narrative_update = {}
if hasattr(sentiment, "narrative_layer") and sentiment.narrative_layer is not None:
    narrative_update["narrative_layer"] = sentiment.narrative_layer
    narrative_update["narrative_target_actor"] = sentiment.narrative_target_actor
    narrative_update["narrative_salience"] = sentiment.narrative_salience
else:
    self._log.warning(
        "narrative_fields_missing",
        sentiment_from=sentiment.from_country,
        sentiment_to=sentiment.to_country,
        msg="BilateralSentiment has no narrative fields; NarrativeClassifierStage may have been skipped"
    )
```
**Impact Assessment:** Silent data loss in `DiscourseFlowTable`. Monitoring in HITL admin panel will not surface the problem. Downstream TASK-A07 receives null narrative inputs.

---

## SECTION 5: TESTING SUITE — DEFECTS

### FINDING T-01
**Classification:** major
**Location:** `tests/unit/nlp/test_strategic_narratives.py` — `test_narrative_salience_calculation()`
**Root Cause:** The test asserts `score_2 > score_1` where `score_2` is computed with `SpeechActType.DIRECTIVE` at `confidence=0.9` and `score_1` with `SpeechActType.ASSERTIVE` at `confidence=0.8`. Under the current implementation, `ASSERTIVE` receives no modifier (returns `1.0`) while `DIRECTIVE` receives `1.0 + 0.25 × 0.9 = 1.225`. The assertion passes purely because of the type difference, not because the coercive boost branch was exercised. The test does not verify that `force_modifier="strongly"` caused the additional `+0.15` boost.

A correct test that isolates the coercive boost:
```python
def test_narrative_salience_coercive_boost_isolated():
    tracker = NarrativeSalienceTracker(speech_act_weight=0.25)

    # Both DIRECTIVE, same confidence — only difference is force_modifier
    directive_base = SpeechActClassification(
        primary_type=SpeechActType.DIRECTIVE,
        confidence=0.9,
        force_modifier=None
    )
    directive_coercive = SpeechActClassification(
        primary_type=SpeechActType.DIRECTIVE,
        confidence=0.9,
        force_modifier="strongly"
    )

    mod_base = tracker.calculate_speech_act_modifier(directive_base)
    mod_coercive = tracker.calculate_speech_act_modifier(directive_coercive)

    # Coercive modifier MUST be exactly base + 0.15
    assert abs(mod_coercive - mod_base - 0.15) < 1e-9, (
        f"Expected coercive boost of 0.15, got delta={mod_coercive - mod_base:.6f}"
    )
```
**Proposed Resolution:** Add the isolated test above. Retain the existing test but add a comment that it does not test the coercive branch in isolation.
**Impact Assessment:** Test suite provides false confidence that the coercive boost path is verified. Combined with FINDING P-02 (`is_coercive` undefined), the gap means the coercive branch can be broken without any test failing.

### FINDING T-02
**Classification:** major
**Location:** `tests/unit/nlp/test_strategic_narratives.py` — `test_narrative_clash_anomaly_trigger()`
**Root Cause:** `@pytest.mark.asyncio` requires `pytest-asyncio` to be installed and configured. Neither a `pyproject.toml` `asyncio_mode` setting nor a `pytest.ini` `asyncio_mode = auto` directive is specified. In `pytest-asyncio >= 0.21`, the default mode changed from `auto` to `strict`, requiring explicit `asyncio_mode` or `@pytest.mark.asyncio` combined with a session-scoped fixture. Without configuration, the test will be collected but may not actually run as an async test in strict mode — it may be treated as a synchronous test returning a coroutine object, which evaluates as truthy and causes silent test pass without execution.
**Proposed Resolution:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```
OR on the test function:
```python
@pytest.mark.asyncio(loop_scope="function")
async def test_narrative_clash_anomaly_trigger():
    ...
```
**Impact Assessment:** Test may silently pass without executing the async body. CI pipeline reports green while async anomaly detection is untested.

### FINDING T-03
**Classification:** minor
**Location:** `tests/unit/nlp/test_strategic_narratives.py` — `test_narrative_clash_anomaly_trigger()`
**Root Cause:** The `Analysis` constructor receives `id="anal-1"` but the `Analysis` domain model likely expects `id: UUID` based on the ORM mapping in `DiscourseFlowTable.to_domain()` which calls `uuid.UUID(self.id)`. Passing a non-UUID string will raise `pydantic.ValidationError` at `Analysis(id="anal-1", ...)` construction.
**Proposed Resolution:**
```python
import uuid
analysis = Analysis(
    id=uuid.uuid4(),
    source_text="This is an identity defense statement.",
    bilateral_metrics=[bilateral],
    segments=[]
)
```
**Impact Assessment:** Test fails at construction before reaching the assertion. Combined with FINDING T-02 (async test may not execute), this test provides zero coverage in its current form.

### FINDING T-04
**Classification:** minor
**Location:** Section 5 — "Verification Verification Commands" heading
**Root Cause:** Section header contains duplicate word: "Verification Verification Commands". This is a documentation authoring error in the original spec.
**Proposed Resolution:** Correct to "Verification Commands".
**Impact Assessment:** Parsing ambiguity for document-ingesting agents that use section headers as keys in structured extraction.

---

## SECTION 6: ARCHITECTURE — STRUCTURAL OBSERVATIONS

### FINDING A-01
**Classification:** major
**Location:** `src/bb_paxdata/application/pipeline/stages/narrative_classifier_stage.py` — `process_analysis()`, field access on `Analysis`
**Root Cause:** The implementation accesses `analysis.source_text`, `analysis.entities`, `analysis.speaker_id`, `analysis.frame_salience`, `analysis.speech_act`, `analysis.bilateral_metrics`, and `analysis.segments`. The `Analysis` god node has 171 edges and 157 INFERRED connections in the graph. The spec does not verify which of these field names exist on the actual `Analysis` domain model. In particular:
- `analysis.entities`: not confirmed in spec or graph. The graph shows `ArgumentGraph` (91 edges) and `Segment` (122 edges) as NER-carrying nodes; entity lists may reside on `Segment` objects, not directly on `Analysis`.
- `analysis.speaker_id`: not confirmed. Graph Community 58 shows `get_speaker_map_version()` and `normalize_name_for_matching()` in the speaker parsing utilities, suggesting speaker identity is resolved at a different layer.
- `analysis.frame_salience`: plausible given `FrameLexiconService` and `FrameAssembler` in Community 70, but field name unverified.
- `analysis.speech_act`: plausible given `SpeechActClassification` domain model existence, but field name unverified.

**Proposed Resolution:** Before code generation, execute:
```bash
grep -n "class Analysis" src/bb_paxdata/domain/models/analysis.py
grep -n "^\s\+[a-z_]\+:" src/bb_paxdata/domain/models/analysis.py
```
Map confirmed field names against the seven accessed in `process_analysis()`. Replace any unconfirmed field access with an explicit `AttributeError` guard or constructor injection pattern.
**Impact Assessment:** `AttributeError` at pipeline runtime if any of the seven field names are incorrect. The 157 INFERRED edges on `Analysis` (confidence ~0.59) means graph-based validation is insufficient — source code inspection is mandatory.

### FINDING A-02
**Classification:** major
**Location:** System architecture — persistence gap between pipeline stages
**Root Cause:** Narrative enrichments are applied to `BilateralSentiment` objects inside `NarrativeClassifierStage.process_analysis()` as immutable `model_copy` overrides. These enriched objects exist only in memory between stage execution and `NetworkAssemblyStage.process()`. If the pipeline is interrupted (exception in any intermediate stage, process kill, timeout) between these two stages, all narrative enrichments are lost with no DB record. No recovery path exists.

The graph confirms that `NetworkAssemblyStage` is downstream from `NarrativeClassifierStage` in the pipeline sequence via `_process_single_file()` (87 edges, betweenness centrality 0.064 — a cross-community bridge). The `_process_single_file()` orchestration must maintain stage ordering guarantees.

**Proposed Resolution:** Add a narrative persistence checkpoint after `NarrativeClassifierStage` completes. The simplest approach is to persist enriched `BilateralSentiment` narrative fields to a separate ephemeral cache keyed by `(panel_id, from_country, to_country)`, recoverable by `NetworkAssemblyStage` via cache lookup:
```python
# In NarrativeClassifierStage.process_analysis(), after computing enrichments:
for sentiment in updated_bilateral:
    if sentiment.narrative_layer is not None:
        cache_key = f"narrative:{sentiment.panel_id}:{sentiment.from_country}:{sentiment.to_country}"
        await self._cache.set(cache_key, {
            "narrative_layer": sentiment.narrative_layer.value,
            "narrative_target_actor": sentiment.narrative_target_actor,
            "narrative_salience": sentiment.narrative_salience,
        })
```
**Impact Assessment:** Without checkpointing, long-running panels with many segments will lose narrative data on any pipeline failure. Partial panel processing becomes unrecoverable for A05 outputs.

### FINDING A-03
**Classification:** informational
**Location:** Section 6 — Phase Deployment Timeline
**Root Cause:** TASK-A07 (Bayesian Position Tracker) is listed as downstream of TASK-A05. Community 60 confirms `SBICalculator` and `WordfishParams` already exist in the codebase. The SBI scoring (`SBICalculator`) uses Wordfish EM algorithm over speaker positions. If TASK-A07's Bayesian tracker is to incorporate `NarrativeLayer` as a prior weight, the interface between `NarrativeSalienceTracker` outputs and `SBICalculator` inputs must be specified explicitly. The spec does not define this interface.
**Proposed Resolution:** Before TASK-A07 implementation, produce an interface specification document defining:
1. The `SpeakerPosition.narrative_weight` field (new, or derived from `narrative_salience`).
2. The Bayesian update equation that consumes `S_A(L, t)` as a prior modifier on Wordfish positional estimates.
3. Whether `NarrativeLayer.SYSTEM` / `IDENTITY` / `ISSUE` map to different prior distributions or a single scalar weight.
**Impact Assessment:** Unspecified interface will cause TASK-A07 to implement incompatible data contracts relative to TASK-A05 outputs.

### FINDING A-04
**Classification:** informational
**Location:** `src/bb_paxdata/application/pipeline/stages/narrative_classifier_stage.py` — Section 3.2, `narrative_keywords` dict
**Root Cause:** The keyword vocabulary is hardcoded as a class-level dict with 10 keywords per layer. This approach:
1. Produces `O(n_keywords × len(text))` substring search complexity via Python `in` operator (string `__contains__`). For a 500-word segment and 30 keywords, this is 15,000 substring comparisons per classification call.
2. Is not language-aware. BB-PAXDATA processes multilingual content (Community 37 confirms `LanguageDetector` and `LanguageRouter` with Cyrillic fallback support). The English keyword list will produce zero matches on Turkish, Russian, or Arabic text.
3. Is not versioned. Adding a keyword requires a code change, not a configuration change.

**Proposed Resolution:** Move keyword vocabulary to a YAML/JSON configuration file loaded at `ServiceContainer` initialization time. Integrate with `LanguageRouter` to select language-specific keyword sets:
```python
# src/bb_paxdata/infrastructure/config/narrative_keywords.yaml
SYSTEM:
  en: ["world order", "international community", "multipolar", ...]
  tr: ["dünya düzeni", "uluslararası toplum", "çok kutuplu", ...]
  ru: ["мировой порядок", "международное сообщество", ...]
IDENTITY:
  en: ["national interest", "historic duty", ...]
  tr: ["ulusal çıkar", "tarihi görev", ...]
```
**Impact Assessment:** English-only keywords produce systematic zero-signal output on non-English transcripts, causing all non-English segments to fall through to the `NarrativeLayer.ISSUE` default (FINDING P-06). This is a high-severity correctness issue for multilingual corpora.

---

## SECTION 7: DEPENDENCY CHAIN VERIFICATION

### Required Pre-Conditions Before TASK-A05 Code Generation

| Dependency                                         | Status                                                                      | Verification Required                                                    |
| -------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `TASK-A01` (SRL — `ArgumentGraph`)                 | CONFIRMED: Community 40 (ArgumentGraph, 91 edges)                           | Verify `SRLFrame` field names accessed by A05 code                       |
| `TASK-A04` (SpeechAct — `SpeechActClassification`) | UNCONFIRMED: No community explicitly lists `SpeechActClassification` fields | Grep `src/bb_paxdata/domain/models/speech_act.py` for field declarations |
| `DiscourseFlow.narrative_*` fields                 | BLOCKED: Requires FINDING D-01 and D-02 resolutions                         | Migration must run before any A05 pipeline execution                     |
| `BilateralSentiment.narrative_*` fields            | BLOCKED: Requires FINDING P-01 resolution                                   | Schema update is critical-path                                           |
| `CrossAnomalyServiceImpl` interface                | CONFIRMED: Community 74                                                     | Verify `ContradictionResult` field schema before FINDING I-01 resolution |
| `Analysis` field schema                            | UNCONFIRMED: 157 INFERRED edges                                             | Source inspection mandatory (FINDING A-01)                               |
| `pytest-asyncio` configuration                     | UNCONFIRMED                                                                 | `pyproject.toml` inspection required                                     |

### Implementation Sequence Constraints

1. FINDING D-01 (Pydantic syntax fix) must be resolved before any model instantiation tests can pass.
2. FINDING P-01 (BilateralSentiment schema) must be resolved before FINDING I-01 (ContradictionResult) can be resolved, because `detect_narrative_clashes()` reads `narrative_layer` and `narrative_salience` from `BilateralSentiment` objects.
3. FINDING P-02 (`is_coercive`) must be resolved before `NarrativeSalienceTracker` is imported anywhere — module-level `AttributeError` propagates at import time if `SpeechActClassification.is_coercive` does not exist.
4. FINDING D-02 (idempotent migration) must be resolved and migration executed before integration tests that write to `discourse_flows` table can succeed.
5. FINDING P-06 (None return from classifier) is a precondition for correct FINDING I-01 resolution — if the classifier returns `None`, the anomaly detection must handle `narrative_layer=None` gracefully.

---

## SECTION 8: ACCURACY THRESHOLDS — OPERATIONALIZATION

The spec claims Recall ≥ 0.65, Precision ≥ 0.75 targets. These are asserted without:
1. A ground-truth evaluation dataset specification.
2. A definition of true/false positive for narrative layer classification (multi-label or single-label per segment?).
3. A confidence score threshold separating positive predictions from negative ones (the classifier always assigns a layer — precision/recall require a confidence threshold to compute).

**Proposed Resolution:** Before threshold claims can be validated:
```python
# Minimum evaluation harness required:
def evaluate_classifier(
    stage: NarrativeClassifierStage,
    gold_standard: list[tuple[str, NarrativeLayer]]  # (text, true_layer)
) -> dict[str, float]:
    tp = fp = fn = 0
    for text, true_layer in gold_standard:
        predicted = stage.classify_segment_layer(text)
        if predicted == true_layer:
            tp += 1
        elif predicted is not None and predicted != true_layer:
            fp += 1
            fn += 1
        else:  # predicted is None
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": 2*precision*recall/(precision+recall+1e-9)}
```
The gold standard dataset must be drawn from actual BB-PAXDATA panel transcripts with human-annotated narrative layers.

---

## SECTION 9: GRAPH-DERIVED RISK SIGNALS

Graph property `25% INFERRED edges at avg confidence 0.59` implies:
- 3793 edges in the dependency graph are model-reasoned, not code-extracted.
- Any architectural claim derived solely from the graph (e.g., "component X calls component Y") carries ~41% false positive risk.
- Findings in this report that rely on graph community membership (FINDING A-01, A-02, A-03, A-04) are directionally correct but require source code verification before implementation.

Community 850 in the graph contains `FINDING M-03` with embedded Python code snippets referencing `_detect_affect()` and `APPRECIATION_LEXICON` / `JUDGMENT`. This suggests a prior code audit exists within the codebase itself (possibly as an inline comment or documentation artifact). This finding should be retrieved and cross-referenced with TASK-A05 implementation scope to verify there is no lexicon overlap between the affect detection system and the narrative keyword classifier.

552 isolated graph nodes represent components with ≤1 documented connection. Before deploying `NarrativeClassifierStage` and `NarrativeSalienceTracker` as new service registrations in `ServiceContainer`, run `grep -r "NarrativeSalient\|NarrativeClassif\|NarrativeLayer" src/` to confirm no conflicting or partial implementations exist among isolated nodes.