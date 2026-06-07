# AGENTS.md — BB-PAXDATA

Diplomatik transkriptler için çok katmanlı NLP motoru. Duygu analizi, risk puanlama, hedge dili tespiti, çerçeveleme analizi ve HITL kalite güvencesini tek bir bütünleşik pipeline altında toplar.

---

## Mimari — Hızlı Harita

```
src/bb_paxdata/
├── interfaces/
│   └── cli/
│       ├── commands/          # build.py, analyze.py, validate.py, migrate.py, test.py
│       └── review_commands.py # HITL review CLI
├── application/
│   └── commands/              # BuildDatabaseCommand, RunAnalysisCommand, RunFailCheckCommand
├── domain/
│   ├── sentiment/             # SentimentService — DIPLO + VADER
│   ├── risk/                  # RiskService — SBI / DKI
│   ├── hedging/               # HedgingService — Hyland (1995)
│   ├── framing/               # FramingService — Entman (1993)
│   ├── anomaly/               # CrossAnomalyService — 10 kural, plugin mimarisi
│   ├── topic/                 # TopicService — TF-IDF + BERTopic
│   ├── temporal/              # TemporalAnalyzer — CUSUM + JSD
│   └── ner/                   # NERService — spaCy GPE/ORG
├── infrastructure/
│   ├── ai/                    # AIClient ABC + Ollama, Anthropic, Gemini, Groq, DeepSeek
│   ├── db/                    # SQLAlchemy 2.0 async + Alembic migrations
│   ├── cache/                 # DiskCache + Redis
│   ├── recovery/              # 6-Seviyeli JSON Recovery Engine
│   └── observability/         # Prometheus metrics
└── config/                    # Pydantic Settings (.env), structlog
```

Katman bağımlılığı tek yönlüdür: `interfaces → application → domain → infrastructure → config`. Hiçbir zaman bu yönün tersine import yapmayın.

---

## Ortam Kurulumu

```bash
git clone https://github.com/BBgitaccount/BB-PAXDATA.git
cd BB-PAXDATA
cp .env.example .env            # API anahtarlarını doldurun
poetry install
poetry run alembic upgrade head  # DB tablolarını oluştur
```

`.env` içinde en az bir AI backend gereklidir. Yerel geliştirme için Ollama ücretsizdir:

```ini
OLLAMA_BASE_URL=http://localhost:11434
DATABASE_URL=sqlite:///./data/paxdata.db
CACHE_BACKEND=diskcache
CACHE_DIR=./data/cache
```

> **Poetry 2.0+ notu:** `poetry shell` varsayılan gelmez.  
> `poetry self add poetry-plugin-shell` ile ekleyin ya da tüm komutları `poetry run` ile çalıştırın.

---

## Testleri Çalıştırma

Kodun doğruluğunu doğrulamak için her zaman ilk olarak logic testlerini çalıştırın — AI çağrısı yapmaz, maliyetsizdir ve hızlıdır:

```bash
poetry run bbpaxdata test run --type logic         # Sadece kural/NLP testleri
poetry run bbpaxdata test run --type ai            # AI/LLM servis testleri
poetry run bbpaxdata test run --type e2e           # Uçtan uca sistem testi
poetry run bbpaxdata test run --type all           # Tam test süiti
```

Tek cümle üzerinde hızlı doğrulama:

```bash
poetry run bbpaxdata test eval-sentence "We will never accept this ultimatum." --logic-only
```

Golden Dataset kalite ölçümü:

```bash
poetry run bbpaxdata test eval-dataset --limit 50
```

---

## Kod Stili

| Araç     | Konfigürasyon   | Kural                                      |
|----------|-----------------|--------------------------------------------|
| `ruff`   | `pyproject.toml`| Linting — import sırası, kullanılmayan kod |
| `black`  | `pyproject.toml`| Formatlama                                 |
| `mypy`   | `mypy.ini`      | **Strict mod** — tüm public fonksiyonlar için type hint zorunludur |

Commit öncesi kontrol:

```bash
poetry run ruff check src/
poetry run black src/
poetry run mypy src/
```

`pre-commit` hook'ları kuruluysa bu kontroller otomatik çalışır:

```bash
pre-commit install
```

---

## Temel Geliştirme Kuralları

### 1. Yeni Domain Servisi Ekleme

Her domain servisi `domain/` altında kendi modülünde yaşar. Servislere doğrudan infrastructure bağımlılığı **eklemeyin** — tüm persistence ve AI çağrıları `application/` katmanı üzerinden geçer.

```python
class MyNewService:
    def analyze(self, text: str, context: AnalysisContext) -> MyResult:
        ...  # Saf hesaplama mantığı burada
```

### 2. Yeni Anomali Kuralı Ekleme

`CrossAnomalyService` plugin mimarisi kullanır. `AnomalyRule` protokolünü uygulayan her sınıf otomatik olarak motor tarafından keşfedilir:

```python
class MyNewAnomalyRule(AnomalyRule):
    def evaluate(self, analysis: Analysis) -> AnomalyContribution | None:
        ...
```

Kural tetiklendiğinde döndürülen katkı, toplam anomali skoruna `min(Σ katkılar, 1.0)` ile eklenir.

### 3. Yeni AI Backend Ekleme

`infrastructure/ai/` altında `AIClient` ABC'yi miras alın:

```python
class MyBackendClient(AIClient):
    async def generate(self, prompt: str, **kwargs) -> str: ...
    async def embed(self, text: str) -> list[float]: ...
```

Fallback zinciri otomatik olarak çalışır: birincil → ikincil → üçüncül → 6-Seviyeli JSON Recovery.

### 4. JSON Recovery Engine — Dokunmayın

`recovery/` altındaki 6 seviyeli kurtarma motoru (L1 Direct → L6 SchemaDefault) production-kritik bir bileşendir. AI backend'lerden dönen ham yanıtlar her zaman bu motor üzerinden geçirilir. Yeni bir parsing mantığı eklerken Recovery Engine'i bypass etmeyin — her zaman `RecoveryEngine.recover(raw_text)` kullanın.

### 5. Formül Doğrulama Değiştirme

`FormulaAuditor` içindeki deterministik kontroller (`FORMULA_VALIDATION_LOG` tablosuna yazar) değiştirilirken şunlara dikkat edin:

- `is_current` / `superseded_by` sürüm zinciri bozulmamalıdır.
- Her değişiklik `formula_validation_audit` tablosuna anlık kaydedilir (WORM — sadece yazma).
- Auto-triage kuralları (CRITICAL / SOVEREIGN_PRIORITY / HIGH_PRIORITY / NORMAL) kritik öneme sahiptir; eşikleri keyfi değiştirmeyin.

### 6. Veritabanı Şema Değişiklikleri

Model değişikliklerinde her zaman Alembic migration oluşturun:

```bash
poetry run alembic revision --autogenerate -m "add_my_column"
poetry run alembic upgrade head
```

`HumanReview` ve `FormulaValidationAudit` tabloları immutable'dır — bu tablolarda UPDATE veya DELETE çalıştıracak migration yazmayın.

---

## Önemli CLI Komutları

```bash
# Transkriptleri yükle
poetry run bbpaxdata build data/

# AI-free hızlı yükleme (ücretsiz, sıfır LLM çağrısı)
poetry run bbpaxdata build data/ --logic-only --force-rebuild

# Bütçe kontrollü: sadece ilk 50 cümleyi AI ile işle
poetry run bbpaxdata build data/ --ai-limit 50 --force-rebuild

# Klasör izleme (canlı)
poetry run bbpaxdata build watch data/ --logic-only --interval 5

# Tam analiz pipeline'ı
poetry run bbpaxdata analyze full --panel-id "panel_01" --threshold 0.5 --centrality

# Veritabanı doğrulama
poetry run bbpaxdata validate db --strict

# HITL dashboard
poetry run streamlit run scripts/hitl_dashboard.py

# Haftalık kalibrasyon
poetry run bbpaxdata review calibrate --prompt-version v3 --days-back 7
```

---

## Önbellek Stratejisi

Tüm AI çağrıları `SHA-256(prompt_text + model_version)` anahtarıyla önbelleğe alınır. Prompt değişirse önbellek otomatik geçersiz hale gelir. Önbelleği manuel temizlemeniz gereken durumlarda:

```bash
# DiskCache için
rm -rf data/cache/

# Redis için
redis-cli FLUSHDB
```

---

## Metrik Endpointi

Prometheus metrikleri `:8000/metrics` üzerinden sunulur. Grafana dashboard'u Docker Compose ile ayağa kalkar:

```bash
docker compose up prometheus grafana
```

Kritik metrikler: `ai_backend_latency_seconds`, `cache_hit_rate`, `json_recovery_total`, `batch_fallback_count`.

---

## Yaygın Hatalar ve Çözümleri

| Hata | Neden | Çözüm |
|------|-------|-------|
| `InvalidFileException` `.xls` dosyasında | openpyxl `.xls` okuyamaz | `pd.read_excel(engine="xlrd")` kullan |
| `poetry shell` bulunamadı | Poetry 2.0+ | `poetry self add poetry-plugin-shell` |
| `alembic upgrade head` başarısız | Schema çakışması | `alembic downgrade -1` sonra tekrar dene |
| AI backend timeout | Rate limit / bağlantı | `.env`'de fallback backend tanımla |
| `SOVEREIGN_PRIORITY` kuyruğu doldu | Tier-1 konuşmacı yoğunluğu | Dashboard'dan manuel verdict gir |

---

## Bilimsel Formüller — Hızlı Başvuru

Implementasyonda değiştireceğiniz formüller için referans:

| Servis | Formül | Dosya |
|--------|--------|-------|
| Duygu | `diplo_compound = VADER_compound + (Σ v_p) × 0.05` | `domain/sentiment/` |
| Negasyon | `score = -v_p × 0.8` (sol pencere [i-4:i]) | `domain/sentiment/` |
| SBI | `(P_level × W_demand) / 2 + R_score` | `domain/risk/` |
| DKI | `(d_norm×0.4 + (1-r_norm)×0.3 + d_req×0.2 + (1-m_norm)×0.1) × 2 - 1` | `domain/risk/` |
| Hedge | `H_score = Σ(w_c × n_c) / max(1, N_matches)` | `domain/hedging/` |
| Uncertainty | `U = H(p) = -Σ p_c log₂ p_c` | `infrastructure/quality/` |
| CUSUM | `CUSUM⁺_t = max(0, CUSUM⁺_{t-1} + z_t - k)` | `domain/temporal/` |

---

## Güvenlik ve RBAC

HITL denetçi işlemleri JWT tabanlı kimlik doğrulama gerektirir. Yetki seviyeleri `ReviewerAssignment` tablosunda saklanır: `view → verdict → correct → escalate → admin`. Kod değişikliği yaparken hiçbir endpoint bu hiyerarşiyi atlatmamalıdır.

---

## Sürüm Notu (v3.0.0)

Bu sürümde eklenen bileşenler: FormulaAuditor, Auto-Triage, WORM Audit Trail, Log Versioning (superseded_by zinciri), RBAC, Streamlit Review Dashboard, Triplet Card bağlam görünümü. Bu bileşenleri kapsayan testler `tests/hitl/` ve `tests/formula/` altında bulunur.