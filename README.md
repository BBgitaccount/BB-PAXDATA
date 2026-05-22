<div align="center">

<!-- Animated SVG Banner -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 160" width="900" height="160">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0f0c29;stop-opacity:1" />
      <stop offset="50%" style="stop-color:#302b63;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#24243e;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#a78bfa" />
      <stop offset="50%" style="stop-color:#60a5fa" />
      <stop offset="100%" style="stop-color:#34d399" />
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
      <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="900" height="160" rx="16" fill="url(#bg)"/>
  <!-- Animated circles -->
  <circle cx="50" cy="30" r="3" fill="#a78bfa" opacity="0.6">
    <animate attributeName="cy" values="30;130;30" dur="4s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.6;0.1;0.6" dur="4s" repeatCount="indefinite"/>
  </circle>
  <circle cx="150" cy="80" r="2" fill="#60a5fa" opacity="0.5">
    <animate attributeName="cy" values="80;20;80" dur="3s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.5;0.1;0.5" dur="3s" repeatCount="indefinite"/>
  </circle>
  <circle cx="800" cy="50" r="3" fill="#34d399" opacity="0.6">
    <animate attributeName="cy" values="50;140;50" dur="5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.6;0.1;0.6" dur="5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="850" cy="120" r="2" fill="#f472b6" opacity="0.5">
    <animate attributeName="cy" values="120;10;120" dur="3.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.5;0.1;0.5" dur="3.5s" repeatCount="indefinite"/>
  </circle>
  <!-- Main title -->
  <text x="450" y="72" text-anchor="middle" font-family="'Segoe UI', Arial, sans-serif"
        font-size="46" font-weight="900" fill="url(#textGrad)" filter="url(#glow)">
    BB-PAXDATA
  </text>
  <!-- Subtitle -->
  <text x="450" y="105" text-anchor="middle" font-family="'Segoe UI', Arial, sans-serif"
        font-size="15" fill="#94a3b8" letter-spacing="3">
    DIPLOMATIC DISCOURSE ANALYSIS ENGINE
  </text>
  <!-- Version badge -->
  <rect x="380" y="118" width="140" height="24" rx="12" fill="#1e1b4b" opacity="0.8"/>
  <text x="450" y="134" text-anchor="middle" font-family="'Segoe UI', Arial, sans-serif"
        font-size="11" fill="#a78bfa" font-weight="600">
    v1.0.0  ·  Python 3.12+
  </text>
  <!-- Decorative lines -->
  <line x1="80" y1="80" x2="340" y2="80" stroke="#a78bfa" stroke-width="0.5" opacity="0.3"/>
  <line x1="560" y1="80" x2="820" y2="80" stroke="#34d399" stroke-width="0.5" opacity="0.3"/>
</svg>

<br/>

[![Version](https://img.shields.io/badge/version-1.0.0-a78bfa?style=for-the-badge&logo=semantic-release&logoColor=white)](https://github.com/BBgitaccount/BB-PAXDATA)
[![Python](https://img.shields.io/badge/Python-3.12+-3b82f6?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-34d399?style=for-the-badge&logo=gnu&logoColor=white)](./LICENSE)
[![Tests](https://img.shields.io/badge/Tests-pytest-f472b6?style=for-the-badge&logo=pytest&logoColor=white)](./tests)
[![Code Style](https://img.shields.io/badge/Code%20Style-ruff%20%2B%20black-facc15?style=for-the-badge&logo=python&logoColor=black)](./pyproject.toml)
[![Type Check](https://img.shields.io/badge/Types-mypy%20strict-60a5fa?style=for-the-badge&logo=python&logoColor=white)](./mypy.ini)

---

*Diplomatik transkriplerin yapısal çıkarımı, çok katmanlı anotasyonu ve kantitatif çerçeveleme analizi için geliştirilmiş**açık kaynaklı NLP motoru**.*

> **⚠️ Bu döküman v1.0.0'e özeldir.** Sistem geliştikçe API'ler, formüller ve mimariler önemli ölçüde değişebilir. Güncel bilgi için her zaman etiketli sürümün dökümantasyonuna başvurun.

</div>

---

## 📋 İçindekiler

| # | Bölüm |
|---|-------|
| 1 | [Sistem Genel Bakış](#1-sistem-genel-bakış) |
| 2 | [Mimari](#2-mimari) |
| 3 | [Analitik Pipeline](#3-analitik-pipeline) |
| 4 | [Domain Servisleri — Teknik Detaylar](#4-domain-servisleri--teknik-detaylar) |
| 5 | [Altyapı](#5-altyapı) |
| 6 | [Gözlemlenebilirlik](#6-gözlemlenebilirlik) |
| 7 | [Kalite Güvencesi](#7-kalite-güvencesi) |
| 8 | [Hızlı Başlangıç Kılavuzu](#8-hızlı-başlangıç-kılavuzu) |
| 9 | [CLI Referansı](#9-cli-referansı) |
| 10 | [Proje Yol Haritası](#10-proje-yol-haritası) |
| 11 | [Bilimsel Metodoloji](#11-bilimsel-metodoloji) |
| 12 | [Akademik Kaynaklar](#12-akademik-kaynaklar) |

---

## 1. Sistem Genel Bakış

BB-PAXDATA, diplomatik söylemleri (konferans tutanakları, zirve konuşmaları, BM oturumları vb.) çok boyutlu biçimde analiz eden bir **NLP boru hattıdır**. Sistem; duygu analizi, risk puanlama, çit (hedge) dili tespiti, çerçeveleme analizi ve anomali tespitini tek bir bütünleşik motorun altında toplar.

```
📝 Ham Transkript
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER                                                                   │
│  Transkript normalleştirme · Konuşmacı ayrıştırma · SHA-256 idempotency           │
│  ftfy encoding düzeltme · Türkçe/Arapça/Kiril karakter düzeltme                  │
└───────────────────────────────────────────────────────────────────────────────────┘
        │  Segment[ ]  Speaker[ ]
        ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│  DOMAIN CORE — NLP Annotation Pipeline                                            │
│  SentimentService · RiskService · HedgingService · FramingService                 │
│  CrossAnomalyService · TopicService · TemporalAnalyzer                            │
│  NERService · DependencyService · ExplainabilityService                           │
└───────────────────────────────────────────────────────────────────────────────────┘
        │  Analysis[ ]
        ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE                                                                   │
│  SQLAlchemy 2.0 (async) · Alembic · AI Client Abstraction                         │
│  6-Level JSON Recovery · Disk/Redis Cache · Prometheus Metrics                    │
└───────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│  INTERFACE                                                                        │
│  CLI (Typer + Rich) · Future: FastAPI REST                                        │
│  HTML/PDF Raporlar · JSON Exports · Grafana Dashboards                            │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Katman Sorumlulukları

| Katman | Sorumluluk | Çıktı |
|--------|------------|-------|
| **Ingestion** | Transkript normalleştirme, konuşmacı ayrıştırma, idempotency | `Segment[]`, `Speaker[]` |
| **Domain Core** | NLP anotasyonu (duygu, risk, hedge, çerçeve, anomali) | `Analysis` (cümle başına) |
| **Infrastructure** | Persistans, AI backend soyutlaması, önbellekleme, kurtarma | Alembic-versioned DB, önbellek |
| **Observability** | Metrikler, izleme, prompt versiyonlama | Prometheus + Grafana |
| **Quality Assurance** | Altın veri seti değerlendirmesi, belirsizlik puanlama, drift tespiti | `QualityReport`, `UncertaintyScore` |
| **Interface** | CLI (`typer`) + gelecek REST API (`FastAPI`) | Okunabilir raporlar & yapısal export |

---

## 2. Mimari

### 2.1 Genel Mimari — Katmanlı Görünüm

```mermaid
graph TB
    subgraph INTERFACES["🖥️ INTERFACES"]
        CLI["CLI (Typer + Rich)"]
        API["Future: FastAPI REST"]
    end

    subgraph APPLICATION["⚙️ APPLICATION"]
        CMD_BUILD["BuildDatabaseCommand"]
        CMD_ANALYZE["RunAnalysisCommand"]
        CMD_FAIL["RunFailCheckCommand"]
        QUERIES["Query Objects"]
        PIPELINE["AnalysisPipeline"]
        CONSENSUS["ConsensusService"]
    end

    subgraph DOMAIN["🧠 DOMAIN CORE"]
        SENTIMENT["SentimentService\n(DIPLO + VADER)"]
        RISK["RiskService\n(SBI + DKI)"]
        HEDGING["HedgingService\n(Hyland 1995)"]
        FRAMING["FramingService\n(Entman 1993)"]
        ANOMALY["CrossAnomalyService\n(10 Kural)"]
        TOPIC["TopicService\n(TF-IDF + BERTopic)"]
        TEMPORAL["TemporalAnalyzer\n(CUSUM + JSD)"]
        NER["NERService\n(spaCy GPE/ORG)"]
    end

    subgraph INFRA["🏗️ INFRASTRUCTURE"]
        DB["SQLAlchemy 2.0 async\n+ Alembic"]
        AI["AI Clients\n(Ollama/Claude/Gemini/Groq)"]
        CACHE["Cache\n(DiskCache + Redis)"]
        RECOVERY["6-Level JSON\nRecovery Engine"]
        OBS["Observability\n(Prometheus)"]
        QUALITY["Quality\n(DeepEval + Golden DS)"]
    end

    subgraph CONFIG["⚙️ CONFIG"]
        SETTINGS["Pydantic Settings\n(.env)"]
        LOGGING["Structlog"]
    end

    INTERFACES --> APPLICATION
    APPLICATION --> DOMAIN
    APPLICATION --> INFRA
    DOMAIN --> INFRA
    INFRA --> CONFIG

    style INTERFACES fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style APPLICATION fill:#0f2746,stroke:#60a5fa,color:#e2e8f0
    style DOMAIN fill:#052e16,stroke:#34d399,color:#e2e8f0
    style INFRA fill:#2d1515,stroke:#f87171,color:#e2e8f0
    style CONFIG fill:#1c1917,stroke:#a3a3a3,color:#e2e8f0
```

### 2.2 Veri Akışı — Cümle Düzeyinde Pipeline

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant CMD as BuildCommand
    participant INGEST as IngestService
    participant DB as Database
    participant PIPELINE as AnalysisPipeline
    participant AI as AI Client
    participant RECOVERY as RecoveryEngine
    participant CACHE as Cache

    CLI->>CMD: bbpaxdata build --transcript transcript.json
    CMD->>INGEST: parse_transcript()
    INGEST->>INGEST: SHA-256 idempotency check
    INGEST->>DB: upsert Speakers, Segments, Sentences

    CMD->>PIPELINE: run_analysis(segments)
    loop Her Cümle için
        PIPELINE->>CACHE: check(sha256(text))
        alt Cache hit
            CACHE-->>PIPELINE: cached_analysis
        else Cache miss
            PIPELINE->>AI: generate(prompt)
            AI-->>PIPELINE: raw_json_text
            PIPELINE->>RECOVERY: recover(raw_json_text)
            RECOVERY-->>PIPELINE: structured_dict
            PIPELINE->>CACHE: store(sha256(text), result)
        end
        PIPELINE->>DB: upsert Analysis
    end
    CMD-->>CLI: ✅ Analysis complete
```

### 2.3 Domain Model — Varlık İlişkisi

```mermaid
erDiagram
    TRANSCRIPT {
        string id PK
        string title
        string source
        datetime created_at
        string language
    }
    SPEAKER {
        string id PK
        string name
        string role
        string country
        float power_level
        string bloc_type
    }
    SEGMENT {
        string id PK
        string transcript_id FK
        string speaker_id FK
        int order_index
        string text
        float duration
    }
    SENTENCE {
        string id PK
        string segment_id FK
        string speaker_id FK
        int global_sent_order
        string text
        float sentiment_score
        float risk_score
        float hedging_score
        string diplomatic_tone
        string dominant_frame
        string dominant_topic
    }
    ANALYSIS {
        string id PK
        string sentence_id FK
        float ai_sentiment_score
        float ai_risk_score
        float sbi_score
        float dki_score
        float anomaly_score
        string risk_level
        json ai_raw_output
        bool has_ai_output
    }
    QUALITY_REPORT {
        string id PK
        string analysis_id FK
        float uncertainty_score
        float accuracy_vs_golden
        string review_status
    }

    TRANSCRIPT ||--o{ SPEAKER : "has"
    TRANSCRIPT ||--o{ SEGMENT : "contains"
    SPEAKER ||--o{ SEGMENT : "speaks"
    SEGMENT ||--o{ SENTENCE : "contains"
    SPEAKER ||--o{ SENTENCE : "spoken_by"
    SENTENCE ||--|| ANALYSIS : "analyzed_as"
    ANALYSIS ||--o| QUALITY_REPORT : "evaluated_by"
```

---

## 3. Analitik Pipeline

### 3.1 Ön İşleme (Pre-processing)

```mermaid
flowchart LR
    RAW["📄 Ham Metin"] --> ENCODE["🔧 Encoding\nNormalization\n(ftfy + unicodedata)"]
    ENCODE --> TOKENIZE["✂️ Tokenization\n(Kelime + Cümle)"]
    TOKENIZE --> LEMMA["📚 Lemmatization\n(spaCy tr/en)"]
    LEMMA --> POS["🏷️ POS Tagging\n(Dependency Parser)"]
    POS --> NER["🌍 NER\n(GPE, ORG, PERSON)"]
    NER --> STOP["🚫 Stopword\nFiltering\n(negasyon korunur)"]
    STOP --> FEAT["📊 Feature\nExtraction\n(TF-IDF, N-gram,\nEmbeddings)"]

    style RAW fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style FEAT fill:#052e16,stroke:#34d399,color:#e2e8f0
```

| Adım | Yöntem | Amaç |
|------|--------|-------|
| Tokenization | Kelime + cümle düzeyi | Tüm downstream görevler için temel |
| Encoding Normalization | `ftfy` + `unicodedata` | Türkçe/Arapça/Kiril mojibake düzeltme |
| Lemmatization | spaCy (`tr_core_news_trf`, `en_core_web_trf`) | Morfolojik varyantları standartlaştırma |
| POS Tagging | spaCy dependency parser | Sözdizimsel özellik çıkarımı |
| NER | spaCy + özel GPE modeli | Jeopolitik varlık tespiti |
| Stopword Filtering | Alan-farkında (negasyon *not*, *never* korunur) | Retorik açıdan yüklü token'ları koruma |

### 3.2 Özellik Çıkarımı

| Özellik | Teknik | Granülarlik |
|---------|--------|-------------|
| TF-IDF | Scikit-learn / özel | Segment düzeyinde anahtar kelime sıralaması |
| N-gram | Bigram / trigram frekansı | Collocation & retorik örüntü tespiti |
| Embeddings | Bağlamsal (transformer tabanlı) | Semantik benzerlik & kümeleme |

---

## 4. Domain Servisleri — Teknik Detaylar

### 4.1 Duygu Analizi (`SentimentService`)

Sistem, diplomatik söylemler için özelleştirilmiş **DIPLO leksikonu** ile VADER'ı birleştirir.

#### Temel Formül

Saf DIPLO skoru şu şekilde hesaplanır:

$$\text{diplo\_compound} = \text{VADER\_compound} + \left(\sum_{p \in \text{matched\_phrases}} v_p\right) \times 0.05$$

Burada $v_p \in [-0.9, +0.7]$ aralığında diplomatik değerlik puanlarıdır. Sonuç $[-1, 1]$ aralığına sıkıştırılır.

#### Negasyon-Farkında Skor

Sol-pencere negasyon tespiti *(Jia & Liang, 2017)*:

$$\text{score}_{\text{neg-aware}} = \begin{cases}
-v_p \times 0.8 & \text{eğer } \exists \; n \in \text{NEGATION\_WORDS} \; \text{window}[i-N:i] \\
v_p & \text{aksi hâlde}
\end{cases}$$

Burada $N = 4$ (negasyon pencere boyutu) ve $0.8$ attenuation faktörüdür.

```mermaid
flowchart TD
    TEXT["📝 Cümle Girişi"] --> TOKENIZE["Token'lara Ayır\n(contraction korumalı)"]
    TOKENIZE --> DIPLO_MATCH["DIPLO Leksikonu ile\nEşleştir (phrase-first)"]
    DIPLO_MATCH --> NEG_CHECK{"Sol-pencere\nNegasyon Var mı?\n[i-4 : i]"}
    NEG_CHECK -- "Evet" --> ATTENUATE["Polarite Ters Çevir\n-v × 0.8"]
    NEG_CHECK -- "Hayır" --> KEEP["v olarak koru"]
    ATTENUATE & KEEP --> SUM["Toplam Düzeltme\nΣ × 0.05"]
    SUM --> VADER["VADER compound\nekle"]
    VADER --> CLAMP["[-1, 1] aralığına\nsıkıştır"]
    CLAMP --> CLASSIFY["Kategori Sınıflandır\nCONFRONTATIONAL / CONCERNED\nNEUTRAL / CONSTRUCTIVE / COOPERATIVE"]

    style TEXT fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style CLASSIFY fill:#052e16,stroke:#34d399,color:#e2e8f0
```

**Duygu Eşikleri:**

| Skor Aralığı | Kategori |
|-------------|---------|
| $s \leq -0.40$ | `CONFRONTATIONAL` |
| $-0.40 < s \leq -0.10$ | `CONCERNED` |
| $-0.10 < s < 0.10$ | `NEUTRAL_CAUTIOUS` |
| $0.10 \leq s < 0.35$ | `CONSTRUCTIVE` |
| $s \geq 0.35$ | `COOPERATIVE` |

---

### 4.2 Risk Puanlama (`RiskService`)

Sistem iki adet bileşik indeks hesaplar: **SBI** (Söylemsel Baskı İndeksi) ve **DKI** (Diplomatik Konum İndeksi).

#### SBI — Söylemsel Baskı İndeksi

$$\text{SBI} = \frac{P_{\text{level}} \times W_{\text{demand}}}{2} + R_{\text{score}}$$

Burada:
- $P_{\text{level}} \in [0, 10]$: Konuşmacının güç düzeyi
- $W_{\text{demand}} \in [0, 1]$: Talebin ağırlığı (*suggest*=0.5, *should*=0.7, *must/demand*=0.9)
- $R_{\text{score}} \in [0, 10]$: Baz risk skoru

#### DKI — Diplomatik Konum İndeksi

$$\text{DKI} = \Big(d_{\text{norm}} \cdot 0.4 + (1 - r_{\text{norm}}) \cdot 0.3 + d_{\text{req}} \cdot 0.2 + (1 - m_{\text{norm}}) \cdot 0.1\Big) \times 2 - 1$$

Burada:
- $d_{\text{norm}}$: Normalize diplomatik skor $\in [0, 1]$
- $r_{\text{norm}}$: Normalize risk skoru $\in [0, 1]$
- $d_{\text{req}}$: Normalize talep yoğunluğu $\in [0, 1]$
- $m_{\text{norm}}$: Normalize manipülasyon skoru $\in [0, 1]$

Sonuç: $\text{DKI} \in [-1, 1]$ (−1 = tam düşmanca, +1 = tam işbirlikçi).

#### Bağlamsal Risk (NER Çarpanı)

$$R_{\text{ctx}} = \min\!\left(10,\; R_{\text{base}} \times \mu\right)$$

$$\mu = \begin{cases} 1.5 & \text{GPE veya ORG varlığı tespit edilirse} \\ 1.2 & \text{yalnızca PERSON varlığı tespit edilirse} \\ 1.0 & \text{varlık yok} \end{cases}$$

**Risk Sinyal Ağırlıkları:**

| Kategori | Örnekler | Puan |
|----------|---------|------|
| CRITICAL | *red line*, *ultimatum*, *unacceptable*, *military option* | 3 |
| HIGH | *escalate*, *retaliate*, *decisive actions*, *deep strikes* | 2 |
| BASE | Diğer tüm sinyal kelimeleri | 1 |

*Akademik referans: Baldwin (1985) — zorlayıcı diplomasi teorisi; Kıyılar (2020).*

---

### 4.3 Çit (Hedge) Dili Analizi (`HedgingService`)

**Hyland (1995, 2005)** taksonomisinse dayanan epistemic ve stil hedge kategorileri:

```mermaid
graph LR
    HEDGE["🛡️ Hedge Tespiti"] --> EH["Epistemic High\n(might, could, possibly)\nAğırlık: 0.8"]
    HEDGE --> EM["Epistemic Medium\n(typically, generally)\nAğırlık: 0.5"]
    HEDGE --> AH["Anti-Hedge\n(definitely, certainly)\nAğırlık: -0.3"]
    HEDGE --> APX["Approximator\n(roughly, about)\nAğırlık: 0.4"]
    HEDGE --> SH["Shield\n(I'm not sure, to my knowledge)\nAğırlık: 0.6"]
    HEDGE --> ATTR["Attribution\n(reportedly, allegedly)\nAğırlık: 0.3"]

    EH & EM & AH & APX & SH & ATTR --> SCORE["📊 Hedge Skoru\n[0, 1]"]
    SCORE --> INTERP["Yorum\n0.6+ = Yüksek Belirsizlik\n0.1-0.6 = Orta\n< 0.1 = Doğrudan Dil"]

    style HEDGE fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style INTERP fill:#052e16,stroke:#34d399,color:#e2e8f0
```

#### Hedge Yoğunluk Formülü

$$H_{\text{score}} = \frac{\sum_{c \in \text{categories}} w_c \cdot n_c}{\max(1, N_{\text{matches}})}$$

Burada $w_c$ kategori ağırlığı, $n_c$ o kategorideki eşleşme sayısı ve $N_{\text{matches}}$ toplam eşleşme sayısıdır.

*Akademik referans: Hyland, K. (1995). The Author in the Text: Hedging Scientific Writing. Hong Kong Papers in Linguistics and Language Teaching.*

---

### 4.4 Çerçeveleme Analizi (`FramingService`)

**Entman (1993)** dört-fonksiyonlu çerçeveleme modelini uygular:

```mermaid
mindmap
  root((Çerçeveleme\nAnalizi))
    Problem Tanımı
      Konu-varlık ko-oluşumu
      NER GPE entegrasyonu
    Nedensel Yorum
      dependency path nsubj→ROOT→obl:agent
      Pasif yapı agent tespiti
    Ahlaki Değerlendirme
      Appraisal sistemi
      Değerlendirici sıfat-varlık eşleşmesi
    Tedavi Önerisi
      Modal fiil + politika fiili kümesi
      should, must + GPE bağlamı
```

**Çerçeve Türleri (v1.0.0):**

| Frame Türü | Tanımı |
|-----------|--------|
| `CONFLICT_FRAME` | Savaş/çatışma odaklı çerçeve |
| `HUMANITARIAN_FRAME` | İnsani kriz odaklı çerçeve |
| `SOVEREIGNTY_FRAME` | Egemenlik ve toprak bütünlüğü |
| `SECURITY_FRAME` | Güvenlik tehdidi çerçeve |
| `LEGAL_FRAME` | Uluslararası hukuk ve yaptırım |
| `DETERRENCE_FRAME` | Caydırıcılık stratejisi |
| `PEACE_FRAME` | Diyalog ve uzlaşı |
| `THREAT_FRAME` | Tehdit ve tehlike |
| `MULTILATERAL_FRAME` | Çok taraflı diplomatik eylem |
| `NEGOTIATION_FRAME` | Reform / müzakere süreci |

*Akademik referans: Entman, R.M. (1993). Framing: Toward Clarification of a Fractured Paradigm. Journal of Communication, 43(4), 51–58.*

---

### 4.5 Çapraz Anomali Tespiti (`CrossAnomalyService`)

Plugin mimarisi — her kural `AnomalyRule` protokolünü uygular.

```mermaid
flowchart TD
    ANALYSIS["📊 Analysis Nesnesi"] --> RULES["Kural Motoru\n(Plugin Mimarisi)"]

    RULES --> R1["SentimentRiskDivergenceRule\nTsytsarau (2017) formülü"]
    RULES --> R2["HighRiskThresholdRule\nRisk ≥ 0.8"]
    RULES --> R3["NegativeSentimentRule\nDuygu ≤ -0.7"]
    RULES --> R4["PowerAsymmetryRule\nAsimetri > 0.5 + δ < -0.3"]
    RULES --> R5["CheapTalkAnomalyRule\nTrager (2010) proxy"]

    R1 & R2 & R3 & R4 & R5 --> AGGREGATE["Toplam Anomali Skoru\nmin(Σ katkılar, 1.0)"]
    AGGREGATE --> RISK_LEVEL["Risk Seviyesi\nLOW / MEDIUM / HIGH / CRITICAL"]

    style ANALYSIS fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style RISK_LEVEL fill:#7f1d1d,stroke:#f87171,color:#e2e8f0
```

#### Tsytsarau Çelişki Formülü

$$C = \frac{n \cdot M_2 - M_1^2}{\left(\vartheta \cdot n^2 + M_1^2\right) \cdot W}$$

Burada:
- $M_1 = \frac{1}{n}\sum p_i$ (ortalama polarite)
- $M_2 = \frac{1}{n}\sum p_i^2$ (ikinci moment)
- $\vartheta = 0.1$ (regularizasyon)
- $W = n$ (ağırlıklandırma)

Negasyon düzeltmesinden sonra $C_{\text{adj}} > 0.1$ ise `SENTIMENT_RISK_DIVERGENCE` anomalisi tetiklenir.

*Akademik referans: Tsytsarau, M., Palpanas, T., & Denecke, K. (2017). Identifying Sentiment-based Contradictions. Data Science and Engineering.*

**Anomali Türleri (v1.0.0):**

| Anomali | Tetikleyici Koşul | Kategori |
|---------|-------------------|----------|
| `RISK_HEDGING_CONFLICT` | Risk ≥ 7 AND Hedge ≥ 0.6 | Deception Pattern |
| `NEGATIVE_CONFRONTATIONAL_AMPLIFICATION` | Duygu ≤ -0.5 AND Ton = confrontational | Agresif Söylem |
| `VELVET_GLOVE_CONFRONTATION` | Duygu ≥ 0.3 AND Ton = confrontational | Örtülü Baskı |
| `HIGH_RISK_CONCILIATORY_MASK` | Risk ≥ 7 AND Ton = cooperative | Deception Pattern |
| `DIRECT_MANIPULATION_LOW_HEDGE` | Manip ≥ 0.7 AND Hedge ≤ 0.2 | Manipulation |
| `DOMINANT_ACTOR_PRESSURE` | Güç ≥ 8 AND SBI ≥ 7 AND Risk ≥ 6 | Power Dynamics |
| `VAGUE_DEMAND_PLAUSIBLE_DENIABILITY` | Hedge ≥ 0.6 AND Risk ≥ 4 | Strategic Ambiguity |
| `CONFLICT_FRAME_POSITIVE_WRAP` | Frame=conflict AND Duygu ≥ 0.3 | Framing Strategy |
| `INCONSISTENCY_PLUS_MANIPULATION` | Manip ≥ 0.5 AND |AI−Formül| ≥ 0.5 | Deception Pattern |
| `NEGATIVE_APPRAISAL_PERSUASIVE_TONE` | Appraisal=neg AND Duygu ≤ -0.5 AND Kibarlık ≥ 0.6 | Persuasion Strategy |

---

### 4.6 Konu Modellemesi (`TopicService`)

| Yöntem | Kullanım Amacı |
|--------|---------------|
| TF-IDF + Anahtar Kelime | Segment düzeyinde baz konu sıralaması |
| BERTopic | Tematik drift tespiti için semantik kümeleme |

**Konu Kategorileri (v1.0.0):**
`Gazze_Filistin_İsrail` · `Ukrayna_Rusya` · `BM_Reformu` · `Ekonomi_Ticaret_Enerji` · `Güvenlik_Çatışma`

---

### 4.7 Zamansal Drift Analizi (`TemporalAnalyzer`)

```mermaid
flowchart LR
    subgraph DRIFT_TYPES["Drift Türleri"]
        SENTIMENT_DRIFT["SENTIMENT\nCUSUM Algoritması"]
        TOPIC_DRIFT["TOPIC\nJensen-Shannon Div."]
        LEXICAL_DRIFT["LEXICAL\nMATTR Metriği"]
        TONE_DRIFT["TONE\nMarkov Geçiş Matrisi"]
        RISK_DRIFT["RISK\nSlop Değişim Tespiti"]
    end

    DATA["Zaman Serisi\nVerileri"] --> SENTIMENT_DRIFT
    DATA --> TOPIC_DRIFT
    DATA --> LEXICAL_DRIFT
    DATA --> TONE_DRIFT
    DATA --> RISK_DRIFT

    SENTIMENT_DRIFT & TOPIC_DRIFT & LEXICAL_DRIFT & TONE_DRIFT & RISK_DRIFT --> EVENTS["DriftEvent[]\n(severity: LOW/MEDIUM/HIGH/CRITICAL)"]

    style DATA fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style EVENTS fill:#052e16,stroke:#34d399,color:#e2e8f0
```

#### CUSUM Duygu Drift Tespiti

$$\text{CUSUM}^+_t = \max\!\left(0,\; \text{CUSUM}^+_{t-1} + z_t - k\right)$$
$$\text{CUSUM}^-_t = \min\!\left(0,\; \text{CUSUM}^-_{t-1} + z_t + k\right)$$

Burada $z_t = \frac{s_t - \mu}{\sigma}$ (standardize duygu skoru), $k = 0.3$ (threshold) ve $h = 2.0$ (drift eşiği).

#### Jensen-Shannon Divergence (Konu Drift)

$$\text{JSD}(P \| Q) = \frac{1}{2} D_{\text{KL}}(P \| M) + \frac{1}{2} D_{\text{KL}}(Q \| M)$$

Burada $M = \frac{P + Q}{2}$ ve $D_{\text{KL}}(P \| Q) = \sum_x P(x) \log\frac{P(x)}{Q(x)}$.

#### Ek İstatistiksel Metrikler (v1.0.0)

| Metrik | Formül / Yöntem | Açıklama |
|--------|----------------|----------|
| **MTLD** | Type-Token Ratio stabilizasyon noktası | Sözcük çeşitlilik zenginliği |
| **GARCH(1,1)** | $\sigma^2_t = \omega + \alpha\varepsilon^2_{t-1} + \beta\sigma^2_{t-1}$ | Duygu oynaklık rejimi |
| **Entity Half-Life** | $f(t) = f_0 \cdot e^{-\lambda t}$ | Varlık saliency bozunumu |
| **Lexical Entropy** | $H = -\sum p_i \log_2 p_i$ | Shannon entropi (sözcük dağılımı) |
| **Red Line Flexibility** | Concession Count / Red Line Count | Kırmızı çizgi geri adım indeksi |

---

## 5. Altyapı

### 5.1 AI Backend Soyutlaması

```python
class AIClient(ABC):
    async def generate(self, prompt: str, **kwargs) -> str: ...
    async def embed(self, text: str) -> list[float]: ...

# Desteklenen backend'ler (v1.0.0)
class OllamaClient(AIClient): ...       # Yerel LLM (Llama3, Mistral vb.)
class AnthropicClient(AIClient): ...    # Claude (Haiku / Sonnet / Opus)
class GeminiClient(AIClient): ...       # Google Gemini (Flash / Pro)
class GroqClient(AIClient): ...         # Groq (hızlı çıkarım)

class AIClientFactory:
    @staticmethod
    def create(backend: BackendEnum) -> AIClient: ...
```

```mermaid
flowchart TD
    REQUEST["AI İsteği"] --> PRIMARY["Birincil Backend\n(Yapılandırılmış)"]
    PRIMARY -->|Başarı| RESULT["✅ Sonuç"]
    PRIMARY -->|Hata / Timeout| SECONDARY["İkincil Backend\n(Fallback)"]
    SECONDARY -->|Başarı| RESULT
    SECONDARY -->|Hata| TERTIARY["Üçüncül Backend\n(Son çare)"]
    TERTIARY -->|Başarı| RESULT
    TERTIARY -->|Hata| RECOVERY["6-Seviyeli JSON\nKurtarma"]

    RECOVERY -->|L1 Direct| R1["✅ Direct JSON parse"]
    RECOVERY -->|L2 Stripped| R2["✅ Markdown bloğu sıyrılır"]
    RECOVERY -->|L3 FirstBlock| R3["✅ İlk JSON bloğu bulunur"]
    RECOVERY -->|L4 Partial| R4["✅ Kısmi KV çifti kurtarma"]
    RECOVERY -->|L5 KeyValue| R5["✅ Geniş regex eşleştirme"]
    RECOVERY -->|L6 SchemaDefault| R6["✅ Varsayılan şema uygulanır"]

    style REQUEST fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style RESULT fill:#052e16,stroke:#34d399,color:#e2e8f0
    style RECOVERY fill:#422006,stroke:#f97316,color:#e2e8f0
```

### 5.2 Önbellekleme Stratejisi

| Backend | Sürücü | TTL Stratejisi |
|---------|--------|---------------|
| Disk | `diskcache` | 24 saat (varsayılan) |
| Redis | `redis-py` | LRU + açık geçersiz kılma |

Önbellek anahtarı: `SHA-256(prompt_text + model_version)` — prompt değişirse otomatik geçersiz.

### 5.3 Veritabanı

| Bileşen | Teknoloji |
|---------|-----------|
| ORM | SQLAlchemy 2.0 (async) |
| Migrasyonlar | Alembic |
| Şema | `Sentence → Segment → Speaker → Analysis → QualityReport` |
| Varsayılan | SQLite (geliştirme) |

---

## 6. Gözlemlenebilirlik

```mermaid
graph LR
    subgraph APP["BB-PAXDATA"]
        METRICS["Prometheus\nMetrics Endpoint\n:8000/metrics"]
    end

    subgraph MONITORING["İzleme Yığını"]
        PROM["Prometheus\n:9090"]
        GRAFANA["Grafana\n:3000"]
    end

    subgraph OPTIONAL["Opsiyonel"]
        LANGSMITH["LangSmith\n(Prompt izleme)"]
    end

    APP --> PROM
    PROM --> GRAFANA
    APP --> LANGSMITH

    style APP fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style MONITORING fill:#052e16,stroke:#34d399,color:#e2e8f0
    style OPTIONAL fill:#1c1917,stroke:#a3a3a3,color:#e2e8f0
```

| Metrik | Tip | Etiketler |
|--------|-----|-----------|
| `ai_backend_latency_seconds` | Histogram | `backend`, `operation` |
| `cache_hit_rate` | Gauge | `backend` (disk/redis) |
| `batch_fallback_count` | Counter | `from_backend`, `to_backend` |
| `json_recovery_total` | Counter | `level`, `result` |
| `prompt_version` | Info | `hash`, `registered_at` |

---

## 7. Kalite Güvencesi

| Bileşen | Amaç |
|---------|------|
| `GoldenDataset` | 100 el-etiketli cümle (ground truth) |
| `QualityEvaluator` | DeepEval / özel puanlayıcı (altın kümeye karşı) |
| `UncertaintyScorer` | AI çıktısı başına entropi tabanlı güven |
| `DataContractValidator` | Pandera giriş şema doğrulaması |
| Idempotency | Transkript başına SHA-256 anahtarı (tekrar alımı engeller) |

#### Belirsizlik Puanlama

$$U = H(p) = -\sum_{c} p_c \log_2 p_c$$

Burada $p_c$ çıktının $c$ kategorisine ait olma olasılığı. Yüksek entropi → yüksek belirsizlik → insan incelemesi önerilir.

---

## 8. Hızlı Başlangıç Kılavuzu

> Bu bölüm BB-PAXDATA'yı kuracak ve çalıştıracak kişiler için adım adım bir mini kılavuzdur.

### 8.1 Gereksinimler

| Gereksinim | Versiyon | Zorunlu? |
|------------|---------|---------|
| Python | ≥ 3.12 | ✅ |
| Poetry | ≥ 1.8 | ✅ |
| Docker + Docker Compose | Herhangi | İzleme için |
| Ollama | Herhangi | Yerel LLM için |

### 8.2 Kurulum

```bash
# 1. Repoyu klonla
git clone https://github.com/BBgitaccount/BB-PAXDATA.git
cd BB-PAXDATA

# 2. Environment dosyasını oluştur
cp .env.example .env
# .env dosyasını düzenle — AI API anahtarlarını ekle
```

**.env Dosyası Yapılandırması:**

```ini
# AI Backend Anahtarları (en az biri gerekli)
OLLAMA_BASE_URL=http://localhost:11434   # Yerel LLM için (ücretsiz)
ANTHROPIC_API_KEY=your_claude_key       # Claude için
GEMINI_API_KEY=your_gemini_key          # Google Gemini için
GROQ_API_KEY=your_groq_key             # Hızlı çıkarım için

# Veritabanı
DATABASE_URL=sqlite:///./data/paxdata.db

# Önbellek
CACHE_BACKEND=diskcache
CACHE_DIR=./data/cache

# Sistem Ayarları
BATCH_SIZE=100
WORKER_THREADS=4
QUALITY_THRESHOLD=0.85
LOG_LEVEL=INFO
```

```bash
# 3. Bağımlılıkları kur
poetry install

# 4. Sanal ortamı aktifleştir
poetry shell

# 5. Veritabanı migrasyonlarını çalıştır
alembic upgrade head
```

### 8.3 İlk Analiz

```bash
# Transkript veritabanına al
bbpaxdata build --transcript data/sample_transcript.json

# Analiz pipeline'ını çalıştır
bbpaxdata analyze --transcript-id <id>

# Anomali ve risk denetimi
bbpaxdata failcheck --report-format html

# Veritabanı doğrulama
bbpaxdata validate db --strict
```

### 8.4 İzleme Kurulumu (İsteğe Bağlı)

```bash
# Prometheus + Grafana başlat
docker compose up -d prometheus grafana

# Python metrics endpoint'i başlat (bbpaxdata çalışırken otomatik başlar)
# Manuel kontrol:
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000  (admin / bbpaxdata2024)
```

### 8.5 Makefile Kısayolları

```bash
make install          # Poetry bağımlılıklarını kur
make lint             # ruff + black ile kod stili kontrolü
make typecheck        # mypy strict tip kontrolü
make test             # pytest (tüm testler)
make test-cov         # Kapsam raporu ile pytest
make migrate          # Legacy DB migrasyonu
make migrate-dry      # Kuru çalıştırma (değişiklik yok)
make validate         # DB veri doğrulaması
make validate-json    # JSON rapor çıktısı
make clean            # __pycache__ ve .pyc dosyaları temizle
```

### 8.6 Shell Tamamlama Kurulumu

```bash
# Bash için
make install-completion-bash

# Zsh için
make install-completion-zsh
```

---

## 9. CLI Referansı

```
bbpaxdata [KOMUT] [SEÇENEKLER]

Komutlar:
  build        Transkriptleri veritabanına al
  analyze      Analiz pipeline'ını çalıştır
  failcheck    Anomali ve risk denetimi çalıştır
  validate     Veritabanı bütünlüğünü doğrula
  migrate      Legacy veritabanından veri taşı
  completions  Shell tamamlama kur/kaldır
  review       İnsan inceleme arayüzü

Ortak Bayraklar:
  --help       Yardım göster
  --verbose    Ayrıntılı çıktı
  --dry-run    Değişiklik yapmadan simüle et
  --output     Çıktı yolunu belirt
```

---

## 10. Proje Yol Haritası

```mermaid
gantt
    title BB-PAXDATA Geliştirme Yol Haritası
    dateFormat  YYYY-MM
    axisFormat  %Y-%m

    section Tamamlandı ✅
    Faz 0 - Proje İskeleti ve CI/CD         :done, 2024-01, 2024-02
    Faz 1 - Domain Core (enum, model, servis):done, 2024-02, 2024-04
    Faz 2 - SQLAlchemy ORM ve AI İstemciler :done, 2024-04, 2024-08

    section Devam Ediyor 🔄
    Faz 2 - Önbellekleme ve Recovery        :active, 2024-08, 2025-01

    section Planlanmış ⏳
    Faz 3 - Gözlemlenebilirlik             :2025-01, 2025-03
    Faz 4 - Kalite Güvencesi               :2025-03, 2025-06
    Faz 5 - NLP Güçlendirme (spaCy+SHAP)  :2025-06, 2025-09
    Faz 6 - CLI Geliştirme                 :2025-09, 2025-11
    Faz 7 - Use Case Entegrasyonu          :2025-11, 2026-01
    Faz 8 - Entegrasyon Testleri ve Docs   :2026-01, 2026-04
```

| Faz | Teslimat | Durum |
|-----|---------|-------|
| **0** | Proje iskeleti, CI/CD, linting | ✅ Tamamlandı |
| **1** | Domain core: enum'lar, Pydantic modeller, baz servisler | ✅ Tamamlandı |
| **2** | SQLAlchemy ORM, Alembic, AI istemciler, önbellekleme | 🔄 Devam Ediyor |
| **3** | Gözlemlenebilirlik: Prometheus, Grafana, prompt kaydı | ⏳ Planlandı |
| **4** | Kalite: Altın veri seti, değerlendirici, belirsizlik, drift | ⏳ Planlandı |
| **5** | NLP güçlendirme: spaCy dependency, çok dilli, SHAP | ⏳ Planlandı |
| **6** | CLI: Typer komutları, shell tamamlama, migrasyon | ⏳ Planlandı |
| **7** | Kullanım senaryoları: eski v4/v5 mantığını kapsama | ⏳ Planlandı |
| **8** | Entegrasyon testleri, MkDocs, Docker Compose, belgeler | ⏳ Planlandı |

---

## 11. Bilimsel Metodoloji

### 11.1 Yöntem Özeti

| Modül | Yöntem | Akademik Temel |
|-------|--------|----------------|
| **Sentiment** | Negasyon-farkında DIPLO + VADER | Jia & Liang (2017); Socher et al. (2013) |
| **Risk** | SBI / DKI bileşik indeks | Baldwin (1985); Kıyılar (2020) |
| **Hedging** | Hyland (1995) taksonomisi + yoğunluk oranı | Hyland (1995, 2005) |
| **Framing** | Entman (1993) dört-fonksiyonlu model + salience | Entman (1993) |
| **Anomaly** | 10 kurallı çapraz-anomali tensörü | Tsytsarau et al. (2017); Trager (2010) |
| **Topic** | TF-IDF + BERTopic dinamik modelleme | Grootendorst (2022) |
| **Dependency** | spaCy SVO çıkarımı + diplomatik alan budama | Manning et al. (2014) |
| **Explainability** | SHAP + LIME hibrit | Lundberg & Lee (2017); Ribeiro et al. (2016) |
| **Temporal** | CUSUM + JSD lexical drift + embedding centroid kayması | Page (1954); Lin (1991) |
| **Quality** | Tahmine dayalı entropi + ensemble anlaşmazlığı | Gal & Ghahramani (2016) |

### 11.2 Veri Akışı — Bilimsel Katmanlar

```mermaid
flowchart TB
    subgraph L1["L1: Kural Tabanlı (Deterministik)"]
        DIPLO["DIPLO Leksikonu\n(Phrase-first)"]
        RISK_SIG["Risk Sinyalleri\n(Ağırlıklı)"]
        HEDGE_LEX["Hedge Leksikonu\n(Regex tabanlı)"]
    end

    subgraph L2["L2: İstatistiksel (Stokastik)"]
        CUSUM["CUSUM\n(Drift tespiti)"]
        JSD["Jensen-Shannon\n(Dağılım farkı)"]
        GARCH["GARCH(1,1)\n(Oynaklık)"]
    end

    subgraph L3["L3: Makine Öğrenimi (Olasılıksal)"]
        BERTOPIC["BERTopic\n(Semantik küme)"]
        VADER_ML["VADER\n(Duygu lexicon ML)"]
        EMBEDDING["Sentence Transformers\n(Semantik benzerlik)"]
    end

    subgraph L4["L4: Büyük Dil Modelleri (Üretken)"]
        AI_ANALYST["AI Analyst\n(Claude/Gemini/Groq/Ollama)"]
        PROMPT_REG["Prompt Registry\n(Versiyonlanmış)"]
    end

    L1 --> CONSENSUS["Uzlaşı Motoru\n(Consensus Service)"]
    L2 --> CONSENSUS
    L3 --> CONSENSUS
    L4 --> CONSENSUS

    CONSENSUS --> FINAL["Son Analiz Skoru\n(Ağırlıklı birleşim)"]

    style L1 fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style L2 fill:#0f2746,stroke:#60a5fa,color:#e2e8f0
    style L3 fill:#052e16,stroke:#34d399,color:#e2e8f0
    style L4 fill:#2d1515,stroke:#f87171,color:#e2e8f0
    style FINAL fill:#422006,stroke:#f97316,color:#e2e8f0
```

---

## 12. Akademik Kaynaklar

> Aşağıdaki kaynaklar v1.0.0'de doğrudan uygulanan veya referans alınan çalışmalardır.

### Duygu Analizi

- **Socher, R., Perelygin, A., Wu, J. et al. (2013).** *Recursive Deep Models for Semantic Compositionality Over a Sentiment Treebank.* EMNLP 2013.
  > Cümle düzeyi negatif/pozitif sınıflandırma için temel. VADER'ın benzediği yaklaşımı hakkında bağlam sağlar.

- **Jia, L., & Liang, J. (2017).** *Negation and Speculation Scope Detection.* Chinese National Conference on Computational Linguistics.
  > `negation_aware_diplo()` işlevindeki **sol-pencere negasyon** yaklaşımının ($N=4$, $0.8$ attenuation) akademik temeli.

- **Hutto, C.J., & Gilbert, E.E. (2014).** *VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text.* ICWSM.
  > DIPLO sisteminin compound skora blend ettiği VADER'ın orijinal kaynağı.

### Risk ve Diplomatik Güç

- **Baldwin, D.A. (1985).** *Economic Statecraft.* Princeton University Press.
  > `contextual_risk()` işlevindeki NER çarpanı mantığının dayandığı coercive diplomacy teorisi.

- **Fearon, J.D. (1995).** *Rationalist Explanations for War.* International Organization, 49(3), 379–414.
  > SBI/DKI tasarımına ilham veren taahhüt maliyeti ve sinyal güvenilirliği çerçevesi.

- **Trager, R.F. (2010).** *Diplomatic Calculus in Uncharted Territory.* American Political Science Review, 104(2), 347–371.
  > `CheapTalkAnomalyRule` sınıfının `power_weighted_score` + `credibility` hesabının kuramsal temeli.

### Çit (Hedge) Dili

- **Hyland, K. (1995).** *The Author in the Text: Hedging Scientific Writing.* Hong Kong Papers in Linguistics and Language Teaching, 18, 33–42.
  > `HedgingService` sınıfının `epistemic_high`, `epistemic_medium`, `shield` ve `attribution` kategori taksonomi kaynağı.

- **Hyland, K. (2005).** *Metadiscourse: Exploring Interaction in Writing.* Continuum.
  > Akademik-diplomatik transferini destekleyen genişletilmiş hedge taksonomisi.

### Çerçeveleme Analizi

- **Entman, R.M. (1993).** *Framing: Toward Clarification of a Fractured Paradigm.* Journal of Communication, 43(4), 51–58.
  > `FramingService` sınıfının dört fonksiyonlu modelinin (Problem Tanımı, Nedensel Yorum, Ahlaki Değerlendirme, Tedavi Önerisi) teorik kaynağı.

### Anomali Tespiti

- **Tsytsarau, M., Palpanas, T., & Denecke, K. (2017).** *Identifying Sentiment-based Contradictions.* Data Science and Engineering, 2, 81–97.
  > `SentimentRiskDivergenceRule` içindeki $C = \frac{n \cdot M_2 - M_1^2}{(\vartheta \cdot n^2 + M_1^2) \cdot W}$ formülünün doğrudan kaynağı.

### Zamansal Drift ve İstatistik

- **Page, E.S. (1954).** *Continuous Inspection Schemes.* Biometrika, 41(1/2), 100–115.
  > `detect_sentiment_drift()` işlevinin kullandığı CUSUM (Cumulative Sum) algoritmasının orijinal makalesi.

- **Lin, J. (1991).** *Divergence Measures Based on the Shannon Entropy.* IEEE Transactions on Information Theory, 37(1), 145–151.
  > `_jensen_shannon_divergence()` işlevinin Jensen-Shannon Divergence tanımının kaynağı.

- **Covington, M.A., & McFall, J.D. (2010).** *Cutting the Gordian Knot: The Moving-Average Type–Token Ratio (MATTR).* Journal of Quantitative Linguistics, 17(2), 94–100.
  > `detect_lexical_drift()` içindeki MATTR metriğinin kaynağı.

- **Bollerslev, T. (1986).** *Generalized Autoregressive Conditional Heteroskedasticity.* Journal of Econometrics, 31(3), 307–327.
  > `estimate_sentiment_garch_volatility()` işlevinin GARCH(1,1) modelinin orijinal kaynağı.

### NLP Altyapı

- **Volansky, V., Ordan, N., & Wintner, S. (2015).** *On the Features of Translationese.* Literary and Linguistic Computing, 30(1), 98–118.
  > `CrossAnomalyService` içindeki "Translation Artifact" anomali türünün (POS n-gram dağılım kayması) referansı.

- **Grootendorst, M. (2022).** *BERTopic: Neural topic modeling with a class-based TF-IDF procedure.* arXiv:2203.05794.
  > `TopicService` içindeki BERTopic dinamik konu modellemesinin kaynağı.

- **Lundberg, S.M., & Lee, S.I. (2017).** *A Unified Approach to Interpreting Model Predictions.* NeurIPS 2017.
  > `ExplainabilityService` içindeki SHAP değerleri yönteminin kaynağı.

- **Ribeiro, M.T., Singh, S., & Guestrin, C. (2016).** *"Why Should I Trust You?": Explaining the Predictions of Any Classifier.* KDD 2016.
  > `ExplainabilityService` içindeki LIME hibrit açıklanabilirlik yaklaşımının kaynağı.

---

<div align="center">

---

<!-- Animated footer SVG -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 60" width="900" height="60">
  <defs>
    <linearGradient id="footerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#0f0c29" />
      <stop offset="50%" style="stop-color:#302b63" />
      <stop offset="100%" style="stop-color:#24243e" />
    </linearGradient>
  </defs>
  <rect width="900" height="60" rx="8" fill="url(#footerGrad)"/>
  <text x="450" y="28" text-anchor="middle" font-family="'Segoe UI', Arial, sans-serif"
        font-size="13" fill="#94a3b8">
    BB-PAXDATA v1.0.0 · Diplomatic Discourse Analysis Engine
  </text>
  <text x="450" y="46" text-anchor="middle" font-family="'Segoe UI', Arial, sans-serif"
        font-size="11" fill="#64748b">
    Bu döküman v1.0.0'e özeldir · Sistem geliştikçe içerik değişecektir
  </text>
</svg>

**[⬆ Başa Dön](#-i̇çindekiler)**

</div>
