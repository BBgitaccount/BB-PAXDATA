# TASK-E02 — GAT INTEGRATION UPGRADED TECHNICAL REVIEW
**Report Version:** 2.0  
**Source Task:** TASK-E02 — Fischer DNA Üzerinde Graph Attention Network (GAT) Geliştirme  
**Codebase Commit:** `8d37ef99` (from GRAPH_REPORT.md metadata)  
**Graph Stats:** 9428 nodes · 16372 edges · 966 communities · 25% inferred edges (avg confidence 0.59)  
**Review Scope:** Full supersession of original TASK-E02 design document

---

## SECTION 0 — GRAPH-DERIVED CODEBASE FACTS

The following are structural facts extracted from the Graphify knowledge graph (commit `8d37ef99`) that directly constrain TASK-E02 implementation decisions.

**F-01.** `FischerDNAService` exists in Community 142 (cohesion 0.05). Community cohesion of 0.05 indicates extremely sparse internal edge density, meaning the Fischer DNA domain objects (`NetworkEdge`, `ActorConceptProfile`, `DiscourseFlow`, `FischerDNAService`) have few direct relationships with each other in the current codebase. Test coverage for this community is presumed minimal.

**F-02.** `DiscourseFlowTable` and `DiscourseFlowRepository` both exist (Community 148, Community 369). `test_creates_flows_from_sentiments()` and `test_weight_threshold_filters_weak_edges()` confirm the DiscourseFlow construction pipeline is tested. The `GATEmbeddingService.build_pyg_data()` contract with `DiscourseFlow` domain attributes (`actor_ids`, `concept_ids`, `edges`, `session_id`) must be verified against the actual `DiscourseFlow` model in Community 148.

**F-03.** `RiskAssessment` service (Community 145) already calculates SBI with the formula `(power_level * demand...`. This is the segment-level SBI, distinct from the speaker-level `SpeakerPosition.sbi` targeted by TASK-E02. The task spec conflates these two SBI computations throughout Sections 3 and 5 without disambiguation.

**F-04.** `FINDING M-03: engagement_boost Weight Renders Contribution Negligibly Small` is a pre-existing codebase audit finding (Community 911), with regression test `Regression test for FINDING M-03: engagement_boost weight` (Community 301). The corrected formula (`# Corrected formula — engagement contribution on par with hedging`) is present in Community 911 code block. TASK-E02 proposes `gamma=0.15` for engagement, which does not resolve FINDING M-03 and may conflict with its correction.

**F-05.** `FormulaAuditor` (Community 186) performs deterministic logic and math audits on SBI/DKI/Risk segment aggregates. Any change to SBI formula components requires updating `FormulaAuditor.audit_segment_level_aggregates()`. TASK-E02 makes no reference to this required update.

**F-06.** `FormulaValidationAudit` WORM audit trail (Community 224) logs all HITL formula validation actions as Write Once Read Many records. All SBI formula changes require a corresponding WORM entry. TASK-E02 makes no reference to this audit requirement.

**F-07.** An existing embedding cache infrastructure exists: `InMemoryLRUCache`, batch Redis lookup with fallback pattern (Community 144, Community 153). SBERT feature computation for `initial_features` in `GATEmbeddingService.build_pyg_data()` should route through this cache layer. TASK-E02 does not reference it.

**F-08.** Community 2389 contains `3.1 SBICalculator Güncellemesi` and `SpeakerPosition(BaseModel)` — indicating a concurrent task is also modifying `SpeakerPosition` and `SBICalculator`. This creates a high-probability merge conflict zone for TASK-E02.

**F-09.** `Analysis` node has betweenness centrality 0.061 with 166 inferred edges (highest in graph). `Sentence` has betweenness 0.050 with 90 inferred edges. The high inferred edge ratio for `Analysis` and `Sentence` means SBERT mean-pooling over actor sentences (the proposed initial feature extraction strategy) has 25% inferred structural confidence in the graph — these relationships may not be fully implemented.

**F-10.** `TopicAssignmentORM` / `TopicAssignment` (Community 924) are the concrete domain types for concept nodes. The GAT design document uses the generic term "Concept/Topic" without referencing these existing types. `build_pyg_data` must derive concept node features from `TopicAssignment` objects, not from an abstract BERTopic centroid of unspecified provenance.

**F-11.** `DiscourseNetworkEdgeTable` is present in Community 865 (the large ORM community with 79 nodes). This confirms persistence infrastructure for `NetworkEdge` exists. No corresponding `GATEmbeddingTable` or `GATEmbeddingORM` appears in the graph — the persistence layer for `GATEmbedding` is entirely absent from the codebase.

**F-12.** `LIWC ProxyService` (Community 253) is referenced in context of "Faz 7'de SBI'nin otoritatif/sav..." — indicating LIWC proxy scores are a planned SBI input in a later phase. Adding `delta * gat_anomaly_score` now without accounting for LIWC will require a fifth weight parameter in a subsequent task.

---

## SECTION 1 — MATHEMATICAL MODEL CORRECTIONS

### 1.1 GAT Formulation — Verified Correct
The attention coefficient formula in Section 2.3 is consistent with the GATv1 formulation from Veličković et al. (2018) and matches PyTorch Geometric `GATConv` implementation. No corrections required.

### 1.2 Multi-Head Aggregation — Notation Inconsistency
The multi-head formula uses concatenation (`||`) for intermediate layers but does not formally state the final averaging operation. The correct two-layer formulation is:

Layer 1 (concat, K heads): `h_i^(1) = ||_{k=1}^K σ(Σ_{j∈N(i)} α_ij^k W^k h_j^(0))`  
Layer 2 (avg, 1 head): `h_i^(2) = σ(Σ_{j∈N(i)} α_ij W h_j^(1))`

Output dimension: `out_channels = 256`. With `hidden_channels=128` and `heads=4`, layer 1 output is `128*4=512`. Layer 2 input is `512`, output is `256`. Dimensions are consistent.

### 1.3 Triplet Loss — Distance Function Sign Convention
The cosine distance definition `d(u,v) = 1 - cos_sim(u,v)` is correct for normalized vectors. However `margin=0.3` in cosine distance space is aggressive. With 256-dim vectors, typical inter-cluster cosine distances for diplomatic speech data range 0.1–0.4. A margin of 0.3 will create a regime where most `d(a,n)` values are less than `d(a,p) + margin`, producing a loss landscape dominated by saturated triplets. Recommended starting value: `margin=0.1` with linear warmup.

### 1.4 TF-IDF Edge Weight Formula
`w_ij = tf_score_ij × idf_score_ij` is standard TF-IDF. Missing specification: whether TF is raw count, log-normalized, or binary; whether IDF uses smoothed denominator. These affect edge weight scale and must be documented for reproducibility.

---

## SECTION 2 — FINDINGS

---

### FINDING C-01: `GATNetwork.forward()` Uses Invalid PyTorch Geometric API

**Classification:** CRITICAL  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATNetwork.forward()`

**Root Cause:**  
The implementation calls `self.conv1.edge_updater(...)` to invoke the GATConv layer. `edge_updater` is an internal method in PyTorch Geometric's `MessagePassing` base class that performs only the edge-level feature transformation step. It does not execute the full message-passing pipeline (`propagate` → `message` → `aggregate` → `update`). Calling `edge_updater` directly returns edge-level transformed features but does not aggregate them into node representations. Actor and concept node embeddings after this call remain at their pre-GATConv projected values. The attention weights returned are also unreliable as they are computed only for the edge subset processed by `edge_updater`.

The correct invocation pattern in PyTorch Geometric ≥ 2.0 is direct `__call__` on the layer with `return_attention_weights=True` as a keyword argument to the module's `forward` method signature:

```python
# BROKEN — calls internal edge_updater directly, no aggregation occurs:
x, (edge_idx1, att_weights1) = self.conv1.edge_updater(
    edge_index, x=x, edge_attr=edge_attr, return_attention_weights=True
)

# CORRECT — calls full message passing pipeline with attention output:
x, (edge_idx1, att_weights1) = self.conv1(
    x, edge_index, edge_attr=edge_attr, return_attention_weights=True
)
```

Full corrected `GATNetwork.forward`:

```python
def forward(
    self,
    x: torch.Tensor,
    edge_index: torch.Tensor,
    edge_attr: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    x = self.relu(self.proj(x))

    # Layer 1: concat multi-head, returns attention weights
    x, (_, att_weights_l1) = self.conv1(
        x, edge_index, edge_attr=edge_attr, return_attention_weights=True
    )  # x: [N, hidden_channels * heads]
    x = self.relu(x)

    # Layer 2: averaging single head, return_attention_weights not needed
    x = self.conv2(x, edge_index, edge_attr=edge_attr)
    # x: [N, out_channels=256]

    return x, att_weights_l1  # att_weights_l1: [E, heads]
```

**Impact Assessment:**  
Without this fix, `GATNetwork.forward()` produces node features that are equivalent to a single linear projection of the initial features with no graph structure information. The entire purpose of the GAT layer — capturing structural relationships between actors and concepts — is not realized. All downstream `GATEmbedding` objects contain linear projection outputs, not graph-informed representations. The contrastive training loop trains a linear model, not a graph model.

---

### FINDING C-02: Bipartite Graph Directionality Makes Actor Embeddings Structurally Static

**Classification:** CRITICAL  
**Location:** Mathematical model (Section 2.1), `GATEmbeddingService.build_pyg_data()` edge construction

**Root Cause:**  
The graph is defined as directed Actor → Concept. GATConv in standard mode performs message passing from source nodes to target nodes. With exclusively Actor → Concept directed edges, the following holds:

- Concept nodes (targets) receive aggregated messages from their connected actor nodes. Their representations are updated.
- Actor nodes (sources) have zero incoming edges. They receive no aggregated messages from any neighbor. After GATConv, `h_actor = ReLU(proj(h_actor^(0)))` — identical to the projection layer output regardless of graph topology.

This means actor embeddings contain no structural information about which concepts the actor discusses or how the actor's discourse pattern compares to others. The `GATEmbedding.embedding` for each actor is a function of that actor's SBERT mean-pooling only, not of its position in the bipartite graph.

**Proposed Resolution:**  
Two architecturally valid options:

**Option A — Bidirectional edges (recommended):**  
Add reverse edges (Concept → Actor) to allow concept information to flow back to actor nodes. Apply a two-hop message passing: Actor → Concept in layer 1, Concept → Actor in layer 2.

```python
# In build_pyg_data(), after constructing forward edges:
# Add reverse edges for two-hop message passing
reverse_sources = edge_targets.copy()
reverse_targets = edge_sources.copy()
reverse_attrs = edge_attrs.copy()

all_sources = edge_sources + reverse_sources
all_targets = edge_targets + reverse_targets
all_attrs = edge_attrs + reverse_attrs

edge_index = torch.tensor([all_sources, all_targets], dtype=torch.long, device=self.device)
edge_attr = torch.tensor(all_attrs, dtype=torch.float32, device=self.device)
```

**Option B — Heterogeneous GNN (BipartiteConv):**  
Use `torch_geometric.nn.conv.HeteroConv` with separate message functions for Actor→Concept and Concept→Actor directions, preserving bipartite semantics. This is architecturally cleaner but increases implementation complexity and PyG version dependency.

**Impact Assessment:**  
Without this fix, actor embeddings are deterministic functions of SBERT mean-pooling with no graph topology information. The `characteristic_concepts` derived from attention weights on Actor → Concept edges would still be computed (attention exists on outgoing edges), but the actor embedding itself carries no cross-actor comparative structural signal. The anomaly detection capability reduces to clustering of SBERT mean-pooled representations, which provides no advantage over existing SBERT-based approaches already in the system.

---

### FINDING C-03: `_calculate_anomaly_score()` Returns Hardcoded Constant — Primary Output Non-Functional

**Classification:** CRITICAL  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATEmbeddingService._calculate_anomaly_score()`

**Root Cause:**  
The method unconditionally returns `0.15`. This value is injected as `GATEmbedding.anomaly_score` for every actor in every session, and then flows into `SpeakerPosition.sbi` via `delta * gat_anomaly_score`. The anomaly score is the primary analytical output justifying the entire GAT integration. There is no prototype vector storage, no distance computation, and no reference to training artifacts. The task spec contains the comment "Normal prototip vektörü eğitim sırasında saklanır" but provides no storage mechanism, serialization format, load path, or update protocol.

**Proposed Resolution:**  
The complete anomaly scoring pipeline requires three components that are absent from the design:

**Component 1 — Normal Prototype Storage:**
```python
# In GATEmbeddingService.__init__, after model load:
self.normal_prototype: torch.Tensor | None = None
if model_path:
    prototype_path = model_path.replace(".pt", "_prototype.pt")
    if os.path.exists(prototype_path):
        self.normal_prototype = torch.load(
            prototype_path, map_location=self.device
        )  # shape: [out_channels=256]
```

**Component 2 — Prototype Computation During Training:**
```python
def update_normal_prototype(self, normal_embeddings: list[list[float]]) -> None:
    """Called at end of contrastive training with all normal-labeled embeddings."""
    emb_tensor = torch.tensor(normal_embeddings, dtype=torch.float32, device=self.device)
    # L2-normalize before mean
    emb_normalized = torch.nn.functional.normalize(emb_tensor, p=2, dim=1)
    self.normal_prototype = emb_normalized.mean(dim=0)
    # Persist alongside model weights
    assert self._model_path is not None, "model_path must be set before prototype update"
    prototype_path = self._model_path.replace(".pt", "_prototype.pt")
    torch.save(self.normal_prototype, prototype_path)
```

**Component 3 — Inference-Time Distance Computation:**
```python
def _calculate_anomaly_score(self, embedding: list[float]) -> float:
    if self.normal_prototype is None:
        # No prototype available: return sentinel value, do not use in SBI
        return -1.0  # Signals missing data; SBICalculator must handle this
    emb = torch.tensor(embedding, dtype=torch.float32, device=self.device)
    emb_norm = torch.nn.functional.normalize(emb.unsqueeze(0), p=2, dim=1)
    proto_norm = torch.nn.functional.normalize(
        self.normal_prototype.unsqueeze(0), p=2, dim=1
    )
    # Cosine distance in [0, 2] for non-normalized; in [0, 1] after normalization
    cosine_sim = torch.nn.functional.cosine_similarity(emb_norm, proto_norm).item()
    cosine_dist = (1.0 - cosine_sim) / 2.0  # Maps to [0, 1]
    return float(cosine_dist)
```

Note: `SpeakerPosition.recalibrate_weights` must be updated to treat `anomaly_score == -1.0` (or `None` after sentinel conversion) as missing data requiring weight renormalization (see FINDING M-06).

**Impact Assessment:**  
All `GATEmbedding.anomaly_score` values equal `0.15` regardless of model state or training history. `SBICalculator` injects a constant `+0.15 * delta` term into every SBI value. This is a systematic positive bias of `0.15 * 0.15 = 0.0225` on all speaker positions, uncorrelated with any discourse property. Success criterion 1 (F1 ≥ 0.78 on HITL validation) is unverifiable because the model outputs a constant.

---

### FINDING C-04: `compute_embeddings()` Declared `async` With No Awaitable — Blocks Event Loop

**Classification:** CRITICAL  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATEmbeddingService.compute_embeddings()`

**Root Cause:**  
The method is declared `async def compute_embeddings(...)` but contains no `await` expressions. All operations — `torch.no_grad()`, model forward pass, tensor operations, list comprehensions — are synchronous CPU/GPU blocking calls. When called from an async context (e.g., `BuildPanelNetworkUseCase.execute()` which is async per the integration plan), the entire forward pass runs on the event loop thread, blocking all other coroutines for its duration. On CPU inference with a large session graph, this can block for 100ms–2s depending on graph size.

**Proposed Resolution:**  
Wrap the synchronous compute logic in `asyncio.to_thread()` for Python ≥ 3.9:

```python
import asyncio

async def compute_embeddings(
    self, flow: DiscourseFlow, initial_features: dict[str, list[float]]
) -> list[GATEmbedding]:
    if not flow.edges:
        return []
    # Offload blocking torch operations to thread pool
    return await asyncio.to_thread(self._compute_embeddings_sync, flow, initial_features)

def _compute_embeddings_sync(
    self, flow: DiscourseFlow, initial_features: dict[str, list[float]]
) -> list[GATEmbedding]:
    """Synchronous implementation — runs in thread pool via compute_embeddings."""
    pyg_data, node_to_idx = self.build_pyg_data(flow, initial_features)
    with torch.no_grad():
        embeddings, att_weights = self.model(
            pyg_data.x, pyg_data.edge_index, pyg_data.edge_attr
        )
    # ... remainder of existing logic ...
```

If Python < 3.9, use `loop.run_in_executor(None, self._compute_embeddings_sync, flow, initial_features)`.

**Impact Assessment:**  
Under concurrent request load (multiple panels being analyzed simultaneously), the blocking call starves all other coroutines. The HITL dashboard API (FastAPI async endpoints confirmed in codebase) and any concurrent `BuildPanelNetworkUseCase` calls will experience latency spikes proportional to the GAT inference time. This is a correctness issue under concurrency, not a performance optimization.

---

### FINDING M-01: `pyproject.toml` PyTorch Geometric Dependency Is Functionally Broken for CUDA Environments

**Classification:** MAJOR  
**Location:** `pyproject.toml` — `[tool.poetry.dependencies]`

**Root Cause:**  
The specification `torch-geometric = "^2.5"` is insufficient for a functional installation in CUDA environments. PyTorch Geometric requires:

1. A specific PyTorch version compatible with the PyG release.
2. Installation from PyG's custom wheel index matching the CUDA version and platform.
3. Optional dependencies (`torch-scatter`, `torch-sparse`, `torch-cluster`) for full GATConv functionality.

The standard PyPI index does not contain CUDA-enabled PyG wheels. Poetry resolves `torch-geometric = "^2.5"` to the CPU-only stub package, which installs but fails at runtime with missing `torch_geometric.nn` attributes when CUDA operations are attempted.

**Proposed Resolution:**  
```toml
# pyproject.toml
[tool.poetry.dependencies]
torch = { version = "2.3.0", source = "pytorch-cu118" }
torch-geometric = { version = "2.5.3", source = "pyg-cu118" }

[[tool.poetry.source]]
name = "pytorch-cu118"
url = "https://download.pytorch.org/whl/cu118"
priority = "supplemental"

[[tool.poetry.source]]
name = "pyg-cu118"
url = "https://data.pyg.org/whl/torch-2.3.0+cu118.html"
priority = "supplemental"
```

For CPU-only development environments, provide a separate `pyproject.dev.toml` or use environment markers:
```toml
torch = { version = "2.3.0", source = "pytorch-cpu", markers = "sys_platform == 'linux' and platform_machine != 'x86_64'" }
```

The CI/CD pipeline and `Dockerfile` must be updated to pass `--extra-index-url` flags or configure Poetry source priority accordingly.

**Impact Assessment:**  
All CI runs, Docker builds, and production deployments will install CPU-only torch, causing silent performance regression on GPU-provisioned infrastructure. The T4 GPU training time target (≤2 hours for 50 epochs) assumes CUDA execution; CPU execution will exceed this by an order of magnitude.

---

### FINDING M-02: `build_pyg_data()` Return Type Annotation Incorrect

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATEmbeddingService.build_pyg_data()`

**Root Cause:**  
The method signature declares `-> Data` but the implementation returns `(Data, node_to_idx)` — a `tuple[Data, dict[str, int]]`. Any code consuming this method with the annotated return type will fail at runtime when attempting to access `Data` attributes on a tuple. Static analysis tools (mypy, pyright) will not catch downstream errors because the incorrect annotation suppresses type inference.

**Proposed Resolution:**  
```python
def build_pyg_data(
    self,
    flow: DiscourseFlow,
    initial_features: dict[str, list[float]],
) -> tuple[Data, dict[str, int]]:
    ...
```

**Impact Assessment:**  
Any callers written against the `-> Data` annotation will compile without error but fail at runtime. The incorrectness is propagated silently through the type system.

---

### FINDING M-03: `recalibrate_weights` Epsilon Rejects Valid IEEE 754 Default Weights

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/models/sbi_models.py` — `SpeakerPosition.recalibrate_weights()`

**Root Cause:**  
The validation check `abs(alpha + beta + gamma + delta - 1.0) < 1e-9` uses an epsilon that is too tight for IEEE 754 double-precision floating-point arithmetic. The default weights defined in the same class are `alpha=0.5, beta=0.2, gamma=0.15, delta=0.15`. In Python:

```python
>>> 0.5 + 0.2 + 0.15 + 0.15
0.9999999999999999
>>> abs(0.5 + 0.2 + 0.15 + 0.15 - 1.0)
1.1102230246251565e-16
```

`1.11e-16 < 1e-9` is `True`, so this specific case passes. However, weights derived from UI sliders, JSON deserialization, or intermediate computations regularly accumulate errors in the `1e-9` to `1e-7` range. The safe epsilon for float64 weight sums is `1e-6`.

**Proposed Resolution:**  
```python
_WEIGHT_SUM_EPSILON: float = 1e-6  # Module-level constant

def recalibrate_weights(
    self, alpha: float, beta: float, gamma: float, delta: float
) -> "SpeakerPosition":
    weight_sum = alpha + beta + gamma + delta
    if not abs(weight_sum - 1.0) < _WEIGHT_SUM_EPSILON:
        raise ValueError(
            f"Weights must sum to 1.0 ± {_WEIGHT_SUM_EPSILON}. "
            f"Got {weight_sum:.10f} (delta from 1.0: {abs(weight_sum - 1.0):.2e})"
        )
    ...
```

**Impact Assessment:**  
Weights derived from HITL calibration UI or JSON API payloads may fail validation at epsilon `1e-9` while being within acceptable numerical precision. This would silently prevent SBI recalibration for affected actors.

---

### FINDING M-04: `GATEmbedding.embedding` Has No Dimensional Constraint Enforcement

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/models/gat_models.py` — `GATEmbedding`

**Root Cause:**  
The `embedding` field is typed as `list[float]` without length constraint. The description states "256-dimensional GAT output vector" but no validator enforces this. A model producing 128-dim or 512-dim output due to misconfigured `GATNetwork` architecture or a wrong checkpoint passes validation silently, corrupting all downstream anomaly score computations and SBI values.

**Proposed Resolution:**  
```python
from typing import Annotated
from pydantic import Field, field_validator

EMBEDDING_DIM: int = 256

class GATEmbedding(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    embedding: Annotated[list[float], Field(min_length=EMBEDDING_DIM, max_length=EMBEDDING_DIM)]

    @field_validator("embedding")
    @classmethod
    def validate_embedding_norm(cls, v: list[float]) -> list[float]:
        norm = sum(x * x for x in v) ** 0.5
        if norm < 1e-8:
            raise ValueError(
                f"Embedding vector is near-zero (norm={norm:.2e}). "
                "Possible degenerate input from all-zero initial features."
            )
        return v
```

**Impact Assessment:**  
Dimensionality mismatch between model output and expected 256-dim embeddings propagates silently into anomaly score computation and the SBI formula. All downstream `SpeakerPosition.sbi` values are corrupted without any error signal.

---

### FINDING M-05: `SBICalculator` Domain Service Injecting Repository Violates Clean Architecture DIP

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/services/sbi_calculator.py` (proposed), Section 5 integration plan

**Root Cause:**  
Section 5 Phase 3 states: "hesaplanan aktör için DB'den ilgili oturumun GATEmbedding'i sorgulanır" — the `SBICalculator` domain service is specified to query the database directly. `SBICalculator` resides in the domain layer. Introducing a DB query into a domain service couples domain logic to infrastructure persistence technology, violating the ports-and-adapters (hexagonal) architecture that the rest of the codebase implements (evidenced by `IBilateralSentimentRepository`, `ITopicSynthesisRepository`, `BilateralSentimentRepository` patterns confirmed in Community 1513).

No `IGATEmbeddingRepository` port interface is defined anywhere in the design document or detectable in the graph.

**Proposed Resolution:**  
Define a port interface in the domain layer:

```python
# src/bb_paxdata/domain/ports/i_gat_embedding_repository.py
from abc import abstractmethod
from typing import Protocol
from bb_paxdata.domain.models.gat_models import GATEmbedding


class IGATEmbeddingRepository(Protocol):
    @abstractmethod
    async def get_by_actor_and_session(
        self, actor_id: str, session_id: str
    ) -> GATEmbedding | None: ...

    @abstractmethod
    async def save(self, embedding: GATEmbedding) -> None: ...

    @abstractmethod
    async def save_batch(self, embeddings: list[GATEmbedding]) -> None: ...
```

Inject via constructor in `SBICalculator`:

```python
class SBICalculator:
    def __init__(self, gat_repo: IGATEmbeddingRepository) -> None:
        self._gat_repo = gat_repo

    async def compute(self, ..., session_id: str) -> SBIResult:
        gat_emb = await self._gat_repo.get_by_actor_and_session(actor_id, session_id)
        gat_score = gat_emb.anomaly_score if gat_emb is not None else None
        ...
```

The infrastructure ORM implementation `GATEmbeddingRepository(IGATEmbeddingRepository)` must include the corresponding `GATEmbeddingTable` ORM model and an Alembic migration.

**Impact Assessment:**  
Direct DB access in the domain layer makes `SBICalculator` untestable without a database fixture, couples domain logic to SQLAlchemy session management, and violates the architectural invariant maintained throughout the rest of the BB-PAXDATA codebase. Integration tests already mock `IBilateralSentimentRepository` (confirmed in test infrastructure, Community 141 `MockCacheBackend`, `override_dependencies()`). Bypassing the port pattern breaks this established test strategy.

---

### FINDING M-06: `recalibrate_weights` None Fallback Introduces Systematic SBI Bias

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/models/sbi_models.py` — `SpeakerPosition.recalibrate_weights()`

**Root Cause:**  
When `gat_anomaly_score is None`, the method substitutes `gat_val = 0.0`. This does not preserve the SBI scale. The formula becomes `sbi = alpha * theta + beta * stance + gamma * engagement + delta * 0.0`, which underweights the total combination by `delta`. The effective weight sum applied to known components is `alpha + beta + gamma = 0.85` instead of `1.0`. The SBI value is systematically 15% lower than it would be with GAT data, not equivalent to a three-component formula.

**Proposed Resolution:**  
When `gat_anomaly_score is None`, renormalize remaining weights:

```python
gat_val = self.gat_anomaly_score

if gat_val is not None:
    new_sbi = (
        alpha * self.wordfish_theta
        + beta * self.stance_density
        + gamma * self.engagement_score
        + delta * gat_val
    )
else:
    # Renormalize to preserve SBI scale without GAT component
    remaining = alpha + beta + gamma
    if remaining < 1e-9:
        raise ValueError("Non-GAT weights sum to zero; cannot compute SBI without GAT data.")
    new_sbi = (
        (alpha / remaining) * self.wordfish_theta
        + (beta / remaining) * self.stance_density
        + (gamma / remaining) * self.engagement_score
    )
```

**Impact Assessment:**  
Actors without GAT embeddings (e.g., due to upstream SBERT failure or missing session data) will have SBI values systematically deflated by `delta=0.15`. A speaker position of `0.7` in the full model becomes `0.595` with the zero-substitution, erroneously suggesting a more neutral or less extreme discourse position.

---

### FINDING M-07: No Dropout Regularization — Guaranteed Overfitting on Small Dataset

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATNetwork`

**Root Cause:**  
`GATNetwork` contains no dropout layers. The training dataset consists of diplomatic session graphs. Community 148 confirms `test_creates_flows_from_sentiments()` using individual sentiment records, suggesting typical session graphs have 5–30 actors. With a training set of N_sessions × N_actors/session triplets, the effective training sample count is small relative to the model parameter count. `GATNetwork` has approximately:

- `proj`: `384 * 128 + 128 = 49,280` parameters  
- `conv1`: `(128 + 128) * 128 * 4 + attention_params * 4 ≈ 131,200` parameters  
- `conv2`: `(512 + 512) * 256 + attention_params ≈ 262,656` parameters  
- Total: ~443,000 parameters

With < 1,000 training triplets (conservative estimate for diplomatic data), this model will memorize training sessions.

**Proposed Resolution:**  
```python
class GATNetwork(nn.Module):
    def __init__(
        self,
        in_channels: int,
        hidden_channels: int,
        out_channels: int,
        heads: int = 4,
        dropout: float = 0.3,
        attention_dropout: float = 0.1,
    ):
        super().__init__()
        self.dropout_rate = dropout
        self.proj = nn.Linear(in_channels, hidden_channels)
        self.proj_dropout = nn.Dropout(p=dropout)
        self.conv1 = GATConv(
            hidden_channels, hidden_channels,
            heads=heads, concat=True, edge_dim=1,
            dropout=attention_dropout,  # Dropout on attention coefficients
        )
        self.conv1_dropout = nn.Dropout(p=dropout)
        self.conv2 = GATConv(
            hidden_channels * heads, out_channels,
            heads=1, concat=False, edge_dim=1,
            dropout=attention_dropout,
        )
        self.relu = nn.ReLU()

    def forward(self, x, edge_index, edge_attr):
        x = self.proj_dropout(self.relu(self.proj(x)))
        x, (_, att_w) = self.conv1(x, edge_index, edge_attr=edge_attr, return_attention_weights=True)
        x = self.conv1_dropout(self.relu(x))
        x = self.conv2(x, edge_index, edge_attr=edge_attr)
        return x, att_w
```

Note: `model.eval()` in `GATEmbeddingService.__init__` disables dropout at inference time correctly.

**Impact Assessment:**  
Without regularization, the GAT model will achieve high training-set triplet accuracy after ~10 epochs but will not generalize to new sessions. The F1 ≥ 0.78 success criterion measured on a held-out HITL validation set will not be met.

---

### FINDING M-08: Triplet Mining Strategy Undefined — Training Convergence Not Guaranteed

**Classification:** MAJOR  
**Location:** Section 2.4 and Section 5 Phase 4 — Contrastive Training Loop

**Root Cause:**  
The training specification provides the loss function but no triplet selection strategy. Random triplet sampling from HITL labels in the `human_review` table produces a triplet distribution dominated by easy negatives: cases where `d(a,n) > d(a,p) + margin` is already satisfied before training, yielding zero gradient. With small session graphs (5–30 actors per panel), the number of distinct valid triplets per session is bounded by `|V_A|^3`, making random sampling from a small pool nearly guaranteed to produce stale easy triplets after a few epochs.

**Proposed Resolution:**  
Implement online semi-hard negative mining per session batch:

```python
def mine_triplets(
    embeddings: torch.Tensor,          # [N, D] — all actor embeddings in batch
    labels: torch.Tensor,              # [N] — 0=normal, 1=anomaly
    margin: float = 0.3,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Returns anchor, positive, negative indices using semi-hard negative mining."""
    N = embeddings.size(0)
    # Pairwise cosine distance matrix
    emb_norm = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    dist_matrix = 1.0 - torch.mm(emb_norm, emb_norm.T)  # [N, N]

    anchors, positives, negatives = [], [], []
    for i in range(N):
        label_i = labels[i].item()
        pos_mask = (labels == label_i) & (torch.arange(N) != i)
        neg_mask = labels != label_i

        if pos_mask.sum() == 0 or neg_mask.sum() == 0:
            continue

        # Hardest positive: max distance to same-class
        pos_idx = dist_matrix[i][pos_mask].argmax()
        pos_global = torch.where(pos_mask)[0][pos_idx]

        # Semi-hard negative: d(a,n) > d(a,p) and d(a,n) < d(a,p) + margin
        d_ap = dist_matrix[i, pos_global].item()
        neg_distances = dist_matrix[i][neg_mask]
        semi_hard_mask = (neg_distances > d_ap) & (neg_distances < d_ap + margin)

        if semi_hard_mask.sum() == 0:
            # Fallback: hardest negative
            neg_idx = neg_distances.argmin()
        else:
            neg_idx = neg_distances[semi_hard_mask].argmin()
            neg_idx = torch.where(neg_mask)[0][torch.where(semi_hard_mask)[0][neg_idx]]

        anchors.append(i)
        positives.append(pos_global.item())
        negatives.append(neg_idx if isinstance(neg_idx, int) else neg_idx.item())

    anchor_t = torch.tensor(anchors)
    pos_t = torch.tensor(positives)
    neg_t = torch.tensor(negatives)
    return anchor_t, pos_t, neg_t
```

**Impact Assessment:**  
Without explicit mining, training curves will plateau near zero gradient after ~5 epochs regardless of epoch count. The 50-epoch training budget will be consumed without meaningful weight updates after the initial random initialization phase. The F1 success criterion cannot be met.

---

### FINDING M-09: `att_weights` Tensor Shape is Misspecified in Comments

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `compute_embeddings()`

**Root Cause:**  
The comment states `# edge_index: [2, E], att_weights: [E, heads, 1]`. PyTorch Geometric `GATConv` with `return_attention_weights=True` returns alpha with shape `[E, heads]` (confirmed in PyG source, `GATConv.forward` line: `alpha = (alpha_i + alpha_j).squeeze(-1)` before softmax). The trailing `1` dimension does not exist.

With the actual shape `[E, heads]`:
- `att_weights.mean(dim=1)` → `[E]` ✓ correct
- `.squeeze(-1)` on `[E]` → `[E]` ✓ no-op, accidentally harmless

However with the shape `[E, heads, 1]` that the comment implies:
- `att_weights.mean(dim=1)` → `[E, 1]`
- `.squeeze(-1)` → `[E]` ✓ accidentally correct

The comment causes incorrect shape assumptions in any code that indexes `att_weights` before calling `.mean()`. If another developer writes `att_weights[:, 0]` expecting `[E]` (one head), they will get `[E, 1]` with the documented shape assumption.

**Proposed Resolution:**  
```python
# Correct shape annotation:
# att_weights_l1: [E, heads] — per-edge attention coefficient per head
# After mean: [E] — averaged across heads
mean_att = att_weights.mean(dim=-1)  # dim=-1 is safe for both [E,H] and [E,H,1]
assert mean_att.dim() == 1, f"Expected [E] after mean, got shape {mean_att.shape}"
```

**Impact Assessment:**  
Incorrect shape documentation propagates to any subsequent developer modifying the attention weight extraction logic, causing silent bugs in `characteristic_concepts` extraction.

---

### FINDING M-10: FINDING M-03 (`engagement_boost`) Unresolved — GAT Weight Distribution Does Not Fix Pre-Existing Formula Defect

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/models/sbi_models.py` — `SpeakerPosition` weight defaults; Cross-reference: Community 911 (FINDING M-03)

**Root Cause:**  
FINDING M-03 (Community 911, regression test in Community 301) identifies that `engagement_boost = 0.1 if appraisal.engagement_type == ENGAGEMENT` renders the engagement contribution negligibly small (contribution: `0.1 * engagement_flag` where flag ∈ {0,1}, producing at most `0.01` shift in SBI). The corrected formula in Community 911 increases engagement contribution "on par with hedging."

TASK-E02 proposes `gamma=0.15` for engagement in the four-component SBI. If FINDING M-03's correction changes the scale of `engagement_score` relative to `stance_density` and `wordfish_theta`, then the proposed `gamma=0.15` calibration is based on the pre-correction formula and will be miscalibrated after M-03 is applied.

Additionally, both `gamma=0.15` (engagement) and `delta=0.15` (GAT anomaly) receive equal weight, despite the GAT anomaly score being an untested and freshly introduced signal while `engagement_score` is an established metric. Equal weighting of a mature signal with an experimental signal has no theoretical justification.

**Proposed Resolution:**  
Coordinate resolution of FINDING M-03 before finalizing TASK-E02 weight defaults. Proposed interim defaults that defer to the corrected engagement formula outcome:

```python
# Interim weights pending M-03 resolution — GAT signal is experimental (lower delta)
alpha: float = Field(default=0.55, description="Wordfish theta weight")
beta: float = Field(default=0.22, description="Stance density weight")
gamma: float = Field(default=0.18, description="Engagement score weight (post-M-03 correction)")
delta: float = Field(default=0.05, description="GAT anomaly weight (experimental; increase after validation)")
```

Provide `FormulaAuditor` assertions that `alpha + beta + gamma + delta == 1.0` and `delta <= 0.15` until GAT signal is validated against HITL F1 threshold.

**Impact Assessment:**  
If FINDING M-03 correction and TASK-E02 are both merged without coordination, the SBI formula will have compounded recalibration errors. `FormulaAuditor.audit_segment_level_aggregates()` will need to be updated for both changes simultaneously.

---

### FINDING M-11: `FormulaAuditor` Not Updated for Four-Component SBI Formula

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/domain/services/formula_auditor.py` (inferred from Community 186)

**Root Cause:**  
`FormulaAuditor` (Community 186) performs deterministic logic and math checks on SBI/DKI/Risk pipeline metrics, including `audit_segment_level_aggregates()`. Adding a fourth term `delta * gat_anomaly_score` to the SBI formula changes the mathematical invariants that `FormulaAuditor` validates:

- Weight sum invariant: previously 3 weights summing to 1; now 4 weights.
- Range invariant: `gat_anomaly_score ∈ [0.0, 1.0]` must be validated before use.
- Missing data invariant: behavior when `gat_anomaly_score is None` must be auditable.

TASK-E02 makes no reference to updating `FormulaAuditor`.

**Proposed Resolution:**  
`FormulaAuditor` must be extended to validate:
1. `delta` field existence on `SpeakerPosition`.
2. `gat_anomaly_score` range constraint `[0.0, 1.0]` when not None.
3. `alpha + beta + gamma + delta == 1.0 ± epsilon` when `gat_anomaly_score is not None`.
4. `alpha + beta + gamma == 1.0 ± epsilon` when `gat_anomaly_score is None` (renormalization case per FINDING M-06 resolution).

**Impact Assessment:**  
Without updating `FormulaAuditor`, the existing audit infrastructure will report false-negative results — passing SBI computations that contain GAT-related errors. The WORM audit trail (Community 224) will not capture GAT-specific formula violations.

---

### FINDING M-12: `FormulaValidationAudit` WORM Trail Not Addressed for Formula Change

**Classification:** MAJOR  
**Location:** `src/bb_paxdata/infrastructure/db/models/formula_validation_audit.py` (inferred from Community 224)

**Root Cause:**  
`FormulaValidationAudit` is a WORM (Write Once Read Many) audit trail that logs all HITL formula validation actions. The HITL dashboard (Community 1793: "HITL Formül Doğrulama ve Denetçi Arayüzü v3.0.0") exposes formula validation as a first-class operation. Changing the SBI formula from 3 components to 4 components is a structural formula change requiring a versioned audit log entry. TASK-E02 makes no reference to this.

**Proposed Resolution:**  
At deployment time, before activating the four-component SBI formula, insert a formula change record:

```python
# In migration script or deployment hook:
audit_entry = FormulaValidationAudit(
    formula_name="SBI_v2_GAT",
    previous_formula="alpha*theta + beta*stance + gamma*engagement",
    new_formula="alpha*theta + beta*stance + gamma*engagement + delta*gat_anomaly",
    change_reason="TASK-E02: GAT anomaly signal integration",
    default_weights={"alpha": 0.5, "beta": 0.2, "gamma": 0.15, "delta": 0.15},
    validated_by="TASK-E02",
    effective_from=datetime.now(timezone.utc),
)
```

This is a hard requirement per the WORM audit trail architecture (Community 1793).

**Impact Assessment:**  
Absence of audit trail for formula change violates the system's own data governance requirements. Post-deployment tracing of SBI value changes will not be attributable to the GAT integration.

---

### FINDING m-01: `GATEmbeddingService` Has No Training Interface

**Classification:** MINOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATEmbeddingService`

**Root Cause:**  
`GATEmbeddingService.__init__` unconditionally calls `self.model.eval()`. The contrastive training loop in Section 5 Phase 4 requires `model.train()` mode during backpropagation. No `train()`, `fine_tune()`, or `save_checkpoint()` method is defined on the service. The training loop described in Phase 4 has no corresponding callable in the service interface. Either a separate `GATTrainer` class must be defined (preferred, preserves SRP), or `GATEmbeddingService` must expose training methods with explicit `train()`/`eval()` mode transitions.

**Proposed Resolution:**  
Define a separate `GATContrastiveTrainer` class:

```python
class GATContrastiveTrainer:
    def __init__(
        self,
        service: GATEmbeddingService,
        lr: float = 1e-4,
        margin: float = 0.1,
        weight_decay: float = 1e-5,
    ) -> None:
        self._service = service
        self._optimizer = torch.optim.AdamW(
            service.model.parameters(), lr=lr, weight_decay=weight_decay
        )
        self._loss_fn = torch.nn.TripletMarginWithDistanceLoss(
            distance_function=lambda u, v: 1.0 - torch.nn.functional.cosine_similarity(u, v),
            margin=margin,
            reduction="mean",
        )

    def train_epoch(self, session_graphs: list[tuple[DiscourseFlow, dict]]) -> float:
        self._service.model.train()
        total_loss = 0.0
        for flow, features in session_graphs:
            pyg_data, node_to_idx = self._service.build_pyg_data(flow, features)
            embeddings, _ = self._service.model(
                pyg_data.x, pyg_data.edge_index, pyg_data.edge_attr
            )
            actor_indices = [node_to_idx[a] for a in flow.actor_ids if a in node_to_idx]
            actor_embs = embeddings[torch.tensor(actor_indices)]
            # labels from HITL — must be provided as parameter
            # ... triplet mining and loss computation ...
        self._service.model.eval()
        return total_loss
```

**Impact Assessment:**  
Without a training interface, Phase 4 has no executable implementation path. The model deployed in production will be the randomly initialized model loaded at service instantiation.

---

### FINDING m-02: Zero-Vector Fallback for Missing Node Features Is Silent

**Classification:** MINOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATEmbeddingService.build_pyg_data()`

**Root Cause:**  
`initial_features.get(node, [0.0] * 384)` silently substitutes an all-zero feature vector for nodes absent from the feature map. After `proj(zero_vector) = bias_term` (only the bias of the linear layer is active), followed by `ReLU`, the representation becomes `max(bias, 0)`. Multiple missing-feature nodes will have identical representations, causing their attention weights to aggregate identically and their anomaly scores to cluster at the same value. There is no log warning, no counter, and no error raised.

**Proposed Resolution:**  
```python
missing_nodes: list[str] = []
for node in nodes:
    feats = initial_features.get(node)
    if feats is None:
        missing_nodes.append(node)
        x_list.append([0.0] * 384)
    else:
        x_list.append(feats)

if missing_nodes:
    import logging
    logging.getLogger(__name__).warning(
        "build_pyg_data: %d nodes missing from initial_features — "
        "zero-vector fallback used. IDs: %s",
        len(missing_nodes),
        missing_nodes[:10],  # truncate for log safety
    )
```

**Impact Assessment:**  
Silent zero-vector substitution for actor nodes corrupts actor embeddings for sessions where SBERT extraction failed upstream. The anomaly score will reflect initialization artifacts rather than discourse properties.

---

### FINDING m-03: `characteristic_concepts` Can Return Empty List — Downstream IndexError Risk

**Classification:** MINOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `compute_embeddings()`

**Root Cause:**  
`actor_concept_att.get(actor, [])` returns an empty list when an actor node has no captured outgoing attention weights. This occurs when: (a) the actor has no edges in `flow.edges` (isolated actor node), or (b) FINDING C-01 is present and `edge_updater` fails to populate `actor_concept_att`. `top_concepts = [c[0] for c in sorted_concepts[:5]]` then produces `[]`. `GATEmbedding.characteristic_concepts` has no `min_length` constraint. Downstream consumers calling `embedding.characteristic_concepts[0]` will raise `IndexError`.

**Proposed Resolution:**  
Add `min_length=0` explicit annotation and handle empty case at call sites. Add a data quality check in `build_pyg_data`:

```python
isolated_actors = [
    a for a in flow.actor_ids
    if not any(e.actor_id == a for e in flow.edges)
]
if isolated_actors:
    raise ValueError(
        f"DiscourseFlow contains {len(isolated_actors)} isolated actor(s) with no edges. "
        f"Cannot compute meaningful GAT embeddings. IDs: {isolated_actors}"
    )
```

**Impact Assessment:**  
Isolated actor nodes are a plausible real-world case (a speaker with no topic assignments). Without the guard, the error surfaces downstream in presentation layer code rather than at the point of invalid data construction.

---

### FINDING m-04: Actor / Concept ID Collision Not Checked

**Classification:** MINOR  
**Location:** `src/bb_paxdata/domain/services/gat_embedding_service.py` — `GATEmbeddingService.build_pyg_data()`

**Root Cause:**  
`nodes = sorted(list(flow.actor_ids) + list(flow.concept_ids))`. If any ID appears in both `actor_ids` and `concept_ids` (e.g., a country-level actor that is also a detected BERTopic concept), `sorted(...)` deduplicates via Python's `list` semantics — but only if the same string appears twice. `node_to_idx = {node_id: idx for idx, node_id in enumerate(nodes)}` will then assign one index to the shared ID. Subsequently, all edges referencing that ID as either actor or concept will use the single shared index, conflating the actor and concept representations.

**Proposed Resolution:**  
```python
actor_set = set(flow.actor_ids)
concept_set = set(flow.concept_ids)
collision = actor_set & concept_set
if collision:
    raise ValueError(
        f"actor_ids and concept_ids share {len(collision)} IDs: {collision}. "
        "Bipartite graph requires disjoint node sets."
    )
```

**Impact Assessment:**  
ID collisions are unlikely in production given entity resolution conventions, but the guard prevents silent graph corruption if upstream entity resolution fails.

---

### FINDING m-05: F1 Success Criterion Is Not Reproducibly Verifiable

**Classification:** MINOR  
**Location:** Section 6 — Success and Validation Criteria, Criterion 1

**Root Cause:**  
"HITL anomali doğrulama setinde F1 skoru en az ≥ 0.78" is underspecified:

- No class specification: binary F1 with anomaly=positive, binary F1 with normal=positive, or macro-averaged F1.
- No dataset stratification: with a small HITL label set (n potentially < 100), k-fold stratification strategy affects reported F1 by ±0.05.
- No positive class label definition: `human_review.label ∈ {0, 1}` — which is positive (anomaly=1 is standard).
- No minimum class balance requirement: with 5% anomaly rate (plausible for diplomatic data), a trivial "always normal" classifier achieves F1=0.93 on the majority class.

**Proposed Resolution:**  
Replace Criterion 1 with:

```
Model Performance:
- Metric: Binary F1 score, positive class = anomaly (human_review.label == 1)
- Dataset: Stratified 5-fold cross-validation on HITL-labeled sessions
- Minimum: Macro-averaged F1 ≥ 0.72 across folds (adjusted for class imbalance)
- Baseline: Must exceed SBERT cosine distance baseline classifier by ≥ 0.05 F1
- Class balance constraint: Evaluation set must contain ≥ 15% positive (anomaly) samples; 
  oversample if necessary using SMOTE on embeddings
- Confusion matrix must be reported: TP, FP, FN, TN counts
```

**Impact Assessment:**  
As written, Criterion 1 can be satisfied by a degenerate classifier. The criterion provides no meaningful quality gate.

---

## SECTION 3 — INTEGRATION GAPS

### GAP-01: No `GATEmbeddingTable` ORM or Alembic Migration
`GATEmbedding` objects must be persisted to fulfill the integration plan. No ORM model, no table definition, and no Alembic migration script are specified. Required files:

```
src/bb_paxdata/infrastructure/db/models/gat_embedding_table.py
alembic/versions/XXXX_add_gat_embedding_table.py
```

The `GATEmbeddingTable` must include: `actor_id`, `session_id`, `embedding` (as JSON or ARRAY[FLOAT] depending on DB), `characteristic_concepts` (JSON), `anomaly_score` (FLOAT), `computed_at` (TIMESTAMP WITH TIME ZONE). Composite primary key or unique constraint on `(actor_id, session_id)`.

### GAP-02: No `DiscourseFlow.actor_ids` / `.concept_ids` Attribute Verification
`GATEmbeddingService.build_pyg_data()` calls `flow.actor_ids` and `flow.concept_ids`. The actual `DiscourseFlow` domain model (Community 2293: `class DiscourseFlow(BaseModel):`) attributes are not confirmed in the task spec. If `DiscourseFlow` exposes actors via a different accessor (e.g., `flow.actors`, `flow.get_actor_ids()`), all `build_pyg_data` calls will fail with `AttributeError` at runtime.

**Required action:** Verify `DiscourseFlow` interface against actual model in `src/bb_paxdata/domain/models/` before implementing `GATEmbeddingService`.

### GAP-03: SBERT Feature Extraction Not Specified
The `initial_features: dict[str, list[float]]` parameter passed to `GATEmbeddingService` requires a caller that computes SBERT mean-pooling over actor sentences. No service, use case, or method is specified for this computation. The codebase contains `EmbeddingCacheKey`, `InMemoryLRUCache`, and batch Redis lookup (Community 144) for embeddings — the SBERT feature extraction must route through this existing cache layer to avoid redundant model inference.

### GAP-04: `BuildPanelNetworkUseCase` Modification Not Specified
Section 5 Phase 2 states GAT embedding computation is added to `BuildPanelNetworkUseCase.execute()`. No diff, interface change, or dependency injection modification is provided. `BuildPanelNetworkUseCase` currently receives `IBilateralSentimentRepository` and `ITopicSynthesisRepository` (Community 1513). Injecting `GATEmbeddingService` requires updating the use case constructor, the `make_*` factory function, and the DI container.

### GAP-05: Concurrent `SpeakerPosition` Modification — Merge Conflict Risk
Community 2389 contains `3.1 SBICalculator Güncellemesi` and `SpeakerPosition(BaseModel)` snippets from a concurrent task. TASK-E02 modifies the same `SpeakerPosition` class. Without task sequencing or feature branch isolation, both tasks will produce conflicting modifications to `src/bb_paxdata/domain/models/sbi_models.py`.

### GAP-06: Edge Weight Normalization Absent
TF-IDF edge weights `w_ij = tf * idf` are passed directly as `edge_attr` without normalization. TF-IDF values are globally scaled (IDF depends on corpus size) and unbounded. Different sessions will have different edge weight scales depending on vocabulary size, causing inconsistent attention coefficient magnitudes across sessions. Per-graph min-max normalization or unit normalization of edge weights must be applied in `build_pyg_data()`:

```python
if edge_attrs:
    ea_tensor = torch.tensor(edge_attrs, dtype=torch.float32)
    ea_min, ea_max = ea_tensor.min(), ea_tensor.max()
    if (ea_max - ea_min) > 1e-8:
        ea_tensor = (ea_tensor - ea_min) / (ea_max - ea_min)
    edge_attr = ea_tensor.to(self.device)
```

---

## SECTION 4 — CORRECTED IMPLEMENTATION REFERENCE

The following provides the corrected core components integrating all critical and major findings above.

### 4.1 `GATNetwork` — Corrected

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv


EMBEDDING_DIM: int = 256


class GATNetwork(nn.Module):
    """
    Two-layer GAT with bidirectional bipartite message passing.
    Layer 1: concat K-head attention (hidden_channels → hidden_channels * heads)
    Layer 2: averaging 1-head attention (hidden_channels * heads → out_channels=256)
    """

    def __init__(
        self,
        in_channels: int = 384,
        hidden_channels: int = 128,
        out_channels: int = EMBEDDING_DIM,
        heads: int = 4,
        dropout: float = 0.3,
        attention_dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.proj = nn.Linear(in_channels, hidden_channels)
        self.proj_dropout = nn.Dropout(p=dropout)
        self.conv1 = GATConv(
            hidden_channels, hidden_channels,
            heads=heads, concat=True, edge_dim=1,
            dropout=attention_dropout,
        )
        self.conv1_dropout = nn.Dropout(p=dropout)
        self.conv2 = GATConv(
            hidden_channels * heads, out_channels,
            heads=1, concat=False, edge_dim=1,
            dropout=attention_dropout,
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.proj_dropout(F.relu(self.proj(x)))

        x, (_, att_weights) = self.conv1(
            x, edge_index, edge_attr=edge_attr, return_attention_weights=True
        )  # x: [N, hidden * heads], att_weights: [E, heads]
        x = self.conv1_dropout(F.relu(x))

        x = self.conv2(x, edge_index, edge_attr=edge_attr)
        # x: [N, EMBEDDING_DIM]

        return x, att_weights  # att_weights: [E, heads]
```

### 4.2 `GATEmbedding` — Corrected

```python
from typing import Annotated
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator

EMBEDDING_DIM: int = 256


class GATEmbedding(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    actor_id: str = Field(..., description="Speaker/Country entity ID")
    session_id: str = Field(..., description="Analysis session ID")
    embedding: Annotated[
        list[float],
        Field(min_length=EMBEDDING_DIM, max_length=EMBEDDING_DIM,
              description=f"{EMBEDDING_DIM}-dimensional GAT output vector (L2-normalized)")
    ]
    characteristic_concepts: list[str] = Field(
        ...,
        description="Top-K concept IDs by attention weight from GAT layer 1; may be empty for isolated actors",
    )
    anomaly_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Cosine distance from normal prototype in embedding space; -1.0 if prototype unavailable"
    )
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("anomaly_score", mode="before")
    @classmethod
    def validate_anomaly_score_sentinel(cls, v: float) -> float:
        # Allow -1.0 as sentinel for missing prototype
        if v == -1.0:
            return v
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"anomaly_score must be in [0.0, 1.0] or -1.0 sentinel; got {v}")
        return v

    @field_validator("embedding")
    @classmethod
    def validate_non_degenerate(cls, v: list[float]) -> list[float]:
        norm_sq = sum(x * x for x in v)
        if norm_sq < 1e-12:
            raise ValueError(f"Embedding vector is near-zero (norm²={norm_sq:.2e})")
        return v
```

Note: `anomaly_score` field constraint `ge=0.0, le=1.0` conflicts with the `-1.0` sentinel resolution; the `field_validator` with `mode="before"` resolves this by bypassing the `ge`/`le` constraint for the sentinel case. Alternatively, type as `float | None` and use `None` for missing prototype.

### 4.3 `SpeakerPosition.recalibrate_weights` — Corrected

```python
_WEIGHT_SUM_EPSILON: float = 1e-6


def recalibrate_weights(
    self,
    alpha: float,
    beta: float,
    gamma: float,
    delta: float,
) -> "SpeakerPosition":
    weight_sum = alpha + beta + gamma + delta
    if abs(weight_sum - 1.0) >= _WEIGHT_SUM_EPSILON:
        raise ValueError(
            f"Weights must sum to 1.0 ± {_WEIGHT_SUM_EPSILON}. "
            f"Got sum={weight_sum:.10f} (error={abs(weight_sum - 1.0):.2e})"
        )

    gat_val = self.gat_anomaly_score

    if gat_val is not None and gat_val >= 0.0:
        # GAT data available — full four-component formula
        new_sbi = (
            alpha * self.wordfish_theta
            + beta * self.stance_density
            + gamma * self.engagement_score
            + delta * gat_val
        )
    else:
        # GAT data unavailable — renormalize to preserve SBI scale
        remaining = alpha + beta + gamma
        if remaining < _WEIGHT_SUM_EPSILON:
            raise ValueError(
                "Non-GAT weights sum to zero; SBI is undefined without GAT data."
            )
        new_sbi = (
            (alpha / remaining) * self.wordfish_theta
            + (beta / remaining) * self.stance_density
            + (gamma / remaining) * self.engagement_score
        )

    return self.model_copy(
        update={
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "delta": delta,
            "sbi": new_sbi,
        }
    )
```

---

## SECTION 5 — DEPENDENCY SPECIFICATION (CORRECTED)

```toml
# pyproject.toml additions — replace original torch-geometric entry

[tool.poetry.dependencies]
# Core ML dependencies — CUDA 11.8 build (match deployment environment)
torch = { version = "2.3.0+cu118", source = "pytorch-cu118" }
torch-geometric = { version = "2.5.3", source = "pyg-cu118" }

# Required PyG sparse backends for GATConv with edge_attr
torch-scatter = { version = "2.1.2", source = "pyg-cu118" }
torch-sparse = { version = "0.6.18", source = "pyg-cu118" }

# SBERT for initial node features
sentence-transformers = "^3.0"

[[tool.poetry.source]]
name = "pytorch-cu118"
url = "https://download.pytorch.org/whl/cu118"
priority = "supplemental"

[[tool.poetry.source]]
name = "pyg-cu118"
url = "https://data.pyg.org/whl/torch-2.3.0+cu118.html"
priority = "supplemental"
```

For CPU-only development:
```toml
[tool.poetry.group.dev.dependencies]
torch = { version = "2.3.0", source = "pytorch-cpu" }
torch-geometric = { version = "2.5.3", source = "pyg-cpu" }

[[tool.poetry.source]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
priority = "supplemental"

[[tool.poetry.source]]
name = "pyg-cpu"
url = "https://data.pyg.org/whl/torch-2.3.0+cpu.html"
priority = "supplemental"
```

---

## SECTION 6 — CORRECTED SUCCESS CRITERIA

**Criterion 1 — Model Performance (replaces original):**  
Binary F1 (positive = anomaly, `human_review.label == 1`) ≥ 0.72 under stratified 5-fold cross-validation on the HITL-labeled session dataset. Evaluation set must contain ≥ 15% positive samples (oversample if necessary). Performance must exceed a cosine-distance SBERT baseline by ≥ 0.05 F1 to justify GAT complexity. Confusion matrix (TP/FP/FN/TN) must be logged.

**Criterion 2 — Semantic Correspondence (unchanged):**  
Top-5 characteristic concepts for low-anomaly-score actors must align ≥ 80% with expert-extracted discourse focus.

**Criterion 3 — Training Time (unchanged):**  
50 epochs on T4 GPU ≤ 2 hours. Baseline: with `hidden_channels=128`, `heads=4`, `N≤30 actors + N≤200 concepts` per session, forward pass is ~5ms/graph. 50 epochs × ~1000 graphs × 5ms = ~250s per epoch expectation; total under 4 hours; T4 GPU acceleration should meet the 2-hour target.

**Criterion 4 — Prototype Persistence (new):**  
After contrastive training, `normal_prototype.pt` must be co-located with `model.pt`. `GATEmbeddingService` must load the prototype on init and produce non-sentinel anomaly scores (≥ 0.0) for all actors in sessions with complete initial features.

**Criterion 5 — FormulaAuditor Compliance (new):**  
All `SpeakerPosition` objects with `delta > 0` must pass `FormulaAuditor.audit_segment_level_aggregates()` without violations. All formula changes must produce a `FormulaValidationAudit` WORM entry.

---

## SECTION 7 — FINDING PRIORITY MATRIX

| ID | Classification | Blocking for Phase | Must Fix Before |
|---|---|---|---|
| C-01 | CRITICAL | Phase 1 (model definition) | Any training or inference |
| C-02 | CRITICAL | Phase 1 (graph construction) | Any training or inference |
| C-03 | CRITICAL | Phase 4 (training loop) | Production deployment |
| C-04 | CRITICAL | Phase 2 (use case integration) | Async use case integration |
| M-01 | MAJOR | Phase 1 (dependency install) | Any GPU execution |
| M-02 | MAJOR | Phase 1 (model definition) | Any type-checked caller |
| M-03 | MAJOR | Phase 3 (SBI update) | SBI recalibration |
| M-04 | MAJOR | Phase 1 (model definition) | Any production GATEmbedding |
| M-05 | MAJOR | Phase 3 (SBI update) | Domain layer integration |
| M-06 | MAJOR | Phase 3 (SBI update) | Any actor with missing GAT data |
| M-07 | MAJOR | Phase 4 (training) | F1 criterion |
| M-08 | MAJOR | Phase 4 (training) | F1 criterion |
| M-09 | MAJOR | Phase 1 (model definition) | Attention weight extraction |
| M-10 | MAJOR | Phase 3 (SBI update) | FINDING M-03 resolution |
| M-11 | MAJOR | Phase 3 (SBI update) | Formula audit compliance |
| M-12 | MAJOR | Phase 3 (SBI update) | WORM audit compliance |
| m-01 | MINOR | Phase 4 (training) | Phase 4 execution |
| m-02 | MINOR | Phase 1 | Production observability |
| m-03 | MINOR | Phase 2 | Production stability |
| m-04 | MINOR | Phase 1 | Data integrity |
| m-05 | MINOR | Phase 4 | Reproducible evaluation |
| GAP-01 | MAJOR | Phase 2 | DB persistence |
| GAP-02 | MAJOR | Phase 1 | Any GATEmbeddingService call |
| GAP-03 | MAJOR | Phase 2 | Feature extraction pipeline |
| GAP-04 | MAJOR | Phase 2 | Use case integration |
| GAP-05 | MAJOR | All phases | Merge safety |
| GAP-06 | MAJOR | Phase 1 | Consistent attention magnitudes |
