# BB-PAXDATA

> Diplomatic Discourse Analysis Engine  
> Structured extraction, multi-layer annotation, and quantitative framing analysis for diplomatic transcripts.

---

## 1. System Overview

| Layer | Responsibility | Output |
| --- | --- | --- |
| **Ingestion** | Transcript normalization, speaker diarization, idempotency | `Segment[]`, `Speaker[]` |
| **Domain Core** | NLP annotation (sentiment, risk, hedging, framing, anomaly) | `Analysis` per sentence |
| **Infrastructure** | Persistence, AI backend abstraction, caching, recovery | Alembic-versioned DB, cached LLM calls |
| **Observability** | Metrics, tracing, prompt versioning | Prometheus + Grafana dashboards |
| **Quality Assurance** | Golden dataset evaluation, uncertainty scoring, drift detection | `QualityReport`, `UncertaintyScore` |
| **Interface** | CLI (`typer`) + future REST API (`FastAPI`) | Human-readable reports & structured exports |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INTERFACES                                     │
│  CLI (Typer)  │  Future: FastAPI | WebAPP                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                           APPLICATION                                       │
│  BuildDatabaseCommand │ RunAnalysisCommand │ RunFailCheckCommand │ Queries  │
├─────────────────────────────────────────────────────────────────────────────┤
│                           DOMAIN CORE                                       │
│  SentimentService │ RiskService │ HedgingService │ FramingService │ ...     │
├─────────────────────────────────────────────────────────────────────────────┤
│                         INFRASTRUCTURE                                      │
│  DB (SQLAlchemy 2.0 + Alembic) │ AI (Abstract Client + Factory) │ Cache     │
│  Observability (Prometheus)    │ Quality (Evaluator + Golden DS)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                           CONFIGURATION                                     │
│  Pydantic Settings │ Structlog │ .env / .env.example                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Analytical Pipeline

### 3.1 Pre-processing

| Step | Method | Purpose |
| --- | --- | --- |
| Tokenization | Word-level + sentence-level | Baseline for all downstream tasks |
| Encoding Normalization | `ftfy` + `unicodedata` | Fix Turkish/Arabic/Cyrillic mojibake |
| Lemmatization | spaCy (`tr_core_news_trf`, `en_core_web_trf`) | Standardize morphological variants |
| POS Tagging | spaCy dependency parser | Syntactic feature extraction |
| NER | spaCy + custom GPE model | Geopolitical entity detection |
| Stopword Filtering | Domain-aware (retains negation: *not*, *never*) | Preserve rhetorically loaded tokens |

### 3.2 Feature Extraction

| Feature | Technique | Granularity |
| --- | --- | --- |
| TF-IDF | Scikit-learn / custom | Segment-level keyword ranking |
| N-grams | Bigram / trigram frequency | Collocation & rhetorical pattern detection |
| Embeddings | Contextual (transformer-based) | Semantic similarity & clustering |

---

## 4. Domain Services (Analytical Modules) (UPDATE)

### 4.1 Sentiment Analysis (`SentimentService`)

| Component | Description |
| --- | --- |
| **Negation-Aware DIPLO** | Rule-based diplomatic tone classifier with negation scope detection |
| **VADER Wrapper** | Valence Aware Dictionary and sEntiment Reasoner adapted for formal register |
| **Output** | `DiplomaticTone` enum: `COOPERATIVE`, `CONFRONTATIONAL`, `NEUTRAL`, `AMBIVALENT` |

> **Scientific formulation:** *soon* — Negation-aware sentiment scoring with dependency-tree scope resolution.

### 4.2 Risk Scoring (`RiskService`)

| Metric | Description |
| --- | --- |
| **SBI** (*Speaker-Based Index*) | Aggregated per-speaker risk exposure |
| **DKI** (*Discourse-Kinetic Index*) | Cross-speaker interaction volatility |

> **Scientific formulation:** *soon* — SBI/DKI composite risk tensor calculation with temporal decay.

### 4.3 Hedging Detection (`HedgingService`)

Based on **Hyland (1995, 2005)** taxonomy of epistemic and style hedges in academic/scientific discourse, adapted for diplomatic register.

| Hedge Category | Examples | Function |
| --- | --- | --- |
| Epistemic (uncertainty) | *possibly*, *it seems*, *we believe* | Mitigate commitment |
| Style (attitude) | *roughly*, *kind of*, *in our view* | Soften propositional force |

> **Scientific formulation:** *soon* — Hyland hedge density ratio + modal verb classification via dependency patterns.

### 4.4 Framing Analysis (`FramingService`)

Based on **Entman (1993)** four-function framing model:

| Function | Detection Method |
| --- | --- |
| **Problem Definition** | Keyword + entity co-occurrence in subject position |
| **Causal Interpretation** | Dependency path: `nsubj` → `ROOT` → `obl:agent` |
| **Moral Evaluation** | Evaluative adjective + entity pairing |
| **Treatment Recommendation** | Modal verb (*should*, *must*) + policy verb cluster |

> **Scientific formulation:** *soon* — Entman frame salience score via cascading network activation model.

### 4.5 Cross-Anomaly Detection (`CrossAnomalyService`)

| Anomaly Type | Trigger |
| --- | --- |
| 1. Tone drift | Sentiment variance > 2σ within single segment |
| 2. Entity flip | Same entity receives opposite sentiment within 3 sentences |
| 3. Modal collapse | Absence of hedging in high-stakes proposition |
| 4. Frame contradiction | Problem definition ≠ treatment recommendation |
| 5. Speaker inconsistency | Same speaker, divergent SBI across contexts |
| 6. Temporal gap | > 30s silence with unresolved anaphora |
| 7. Translation artifact | POS n-gram distribution shift (Volansky et al. 2015) |
| 8. Overlapping claim | Multiple speakers assign mutually exclusive causality |
| 9. Missing GPE | Policy verb without geopolitical entity argument |
| 10. Recovery failure | 6-level JSON recovery exhausted |

> **Scientific formulation:** *soon* — Multi-dimensional anomaly tensor with speaker-level covariance.

### 4.6 Topic Modeling (`TopicService`)

| Method | Use Case |
| --- | --- |
| TF-IDF + Keyword | Baseline topic ranking per segment |
| BERTopic | Semantic clustering for thematic drift detection |

> **Scientific formulation:** *soon* — BERTopic dynamic topic modeling with temporal sliding window.

### 4.7 Dependency Parsing (`DependencyService`) — *Phase 5*

| Extraction | Pattern |
| --- | --- |
| Subject-Verb-Object | `nsubj` → `ROOT` → `dobj` / `iobj` |
| Agent-Patient | `obl:agent` + passive `ROOT` |
| Policy Actor | `GPE` + `appos` + `nmod` |

> **Scientific formulation:** *soon* — spaCy dependency triple extraction with diplomatic-domain edge pruning.

### 4.8 Explainability (`ExplainabilityService`) — *Phase 5*

| Method | Output |
| --- | --- |
| SHAP values | Feature importance per prediction |
| Rule-based | Human-readable justification chain |

> **Scientific formulation:** *soon* — SHAP + LIME hybrid for diplomatic discourse classification.

### 4.9 Temporal Drift (`TemporalAnalyzer`) — *Phase 4*

| Metric | Description |
| --- | --- |
| Lexical drift | JSD divergence between time-sliced vocabularies |
| Syntactic drift | POS n-gram KL divergence |
| Semantic drift | Embedding centroid shift |

> **Scientific formulation:** *soon* — Jensen-Shannon divergence + embedding drift detection.

---

## 5. Infrastructure

### 5.1 AI Backend Abstraction

```python
class AIClient(ABC):
    async def generate(self, prompt: str, **kwargs) -> str: ...
    async def embed(self, text: str) -> list[float]: ...

class OllamaClient(AIClient): ...      # Local LLM
class AnthropicClient(AIClient): ...   # Claude
class GeminiClient(AIClient): ...      # Google
class GroqClient(AIClient): ...       # Fast inference

class AIClientFactory:
    @staticmethod
    def create(backend: BackendEnum) -> AIClient: ...
```

| Feature | Implementation |
| --- | --- |
| Smart Fallback | Primary → Secondary → Tertiary backend cascade |
| Retry Logic | Exponential backoff + jitter |
| 6-Level Recovery | JSON repair: bracket balancing → quote normalization → schema injection → LLM self-correction → partial extraction → graceful degradation |

### 5.2 Caching

| Backend | Driver | TTL Strategy |
| --- | --- | --- |
| Disk | `diskcache` | 24h default |
| Redis | `redis-py` | LRU + explicit invalidation |

### 5.3 Database

| Component | Technology |
| --- | --- |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Schema | `Sentence` → `Segment` → `Speaker` → `Analysis` → `QualityReport` |

---

## 6. Observability (Phase 3)

| Metric | Type | Labels |
| --- | --- | --- |
| `ai_backend_latency_seconds` | Histogram | `backend`, `operation` |
| `cache_hit_rate` | Gauge | `backend` (disk/redis) |
| `batch_fallback_count` | Counter | `from_backend`, `to_backend` |
| `prompt_version` | Info | `hash`, `registered_at` |

- **Prometheus** metrics endpoint (`/metrics`)
- **Grafana** dashboard (JSON export in `infrastructure/observability/dashboard/`)
- **LangSmith** integration (optional, API-key gated)

### Test Command

```bash
# Prometheus + Grafana başlat
docker compose up -d prometheus grafana

# Python tarafında metrics endpoint'i başlat
from infrastructure.observability import get_metrics
get_metrics().start_http_server(port=8000)

# Kontrol
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000  (admin / bbpaxdata2024)
```

---

## 7. Quality Assurance (Phase 4)

| Component | Purpose |
| --- | --- |
| `GoldenDataset` | 100 hand-labeled sentences as ground truth |
| `QualityEvaluator` | Deepeval / custom scorer against golden set |
| `UncertaintyScorer` | Entropy-based confidence per AI output |
| `DataContractValidator` | Pandera input schema validation |
| Idempotency | SHA-256 key per transcript to prevent duplicate ingestion |

> **Scientific formulation:** *soon* — Uncertainty quantification via predictive entropy + ensemble disagreement.

---

## 8. Installation & Usage (SOON)

```bash
# 1. Clone
$ git clone https://github.com/yourorg/BB-PAXDATA.git
$ cd BB-PAXDATA

# 2. Environment
$ cp .env.example .env
# Edit .env with your AI backend keys

# 3. Poetry
$ poetry install
$ poetry shell

# 4. Database
$ make migrate

# 5. Run
$ bbpaxdata build     # Build database from transcripts
$ bbpaxdata analyze   # Run full analysis pipeline
$ bbpaxdata failcheck # Anomaly & risk audit
$ bbpaxdata report    # Generate HTML/PDF report
```

### Makefile Targets

```bash
$ make build      # Docker compose up (Postgres + Redis + Ollama + Grafana)
$ make test       # pytest + coverage (>70% target)
$ make lint       # ruff + black + mypy
$ make analyze    # Full pipeline on sample data
```

---

## 9. Project Roadmap

| Phase | Deliverable | Status |
| --- | --- | --- |
| **0** | Project skeleton, CI/CD, linting | ✅ Complete |
| **1** | Domain core: enums, Pydantic models, base services | ✅ Complete |
| **2** | SQLAlchemy ORM, Alembic, AI clients, caching | 🔄 In Progress |
| **3** | Observability: Prometheus, Grafana, prompt registry | ⏳ Planned |
| **4** | Quality: Golden dataset, evaluator, uncertainty, drift | ⏳ Planned |
| **5** | NLP boost: spaCy dependency, multilingual, SHAP | ⏳ Planned |
| **6** | CLI: Typer commands, shell completion, migration | ⏳ Planned |
| **7** | Use cases: wrap legacy v4/v5 logic | ⏳ Planned |
| **8** | Integration tests, MkDocs, Docker Compose, docs | ⏳ Planned |

---

## 10. Scientific Methods & Formulations — Summary

| Module | Method | Status |
| --- | --- | --- |
| Sentiment | Negation-aware DIPLO + VADER | 🔬 *soon* |
| Risk | SBI / DKI composite index | 🔬 *soon* |
| Hedging | Hyland (1995) taxonomy + density ratio | 🔬 *soon* |
| Framing | Entman (1993) four-function model + salience | 🔬 *soon* |
| Anomaly | 10-type cross-anomaly tensor | 🔬 *soon* |
| Topic | TF-IDF + BERTopic dynamic modeling | 🔬 *soon* |
| Dependency | spaCy SVO extraction + diplomatic pruning | 🔬 *soon* |
| Explainability | SHAP + LIME hybrid | 🔬 *soon* |
| Temporal | JSD lexical drift + embedding centroid shift | 🔬 *soon* |
| Quality | Predictive entropy + ensemble disagreement | 🔬 *soon* |

---

## 11. References

- Soon

---
