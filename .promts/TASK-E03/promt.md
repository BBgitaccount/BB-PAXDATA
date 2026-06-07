# TASK-E03 · Dense Retrieval RAG v2 — Technical Engineering Report
**Target Corpus:** BB-PAXDATA commit `8d37ef99` · 601 files · ~586,896 words  
**Graph State:** 10,119 nodes · 17,209 edges · 1,074 communities (24% INFERRED edges, avg confidence 0.59)  
**Report Consumer:** Antigravity (AI system)  
**Scope:** Upgrade RAG retrieval from SBERT cosine similarity to ColBERT late-interaction (PLAID engine)

---

## SECTION 0 — CURRENT STATE BASELINE

Graph-confirmed retrieval stack (Community 31, cohesion 0.10; Community 212, cohesion 0.27):

**Protocol layer:**
- `DenseRetrieverProtocol` → concrete: `PgvectorDenseRetriever`
- `KeywordRetrieverProtocol` → concrete: `MeilisearchKeywordRetriever`
- `RerankerProtocol` → concrete: `LocalCrossEncoderReranker`
- `RAGSynthesisProtocol` (synthesis abstraction)
- `RetrievedContext` (result DTO)
- `RAGQueryRequest` / `RAGQueryResponse` (I/O DTOs)

**Embedding layer (Community 501, cohesion 0.15):**
- `EmbeddingService` protocol — domain port, `domain/ports/embedding_port.py`
- Confirmed methods: `encode(texts) → np.ndarray[N, D, float32]`, `precompute_and_cache(texts) → int`, `embedding_dim() → int`
- Confirmed dimensionality hint: `384 for MiniLM` — establishes current implementation as `sentence-transformers/all-MiniLM-L6-v2` (SBERT), single-vector cosine retrieval

**Caching layer (Community 59, cohesion implied):**
- `EmbeddingCacheProtocol` / `RedisEmbeddingCache` / `InMemoryLRUCache`
- `EmbeddingSerializer` — binary numpy serialization
- `EmbeddingCacheKey` — single-vector keying

**Test coverage for RAG (Community 212):**
- `test_dense_retriever_sqlite_fallback()` — fallback path exists, implies SQLite as dev-mode storage
- `test_keyword_retriever_fallback()` — Meilisearch fallback tested
- No ColBERT-specific tests present

**Downstream SBERT consumers (not in RAG scope, must remain unaffected):**
- `SBERTFrameMatcher` (Community 831/838) — SBERT cosine for frame detection, `EmbeddingService`-dependent
- `AzarbonyadSemanticShiftCalculator` (Community 536) — IDF-weighted context averaging
- `GATEmbeddingService` (Community 142/143) — separate model (256-dim GAT output), unrelated to `EmbeddingService`

**Confirmed retrieval weakness from graph:**
- TF-IDF edge weight formula present in Community 1038 (`1.4 TF-IDF Edge Weight Formula` — SECTION 1 MATHEMATICAL MODEL CORRECTIONS) — confirms TF-IDF is used in at least one retrieval path
- Community 31 cohesion = 0.10 — the RAG component cluster is structurally weakly connected, indicating cross-protocol coupling that must be preserved during swap

---

## SECTION 1 — ARCHITECTURAL IMPACT ANALYSIS

### 1.1 Single-Vector vs. Token-Level Embedding Incompatibility

The current `EmbeddingService` contract:

```python
# domain/ports/embedding_port.py — CURRENT (graph-confirmed)
from typing import Protocol
import numpy as np

class EmbeddingService(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return (N, D) float32 array where N = len(texts), D = model dimension."""
        ...

    def precompute_and_cache(self, texts: list[str]) -> int:
        """Pre-compute and cache embeddings. Returns count of new embeddings."""
        ...

    def embedding_dim(self) -> int:
        """Return embedding dimension (e.g., 384 for MiniLM)."""
        ...
```

ColBERT late-interaction requires per-token embeddings, producing a tensor of shape `(N, T_i, D)` where `T_i` is the token count per text `i`. This is not a scalar-dimension output — it is a ragged tensor. The existing `encode() → np.ndarray[N, D]` signature cannot represent this output without shape violation.

**Constraint:** `SBERTFrameMatcher` and `AzarbonyadSemanticShiftCalculator` consume `EmbeddingService.encode()` and expect `(N, D)` shape. Modifying the base protocol breaks these consumers. The ColBERT service must be a separate protocol and implementation.

### 1.2 PgvectorDenseRetriever Storage Model Incompatibility

`PgvectorDenseRetriever` stores document embeddings as single flat vectors in a PostgreSQL `vector(D)` column. pgvector's `<=>` (cosine distance) and `<->` (L2 distance) operators operate on 1D vectors only.

ColBERT PLAID stores:
- A compressed token-level inverted index over centroid assignments
- Per-document residual vectors for MaxSim computation
- An IVF centroid set (typically 2^k centroids for k-bit residuals)

These are fundamentally incompatible data structures. `PgvectorDenseRetriever` **cannot be reused or extended** for ColBERT retrieval. A new infrastructure component `ColBERTDenseRetriever` must implement `DenseRetrieverProtocol` against ragatouille's PLAID index file system.

### 1.3 EmbeddingCache Schema Incompatibility

`EmbeddingSerializer` uses binary numpy serialization keyed by `EmbeddingCacheKey`. For SBERT, a cache entry is `key → ndarray(D,)` — fixed-size binary blob. For ColBERT, a cache entry is `key → ndarray(T, D)` where T is variable per document. Redis binary blobs of variable size are supported, but the cache key schema and serialization format must accommodate:

1. Variable-length token axis
2. Separate query and document encoding modes (ColBERT uses different encoders for queries and documents)
3. Index-level caching vs. embedding-level caching (ColBERT indexes are not re-encoded per query — MaxSim operates against pre-built PLAID index)

Consequence: the existing `RedisEmbeddingCache` is partially reusable for query-side token caching only. Document-side encoding is subsumed by the PLAID index build process, not per-query embedding cache.

### 1.4 RAGContextAssembler Swap Point

`rag_context_assembler.py` is the correct injection point for a feature-flagged swap. The assembly logic selects retrievers and passes retrieved context to the synthesis layer. The `use_colbert: bool` flag must be resolved at DI wiring time (infrastructure/di.py) rather than at assembly time to avoid per-query branch overhead.

---

## SECTION 2 — FINDINGS

---

### FINDING E03-C01

**Classification:** critical  
**Location:** `domain/ports/embedding_port.py` — `EmbeddingService` protocol  
**Root Cause:** The `encode() → np.ndarray[N, D]` contract returns single pooled vectors. ColBERT late-interaction requires `encode() → list[np.ndarray[T_i, D]]` (ragged, one matrix per document). Retrofitting this into `EmbeddingService` would break `SBERTFrameMatcher.match_frames()` and `AzarbonyadSemanticShiftCalculator.compute_shift_from_embeddings()`, both of which unpack the result as a 2D array and index by row `i`.

**Proposed Resolution:** Define a new protocol `ColBERTEmbeddingService` as a strict extension. Do not modify `EmbeddingService`.

```python
# domain/ports/embedding_port.py — ADDITION (do not remove existing EmbeddingService)
from typing import Protocol
import numpy as np

class ColBERTEmbeddingService(Protocol):
    """
    Protocol for ColBERT late-interaction token-level embedding services.
    Distinct from EmbeddingService — returns per-token vectors, not pooled.
    
    Reference: Khattab & Zaharia (2020) "ColBERT: Efficient and Effective 
    Passage Search via Contextualized Late Interaction over BERT"
    """

    def encode_queries(self, queries: list[str]) -> list[np.ndarray]:
        """
        Encode query strings into token-level embeddings.
        
        Returns:
            List of ndarrays, each shape (T_q, D) float32.
            T_q = query token count (padded to fixed length in ColBERT: 32 tokens).
            D = model hidden dimension (128 for ColBERT-v2).
        """
        ...

    def encode_passages(self, passages: list[str]) -> list[np.ndarray]:
        """
        Encode passage strings into token-level embeddings.
        
        Returns:
            List of ndarrays, each shape (T_d, D) float32.
            T_d = document token count (variable, max 180 tokens for ColBERT-v2).
            D = model hidden dimension (128).
        """
        ...

    def embedding_dim(self) -> int:
        """Return token embedding dimension (128 for ColBERT-v2)."""
        ...
```

**Impact Assessment:** If `EmbeddingService` is modified instead of extended, `SBERTFrameMatcher` (Community 831) and `AzarbonyadSemanticShiftCalculator` (Community 536) will fail at runtime with `IndexError` or `np.broadcast_shapes` failures on the shape mismatch. These are production-critical components.

---

### FINDING E03-C02

**Classification:** critical  
**Location:** `infrastructure/` — `PgvectorDenseRetriever` (concrete of `DenseRetrieverProtocol`)  
**Root Cause:** pgvector stores `vector(D)` — a 1D float array — per document row. ColBERT PLAID does not store per-document 1D vectors; it stores a compressed inverted index over token-level centroid assignments plus residual vectors. The PLAID data structure cannot be represented as a pgvector column. ragatouille manages PLAID as a directory of binary files (`index/`, `collection/`, `config.json`).

**Proposed Resolution:** Implement `ColBERTDenseRetriever` as a new concrete of `DenseRetrieverProtocol`. Wire via DI only when `use_colbert=True`.

```python
# domain/services/colbert_embedding_service.py (new file)
from __future__ import annotations

import numpy as np
from pathlib import Path
from ragatouille import RAGPretrainedModel

from bb_paxdata.domain.ports.embedding_port import ColBERTEmbeddingService


class RAGatoulleColBERTService:
    """
    Concrete implementation of ColBERTEmbeddingService using ragatouille.
    Wraps ColBERT-v2 (Santhanam et al. 2022) via the ragatouille library.
    
    PLAID engine (Santhanam et al. 2022b) provides compressed late-interaction 
    retrieval at < 200ms/query on CPU for corpora up to ~1M passages.
    
    Index lifecycle:
        1. build_index(passages, passage_ids) — one-time or incremental
        2. retrieve(query, k) — returns RetrievedContext list
    """

    _MODEL_NAME = "colbert-ir/colbertv2.0"

    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        self._model: RAGPretrainedModel | None = None

    def _load_or_raise(self) -> RAGPretrainedModel:
        if self._model is None:
            raise RuntimeError(
                "ColBERT model not initialized. Call build_index() or load_index() first."
            )
        return self._model

    def build_index(
        self,
        passages: list[str],
        passage_ids: list[str],
        index_name: str = "bb_paxdata_rag",
        max_document_length: int = 180,
        split_documents: bool = True,
    ) -> None:
        """
        Build PLAID index from passage corpus.
        
        Args:
            passages: Raw text passages (segments, sentences, or chunks).
            passage_ids: Stable string IDs corresponding to each passage.
            index_name: Subdirectory name within index_path.
            max_document_length: Token limit per passage (ColBERT default: 180).
            split_documents: If True, ragatouille auto-splits long passages.
        
        Raises:
            ValueError: If len(passages) != len(passage_ids).
        """
        if len(passages) != len(passage_ids):
            raise ValueError(
                f"passages ({len(passages)}) and passage_ids ({len(passage_ids)}) "
                "must have equal length."
            )
        model = RAGPretrainedModel.from_pretrained(self._MODEL_NAME)
        model.index(
            collection=passages,
            document_ids=passage_ids,
            index_name=index_name,
            max_document_length=max_document_length,
            split_documents=split_documents,
        )
        self._model = model

    def load_index(self, index_name: str = "bb_paxdata_rag") -> None:
        """Load an existing PLAID index from disk."""
        index_dir = self._index_path / index_name
        if not index_dir.exists():
            raise FileNotFoundError(f"PLAID index not found at {index_dir}")
        self._model = RAGPretrainedModel.from_index(str(index_dir))

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        """
        Late-interaction MaxSim retrieval.
        
        Score formula (Khattab & Zaharia 2020):
            S(q, d) = Σ_{t ∈ q} max_{t' ∈ d} (q_t · d_t')
        
        Returns:
            List of dicts: {"content": str, "id": str, "score": float}
            Ordered by descending MaxSim score.
        """
        model = self._load_or_raise()
        results = model.search(query=query, k=k)
        return results

    def encode_queries(self, queries: list[str]) -> list[np.ndarray]:
        """ColBERTEmbeddingService protocol — query-side token embeddings."""
        model = self._load_or_raise()
        return [
            model.model.query_tokenizer.tensorize([q]).cpu().numpy()
            for q in queries
        ]

    def encode_passages(self, passages: list[str]) -> list[np.ndarray]:
        """ColBERTEmbeddingService protocol — passage-side token embeddings."""
        model = self._load_or_raise()
        return [
            model.model.doc_tokenizer.tensorize([p]).cpu().numpy()
            for p in passages
        ]

    def embedding_dim(self) -> int:
        """ColBERT-v2 hidden dim: 128."""
        return 128
```

**Impact Assessment:** Without this implementation, `DenseRetrieverProtocol` cannot be satisfied by a ColBERT backend. The pgvector path remains the only concrete dense retriever. PLAID retrieval performance advantage is blocked entirely.

---

### FINDING E03-C03

**Classification:** critical  
**Location:** `rag_context_assembler.py` — retriever selection logic  
**Root Cause:** `rag_context_assembler.py` currently instantiates `PgvectorDenseRetriever` (directly or via DI). There is no conditional path for `ColBERTDenseRetriever`. Feature flag `use_colbert: bool` is specified in the task but not implemented. Without explicit DI wiring, the assembler will continue using pgvector regardless of config.

**Proposed Resolution:** Introduce `use_colbert` as a settings field and wire at DI initialization. Assembler code should not branch — the correct retriever is injected.

```python
# infrastructure/di.py — ADDITION to existing DI wiring block

from bb_paxdata.domain.ports.rag_ports import DenseRetrieverProtocol
from bb_paxdata.infrastructure.rag.pgvector_retriever import PgvectorDenseRetriever
from bb_paxdata.domain.services.colbert_embedding_service import RAGatoulleColBERTService
from bb_paxdata.infrastructure.config.settings import Settings

def build_dense_retriever(settings: Settings) -> DenseRetrieverProtocol:
    """
    Feature-flagged factory for dense retriever.
    
    use_colbert=True  → RAGatoulleColBERTService (PLAID, late-interaction)
    use_colbert=False → PgvectorDenseRetriever (SBERT cosine, pgvector)
    
    ColBERT path requires PLAID index to be pre-built via:
        python -m bb_paxdata.scripts.build_colbert_index
    """
    if settings.use_colbert:
        service = RAGatoulleColBERTService(
            index_path=settings.colbert_index_path
        )
        service.load_index(index_name=settings.colbert_index_name)
        return ColBERTDenseRetriever(colbert_service=service)
    return PgvectorDenseRetriever(
        db_session_factory=settings.db_session_factory,
        embedding_service=settings.embedding_service,
    )
```

```python
# infrastructure/config/settings.py — ADDITIONS

from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing fields ...

    use_colbert: bool = False
    """Feature flag: enables ColBERT PLAID late-interaction retrieval.
    Requires colbert_index_path to contain a pre-built PLAID index."""

    colbert_index_path: Path = Path(".colbert_index")
    """Filesystem path to the ragatouille PLAID index directory."""

    colbert_index_name: str = "bb_paxdata_rag"
    """Subdirectory name of the active PLAID index within colbert_index_path."""
```

**Impact Assessment:** Without DI wiring, `use_colbert=True` in settings has zero effect. All A/B test comparisons measure the same pgvector path twice.

---

### FINDING E03-M01

**Classification:** major  
**Location:** Caching layer — `RedisEmbeddingCache`, `EmbeddingCacheKey`, `EmbeddingSerializer`  
**Root Cause:** `EmbeddingSerializer` uses binary numpy serialization. For SBERT, each cache value is a fixed-shape `(D,)` array. For ColBERT, query-side encoding produces `(T_q, D)` tensors where `T_q` is fixed (ColBERT pads queries to 32 tokens). Document-side encoding is irrelevant to the runtime cache — PLAID index subsumes document encoding. Therefore:

- Query encoder cache: reusable with shape annotation update
- Document encoder cache: obsolete in ColBERT mode (indexing is offline)

**Proposed Resolution:** Cache only query-side token embeddings in ColBERT mode. Wrap serialization to handle 2D arrays.

```python
# infrastructure/cache/embedding_serializer.py — MODIFICATION

import numpy as np
import io

class EmbeddingSerializer:
    """
    Serializes numpy arrays of arbitrary shape to/from binary for Redis.
    Supports both (D,) single-vector and (T, D) token-matrix formats.
    """

    @staticmethod
    def serialize(array: np.ndarray) -> bytes:
        buf = io.BytesIO()
        np.save(buf, array, allow_pickle=False)
        return buf.getvalue()

    @staticmethod
    def deserialize(data: bytes) -> np.ndarray:
        buf = io.BytesIO(data)
        return np.load(buf, allow_pickle=False)
```

Note: `np.save` preserves shape metadata. Current implementation may use raw `tobytes()` which loses shape. Verify existing `EmbeddingSerializer.serialize()` preserves ndim before assuming compatibility.

**Impact Assessment:** If existing serializer uses `tobytes()` without shape encoding, deserialized ColBERT query tensors will have incorrect shape (flattened 1D instead of `(T, D)`), causing MaxSim computation to fail silently with incorrect scores.

---

### FINDING E03-M02

**Classification:** major  
**Location:** New file — `scripts/build_colbert_index.py` (absent from codebase)  
**Root Cause:** PLAID index construction requires a corpus snapshot — all passages must be encoded in a single offline build pass. No batch indexing pipeline exists in the current RAG community (31/212). The task specifies step 4 ("Index build pipeline: mevcut corpus için ColBERT index (PLAID engine)") but provides no implementation path.

**Proposed Resolution:** Implement a standalone index builder script.

```python
# scripts/build_colbert_index.py (new file)
"""
Offline PLAID index builder for BB-PAXDATA RAG corpus.

Usage:
    python -m bb_paxdata.scripts.build_colbert_index \
        --db-url postgresql+asyncpg://... \
        --index-path .colbert_index \
        --index-name bb_paxdata_rag \
        --chunk-size 180

Corpus source: Pulls Segment.text + Sentence.text from the database.
Passage ID convention: "segment:{segment_id}" or "sentence:{sentence_id}"

Performance expectations (CPU, ColBERT-v2, PLAID):
    - ~586,896 words corpus → ~50,000–80,000 passages (180-token chunks)
    - Index build time: ~2–4 hours on CPU (single process)
    - Index size: ~2–5 GB on disk
    - Query latency post-index: < 200ms (PLAID CPU target from task spec)
"""
import asyncio
from pathlib import Path
import typer
from bb_paxdata.domain.services.colbert_embedding_service import RAGatoulleColBERTService
from bb_paxdata.infrastructure.db.session import get_session
from bb_paxdata.infrastructure.db.models import SegmentTable, SentenceTable

app = typer.Typer()

@app.command()
def build(
    db_url: str = typer.Option(..., help="SQLAlchemy async DB URL"),
    index_path: Path = typer.Option(Path(".colbert_index")),
    index_name: str = typer.Option("bb_paxdata_rag"),
    chunk_size: int = typer.Option(180, help="Max tokens per passage"),
    batch_size: int = typer.Option(1000, help="DB fetch batch size"),
) -> None:
    asyncio.run(
        _build_async(db_url, index_path, index_name, chunk_size, batch_size)
    )

async def _build_async(
    db_url: str,
    index_path: Path,
    index_name: str,
    chunk_size: int,
    batch_size: int,
) -> None:
    passages: list[str] = []
    passage_ids: list[str] = []

    async with get_session(db_url) as session:
        # Fetch segments (primary analytical units)
        offset = 0
        while True:
            rows = await session.execute(
                SegmentTable.__table__.select()
                .where(SegmentTable.text.isnot(None))
                .offset(offset)
                .limit(batch_size)
            )
            batch = rows.fetchall()
            if not batch:
                break
            for row in batch:
                passages.append(row.text)
                passage_ids.append(f"segment:{row.id}")
            offset += batch_size

    typer.echo(f"Collected {len(passages)} passages. Building PLAID index...")

    service = RAGatoulleColBERTService(index_path=index_path)
    service.build_index(
        passages=passages,
        passage_ids=passage_ids,
        index_name=index_name,
        max_document_length=chunk_size,
        split_documents=True,
    )
    typer.echo(f"PLAID index written to {index_path / index_name}")

if __name__ == "__main__":
    app()
```

**Impact Assessment:** Without the index builder, `RAGatoulleColBERTService.load_index()` raises `FileNotFoundError` at startup when `use_colbert=True`. The feature is entirely non-functional at deployment.

---

### FINDING E03-M03

**Classification:** major  
**Location:** `domain/ports/rag_ports.py` — `DenseRetrieverProtocol`  
**Root Cause:** The graph confirms `DenseRetrieverProtocol` exists as a protocol. Its `retrieve()` method signature is not visible in the graph node labels. If the signature is tightly coupled to pgvector internals (e.g., returns raw pgvector row objects rather than `RetrievedContext`), `ColBERTDenseRetriever` cannot satisfy the protocol without an adapter layer.

**Proposed Resolution:** Verify and normalize the `DenseRetrieverProtocol` contract to use `RetrievedContext` as the return type (graph-confirmed domain DTO). ColBERT ragatouille `search()` returns `list[dict]` with keys `"content"`, `"document_id"`, `"score"`. An adapter must map this to `RetrievedContext`.

```python
# Adapter within ColBERTDenseRetriever — required regardless of protocol shape
from bb_paxdata.domain.ports.rag_ports import DenseRetrieverProtocol, RetrievedContext
from bb_paxdata.domain.services.colbert_embedding_service import RAGatoulleColBERTService


class ColBERTDenseRetriever:
    """
    DenseRetrieverProtocol implementation backed by RAGatoulleColBERTService.
    Adapts ragatouille search results to RetrievedContext domain objects.
    """

    def __init__(self, colbert_service: RAGatoulleColBERTService) -> None:
        self._colbert = colbert_service

    async def retrieve(
        self, query: str, k: int = 10
    ) -> list[RetrievedContext]:
        # ragatouille.search() is synchronous — run in thread pool
        import asyncio
        loop = asyncio.get_running_loop()
        raw_results = await loop.run_in_executor(
            None, lambda: self._colbert.retrieve(query=query, k=k)
        )
        return [
            RetrievedContext(
                content=r["content"],
                source_id=r["document_id"],
                score=float(r["score"]),
                retriever_type="colbert_plaid",
            )
            for r in raw_results
        ]
```

Note: `RetrievedContext` field `retriever_type` may not exist in the current domain model. If absent, add it as `Optional[str] = None` to distinguish ColBERT results from pgvector results in the synthesis layer.

**Impact Assessment:** If `DenseRetrieverProtocol.retrieve()` has a synchronous signature and `ColBERTDenseRetriever` is async, the Protocol check fails at runtime (Python typing enforcement via `runtime_checkable` would catch this). ragatouille's CPU PLAID search takes 50–200ms — it must be offloaded to a thread pool to avoid blocking the event loop.

---

### FINDING E03-M04

**Classification:** major  
**Location:** `pyproject.toml` — dependency declaration (cross-reference: Community 1026 FINDING M-01)  
**Root Cause:** Community 1026 contains `FINDING M-01: pyproject.toml PyTorch Geometric Dependency Is Functionally Broken for CUDA Environments`. This is the same `pyproject.toml` that must receive the `ragatouille` dependency. The existing PyTorch pin `torch = { version = "2.3.0", source = "pytorch-cpu" }` (graph-confirmed) creates a constraint: ragatouille requires `torch >= 1.10` and is compatible with `2.3.0`, but its transitive dependency `transformers >= 4.36.0` must be verified against existing pinned versions.

**Proposed Resolution:** Add ragatouille with version pin and explicit torch constraint annotation.

```toml
# pyproject.toml — ADDITION under [tool.poetry.dependencies]
ragatouille = { version = ">=0.0.8,<0.1.0" }
# ragatouille 0.0.8+ includes PLAID engine and colbert-ir/colbertv2.0 support.
# Pin below 0.1.0 until API stability is confirmed.
# Requires: torch>=1.10 (satisfied by existing 2.3.0 pin),
#           transformers>=4.36.0, datasets>=2.14.0
# Verify no conflict with existing transformers pin before merge.
```

Verify with:

```bash
poetry add ragatouille --dry-run 2>&1 | grep -E "transformers|torch|datasets"
```

**Impact Assessment:** If ragatouille's `transformers` requirement conflicts with existing BERT fine-tuning or BERTopic dependencies, a resolution will require constraint relaxation across the entire `[tool.poetry.dependencies]` block. Given FINDING M-01 already documents broken CUDA constraints, this dependency block is high-risk for silent resolution failures.

---

### FINDING E03-I01

**Classification:** informational  
**Location:** Architecture — `LocalCrossEncoderReranker` + ColBERT interaction  
**Root Cause:** The existing `LocalCrossEncoderReranker` implements `RerankerProtocol` and performs cross-encoder rescoring of initial retrieval candidates. In the SBERT pipeline, the cross-encoder reranker compensates for cosine similarity recall imprecision. In the ColBERT pipeline, MaxSim late-interaction already provides fine-grained token alignment. The cross-encoder reranker is architecturally redundant over ColBERT for most query types.

**Assessment:** Retain `LocalCrossEncoderReranker` in the ColBERT pipeline during A/B testing (step 5 of task). Disable it in the ColBERT path only after A/B data confirms no Precision@5 regression. Running ColBERT + CrossEncoder provides a hybrid pipeline at higher latency cost (~350–500ms/query on CPU) but maximum precision — appropriate for high-stakes diplomatic query resolution.

**Instrumentation recommendation:**

```python
# Measure end-to-end latency in rag_context_assembler.py
import time

t0 = time.perf_counter()
dense_results = await self._dense_retriever.retrieve(query, k=k)
t1 = time.perf_counter()
reranked = await self._reranker.rerank(query, dense_results)
t2 = time.perf_counter()

# Emit to Prometheus (metrics endpoint confirmed in Community 535/558)
self._metrics.histogram("rag_dense_latency_ms").observe((t1 - t0) * 1000)
self._metrics.histogram("rag_rerank_latency_ms").observe((t2 - t1) * 1000)
```

---

### FINDING E03-I02

**Classification:** informational  
**Location:** A/B test methodology — task step 5  
**Root Cause:** The task specifies "50 queries for TF-IDF vs ColBERT Recall@10 comparison." The graph confirms the existing retrieval path uses SBERT cosine (`PgvectorDenseRetriever`, confirmed MiniLM dimensionality), not TF-IDF. The `MeilisearchKeywordRetriever` likely provides the TF-IDF/BM25 baseline. Comparing ColBERT against SBERT cosine is the higher-value A/B test for this codebase.

**Corrected A/B test specification:**

| Variant | Retriever | Method | Expected Recall@10 |
|---|---|---|---|
| Baseline-A | `MeilisearchKeywordRetriever` | BM25/TF-IDF | reference |
| Baseline-B | `PgvectorDenseRetriever` | SBERT cosine (MiniLM-384) | +15–20% vs A |
| Treatment | `ColBERTDenseRetriever` | MaxSim PLAID | target +20–40% vs B |

**Evaluation harness (minimal implementation):**

```python
# tests/eval/test_rag_ab.py (new file)
import pytest
from bb_paxdata.eval.rag_eval import recall_at_k, precision_at_k

# 50-query evaluation set — must be constructed from annotated diplomatic corpus
EVAL_QUERIES = [
    {
        "query": "pozisyon değişimi Suriye krizi",
        "relevant_ids": ["segment:1042", "segment:2871", ...],
    },
    # ... 49 more annotated queries
]

@pytest.mark.parametrize("variant", ["baseline_bm25", "baseline_sbert", "colbert"])
def test_recall_at_10(variant: str, retriever_factory) -> None:
    retriever = retriever_factory(variant)
    recalls = []
    for item in EVAL_QUERIES:
        results = retriever.retrieve_sync(item["query"], k=10)
        result_ids = [r.source_id for r in results]
        recalls.append(recall_at_k(result_ids, item["relevant_ids"], k=10))
    mean_recall = sum(recalls) / len(recalls)
    if variant == "colbert":
        # Task success criterion: ColBERT >= SBERT + 20%
        assert mean_recall >= baseline_sbert_recall * 1.20
```

**Impact Assessment:** Without an annotated query set, step 5 cannot be executed. The 50-query evaluation set is a prerequisite to success criterion measurement and must be constructed before PLAID index build.

---

### FINDING E03-I03

**Classification:** informational  
**Location:** Community 501 — `EmbeddingService.precompute_and_cache()` method  
**Root Cause:** `precompute_and_cache(texts) → int` (returns count of newly cached embeddings) is a batch encoding optimization for the SBERT path. In ColBERT mode, the equivalent operation is `build_index()` — offline PLAID index construction. The `precompute_and_cache` method on `ColBERTEmbeddingService` should be a no-op or redirect to index build status check rather than encoding.

**Proposed Resolution:** Explicitly annotate the `ColBERTEmbeddingService` protocol:

```python
class ColBERTEmbeddingService(Protocol):
    # ... encode_queries, encode_passages, embedding_dim ...

    def is_index_ready(self) -> bool:
        """
        Returns True if the PLAID index is loaded and ready for retrieval.
        Replaces precompute_and_cache() semantics — document encoding is 
        performed offline during index build, not on-demand.
        """
        ...
```

---

## SECTION 3 — IMPLEMENTATION SEQUENCE

Ordered by dependency. Each step is a merge-ready unit.

**Step 1: Protocol extension**
- File: `domain/ports/embedding_port.py`
- Action: Add `ColBERTEmbeddingService` protocol (FINDING E03-C01 resolution)
- Prerequisite: None
- Test: No runtime test — protocol is structural typing only

**Step 2: `RAGatoulleColBERTService` implementation**
- File: `domain/services/colbert_embedding_service.py` (new)
- Action: FINDING E03-C02 implementation
- Prerequisite: Step 1, `ragatouille` dependency added to `pyproject.toml`
- Test: Unit test with mock index path; integration test requires pre-built PLAID index

**Step 3: `ColBERTDenseRetriever` adapter**
- File: New concrete of `DenseRetrieverProtocol` in `infrastructure/rag/`
- Action: FINDING E03-M03 adapter
- Prerequisite: Step 2
- Test: `test_dense_retriever_sqlite_fallback()` pattern — verify `RetrievedContext` output shape

**Step 4: Settings + DI wiring**
- Files: `infrastructure/config/settings.py`, `infrastructure/di.py`
- Action: FINDING E03-C03 resolution — `use_colbert: bool`, `colbert_index_path`, `build_dense_retriever()` factory
- Prerequisite: Step 3
- Test: DI wiring unit test with `use_colbert=False` (default) must not import ragatouille

**Step 5: `EmbeddingSerializer` shape preservation**
- File: `infrastructure/cache/embedding_serializer.py`
- Action: FINDING E03-M01 resolution — migrate from `tobytes()` to `np.save/np.load`
- Prerequisite: Step 4
- Test: Round-trip serialization test for both `(D,)` and `(T, D)` shaped arrays

**Step 6: `pyproject.toml` dependency**
- File: `pyproject.toml`
- Action: FINDING E03-M04 — add `ragatouille` with explicit version bounds
- Prerequisite: None (can be parallelized with Step 1)
- Test: `poetry install --dry-run` must resolve without conflict

**Step 7: PLAID index builder script**
- File: `scripts/build_colbert_index.py` (new)
- Action: FINDING E03-M02 implementation
- Prerequisite: Steps 1–6 complete, DB accessible, corpus ≥ 1 passage
- Execution: One-time run; output is PLAID index directory

**Step 8: A/B evaluation harness**
- File: `tests/eval/test_rag_ab.py` (new)
- Action: FINDING E03-I02 implementation
- Prerequisite: Step 7 complete, 50-query annotated evaluation set constructed
- Success criterion: ColBERT Recall@10 ≥ SBERT Recall@10 × 1.20; Precision@5 non-decreasing

---

## SECTION 4 — SUCCESS CRITERIA VERIFICATION PROTOCOL

Criteria from task specification, with implementation-anchored measurement methods:

**SC-1: Recall@10 — ColBERT ≥ TF-IDF + 20%**
- Measurement: `tests/eval/test_rag_ab.py` — `recall_at_k(result_ids, relevant_ids, k=10)` across 50-query eval set
- Baseline definition: Use `MeilisearchKeywordRetriever` (BM25) as TF-IDF proxy
- Note: Task spec says "TF-IDF" but codebase uses BM25 (Meilisearch default). BM25 > TF-IDF; the 20% threshold may be conservative relative to SBERT comparison.

**SC-2: Precision@5 non-decreasing**
- Measurement: `precision_at_k(result_ids, relevant_ids, k=5)` on same 50-query set
- Acceptability threshold: ColBERT P@5 ≥ Baseline-B (SBERT) P@5 × 0.98 (allow 2% noise margin)

**SC-3: Query latency < 200ms (PLAID CPU)**
- Measurement: Prometheus histogram `rag_dense_latency_ms` (FINDING E03-I01 instrumentation)
- Target: p95 < 200ms on CPU, index built from full corpus
- Risk factor: `LocalCrossEncoderReranker` adds ~150–300ms. Disable reranker in latency benchmark.

---

## SECTION 5 — RISK REGISTER

**R01 — ragatouille API instability (High probability, Medium impact)**
ragatouille is pre-1.0 (`< 0.1.0`). Public API surface (`RAGPretrainedModel.from_pretrained`, `.index()`, `.search()`) has changed across minor versions. Pin to `>=0.0.8,<0.1.0` and snapshot integration test outputs for regression detection.

**R02 — PLAID index build time exceeds deployment window (Medium probability, High impact)**
~586,896-word corpus → estimated 2–4 hours index build on CPU. Build must be offline/pre-deployment. Incremental indexing via ragatouille `add_to_index()` is available in `>= 0.0.9` but is slower per-passage than batch build. Strategy: pre-build index in CI on corpus snapshot; expose `build_colbert_index.py` as a deployment task.

**R03 — Existing Meilisearch BM25 retrieval performance exceeds SBERT baseline (Medium probability, Low impact)**
If `MeilisearchKeywordRetriever` already achieves high BM25 recall on the diplomatic corpus (domain-specific proper nouns, Arabic/Turkish proper noun coverage), the marginal gain from ColBERT may be < 20%. Validate Recall@10 on baseline BM25 before committing to ColBERT migration.

**R04 — `RetrievedContext` model missing `retriever_type` field (Low probability, Low impact)**
If `RetrievedContext` is a frozen Pydantic model without `retriever_type`, the `ColBERTDenseRetriever` adapter cannot annotate result provenance. Add as `Optional[str] = None` without breaking existing consumers.

**R05 — DI graph instantiation of `RAGatoulleColBERTService` at app startup (Medium probability, High impact)**
`RAGatoulleColBERTService.__init__` + `load_index()` loads the PLAID index into memory on startup (~2–5 GB). If the index is absent (e.g., first deployment, cold environment), startup fails with `FileNotFoundError`. Guard with lazy initialization and health-check endpoint warning.

---

## SECTION 6 — GRAPH STRUCTURE OBSERVATIONS RELEVANT TO E03

**Community 31 cohesion 0.10** — The RAG protocol cluster is structurally weak. Nodes are connected to many other communities but not densely to each other. This indicates the retrieval protocols are consumed widely across the application (correct architectural pattern — dependency inversion) but also that changes to protocol signatures propagate widely. `EmbeddingService` modification risk is proportional to its fan-out.

**Community 501 — `EmbeddingService` isolation** — `EmbeddingService` is in its own small community (cohesion 0.15, 9 nodes). Its consumers (`SBERTFrameMatcher`, `AzarbonyadSemanticShiftCalculator`) are in separate communities (831, 536). This confirms the protocol is a stable shared dependency — modification must be additive only.

**`Analysis` node betweenness centrality 0.067** — The `Analysis` domain model bridges 35+ communities. Any change to retrieval output that modifies how `Analysis` objects are populated downstream (e.g., if `rag_context_assembler.py` annotates analyses with retrieved contexts) has system-wide propagation risk. E03 changes should not touch `Analysis` model fields.

**Community 212 — `RAGQueryRequest` cluster** — Low cohesion (0.27 for 8 nodes); `RAGQueryRequest` is co-located with test fixtures, not with protocol definitions. This indicates the request DTO is loosely integrated with its execution context. `ColBERTDenseRetriever.retrieve()` should accept a plain `query: str` + `k: int` to avoid coupling to `RAGQueryRequest` internals.

---

## SECTION 7 — COMPLETE FILE MANIFEST FOR E03

| Status | File Path | Action |
|---|---|---|
| MODIFY | `domain/ports/embedding_port.py` | Add `ColBERTEmbeddingService` protocol |
| CREATE | `domain/services/colbert_embedding_service.py` | `RAGatoulleColBERTService` implementation |
| CREATE | `infrastructure/rag/colbert_retriever.py` | `ColBERTDenseRetriever` adapter |
| MODIFY | `infrastructure/config/settings.py` | Add `use_colbert`, `colbert_index_path`, `colbert_index_name` |
| MODIFY | `infrastructure/di.py` | Add `build_dense_retriever()` factory |
| MODIFY | `infrastructure/cache/embedding_serializer.py` | Shape-preserving serialization |
| MODIFY | `pyproject.toml` | Add `ragatouille >= 0.0.8, < 0.1.0` |
| CREATE | `scripts/build_colbert_index.py` | Offline PLAID index builder |
| CREATE | `tests/eval/test_rag_ab.py` | A/B evaluation harness |
| CREATE | `tests/unit/rag/test_colbert_retriever.py` | Unit tests for adapter |
| NO CHANGE | `rag_service.py` | Not a target — task spec lists `rag_context_assembler.py` as swap point |
| NO CHANGE | `domain/ports/rag_ports.py` | `DenseRetrieverProtocol` signature unchanged |
| NO CHANGE | `infrastructure/rag/pgvector_retriever.py` | Retained as default path |

Note: `rag_service.py` is listed as an affected file in the task but the correct injection point is the DI container (`di.py`) and assembler. If `rag_service.py` directly instantiates `PgvectorDenseRetriever`, it must be refactored to accept a `DenseRetrieverProtocol` dependency — move instantiation to `di.py` first.