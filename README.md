<div align="center">

![BB-PAXDATA Banner](assets/banner.svg)

<br/>

[![Version](https://img.shields.io/badge/version-1.0.0-a78bfa?style=for-the-badge&logo=semantic-release&logoColor=white)](https://github.com/BBgitaccount/BB-PAXDATA)
[![Python](https://img.shields.io/badge/Python-3.12+-3b82f6?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-34d399?style=for-the-badge&logo=gnu&logoColor=white)](./LICENSE)
[![Tests](https://img.shields.io/badge/Tests-pytest-f472b6?style=for-the-badge&logo=pytest&logoColor=white)](./tests)
[![Code Style](https://img.shields.io/badge/Code%20Style-ruff%20%2B%20black-facc15?style=for-the-badge&logo=python&logoColor=black)](./pyproject.toml)

---

*Diplomatik transkriplerin yapısal çıkarımı, çok katmanlı anotasyonu ve kantitatif çerçeveleme analizi için geliştirilmiş **açık kaynaklı NLP motoru**.*

> [!WARNING]
> **Bu döküman v1.0.0'e özeldir.** Sistem geliştikçe API'ler, formüller ve mimariler önemli ölçüde değişebilir. Güncel bilgi için her zaman etiketli sürümün dökümantasyonuna başvurun.

</div>

---

## 📋 İçindekiler

| # | Bölüm |
|---|-------|
| 1 | [Hızlı Başlangıç Kılavuzu](#1-hızlı-başlangıç-kılavuzu) |
| 2 | [Sistem Genel Bakış](#2-sistem-genel-bakış) |
| 3 | [Mimari](#3-mimari) |
| 4 | [Analitik Pipeline](#4-analitik-pipeline) |
| 5 | [Domain Servisleri — Teknik Detaylar](#5-domain-servisleri--teknik-detaylar) |
| 6 | [Analiz Çıktıları ve Metrik Hiyerarşisi](#6-analiz-çıktıları-ve-metrik-hiyerarşisi) |
| 7 | [Kalite Güvencesi ve HITL](#7-kalite-güvencesi-ve-hitl) |
| 8 | [Altyapı ve Gözlemlenebilirlik](#8-altyapı-ve-gözlemlenebilirlik) |
| 9 | [Bilimsel Metodoloji ve Kaynaklar](#9-bilimsel-metodoloji-ve-kaynaklar) |

---

## 1. Hızlı Başlangıç Kılavuzu

> [!NOTE]
> Bu bölüm, sistemi sıfırdan kuracak ve analizleri tetikleyecek geliştiriciler / araştırmacılar için adım adım bir rehberdir.

### Gereksinimler
- **Python** $\geq$ 3.12
- **Poetry** $\geq$ 1.8
- *(Opsiyonel)* **Docker** (İzleme ve loglama için)

### Kurulum

```bash
# 1. Repoyu klonla
git clone https://github.com/BBgitaccount/BB-PAXDATA.git
cd BB-PAXDATA

# 2. Ortam değişkenlerini yapılandır (Bkz. .env.example)
cp .env.example .env

# 3. Bağımlılıkları kur ve sanal ortama geç
poetry install
poetry shell

# 4. Veritabanı tablolarını oluştur
alembic upgrade head
```

### İlk Analizi Çalıştırma

CLI üzerinden sistemle doğrudan etkileşime geçebilirsiniz:

```bash
# Ham transkripti veritabanına al
bbpaxdata build --transcript data/sample_transcript.json

# Cümle bazlı NLP/AI analizini tetikle
bbpaxdata analyze --transcript-id <id>

# Anomali ve risk denetimini HTML formatında raporla
bbpaxdata failcheck --report-format html
```

---

## 2. Sistem Genel Bakış

BB-PAXDATA, konferans tutanakları veya zirve konuşmaları gibi diplomatik metinleri alır; duygu (sentiment), risk, çit (hedge) dili ve çerçeveleme (framing) gibi birçok boyutta analiz eder. Bu süreç 5 temel katmanda gerçekleşir:

```mermaid
flowchart TB
    A([📄 Ham Transkript Girişi]) --> INGEST["📥 INGESTION LAYER\nMetin Normalleştirme & Konuşmacı Ayrıştırma\n(Idempotency: SHA-256)"]
    INGEST --> CORE["🧠 DOMAIN CORE\nNLP & Yapay Zeka Anotasyonu\n(Duygu, Risk, Hedge, Çerçeveleme)"]
    CORE --> INFRA["🏗️ INFRASTRUCTURE\nAI Backend'leri (Ollama/Claude)\n6-Seviyeli JSON Kurtarma (Recovery Engine)"]
    INFRA --> OBS["📊 OBSERVABILITY & HITL\nKalite Güvencesi, İnsan İncelemesi (HITL)\nPrometheus Metrikleri"]
    OBS --> INTERFACE["🖥️ INTERFACES\nTyper CLI & FastAPI REST\nRaporlama (JSON/HTML)"]
    
    style A fill:#475569,stroke:#94a3b8,color:#f8fafc
    style INGEST fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style CORE fill:#052e16,stroke:#34d399,color:#e2e8f0
    style INFRA fill:#2d1515,stroke:#f87171,color:#e2e8f0
    style OBS fill:#0f2746,stroke:#60a5fa,color:#e2e8f0
    style INTERFACE fill:#422006,stroke:#f97316,color:#e2e8f0
```

---

## 3. Mimari

Sistem bileşenlerinin ve tabloların ilişkisi aşağıdaki Entity-Relationship diyagramında gösterilmiştir.

```mermaid
erDiagram
    TRANSCRIPT {
        string id PK
        string title
        datetime created_at
    }
    SPEAKER {
        string id PK
        string name
        float power_level
    }
    SEGMENT {
        string id PK
        string transcript_id FK
        string speaker_id FK
    }
    SENTENCE {
        string id PK
        string segment_id FK
        string text
    }
    ANALYSIS {
        string id PK
        string sentence_id FK
        float sbi_score
        float dki_score
        float anomaly_score
        string risk_level
    }
    QUALITY_REPORT {
        string id PK
        string analysis_id FK
        float uncertainty_score
    }

    TRANSCRIPT ||--o{ SPEAKER : "has"
    TRANSCRIPT ||--o{ SEGMENT : "contains"
    SPEAKER ||--o{ SEGMENT : "speaks"
    SEGMENT ||--o{ SENTENCE : "contains"
    SENTENCE ||--|| ANALYSIS : "analyzed_as"
    ANALYSIS ||--o| QUALITY_REPORT : "evaluated_by"
```

---

## 4. Analitik Pipeline

Ham metin sisteme girdikten sonra ön işleme aşamasından geçer:

```mermaid
flowchart LR
    RAW["Ham Metin"] --> ENCODE["Encoding\n(ftfy)"]
    ENCODE --> TOKENIZE["Tokenization"]
    TOKENIZE --> LEMMA["Lemmatization\n(spaCy)"]
    LEMMA --> NER["NER\n(GPE/ORG)"]
    NER --> STOP["Stopword Filtresi\n(Negasyon Korumalı)"]
    STOP --> FEAT["Özellik Çıkarımı\n(TF-IDF, Embeddings)"]

    style RAW fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style FEAT fill:#052e16,stroke:#34d399,color:#e2e8f0
```

---

## 5. Domain Servisleri — Teknik Detaylar

> [!IMPORTANT]
> Bu bölümde sistemde kullanılan indekslerin formülleri açıklanmaktadır. Github'ın Markdown render sürecinde formüllerin bozulmaması için `\text{...}` bloklarında alt çizgiler (`_`) alt simge (subscript) olarak kodlanmıştır.

### 5.1 Duygu Analizi (`SentimentService`)

Sistem, diplomatik söylemler için özelleştirilmiş **DIPLO leksikonu** ile VADER'ı birleştirir.

Saf DIPLO skoru:
$$\text{diplo}_{\text{compound}} = \text{VADER}_{\text{compound}} + \left(\sum_{p \in \text{matched}_{\text{phrases}}} v_p\right) \times 0.05$$

**Negasyon-Farkında Skor** *(Jia & Liang, 2017)*:
$$\text{score}_{\text{neg-aware}} = \begin{cases}
-v_p \times 0.8 & \text{eğer } \exists \; n \in \text{NEGATION}_{\text{WORDS}} \; \text{window}[i-4:i] \\
v_p & \text{aksi hâlde}
\end{cases}$$

### 5.2 Risk Puanlama (`RiskService`)

İki adet bileşik indeks hesaplanır:

1. **SBI (Söylemsel Baskı İndeksi):** Güç düzeyi ve talep ağırlığına dayanır.
   $$\text{SBI} = \frac{P_{\text{level}} \times W_{\text{demand}}}{2} + R_{\text{score}}$$

2. **DKI (Diplomatik Konum İndeksi):** Nihai diplomatik duruş skoru. $[-1, 1]$
   $$\text{DKI} = \Big(d_{\text{norm}} \cdot 0.4 + (1 - r_{\text{norm}}) \cdot 0.3 + d_{\text{req}} \cdot 0.2 + (1 - m_{\text{norm}}) \cdot 0.1\Big) \times 2 - 1$$

### 5.3 Çapraz Anomali Tespiti (`CrossAnomalyService`)

Tsytsarau (2017) çelişki formülü baz alınarak **10 farklı kural seti** ile anomali skoru hesaplanır:
$$C = \frac{n \cdot M_2 - M_1^2}{\left(\vartheta \cdot n^2 + M_1^2\right) \cdot W}$$

---

## 6. Analiz Çıktıları ve Metrik Hiyerarşisi

Sistemdeki verilerin ham halden global endekslere nasıl dönüştüğünü gösteren metrik hiyerarşisi:

```mermaid
flowchart LR
    subgraph INPUT["1. Girdi Katmanı"]
        T["Metin Segmenti"]
        S["Konuşmacı Gücü (Power Level)"]
    end

    subgraph BASE["2. Temel Çıkarımlar"]
        VADER["VADER & DIPLO Sentiment"]
        HEDGE["Hedge Skoru (Hyland)"]
        NER["GPE/ORG Varlık Tespiti"]
        FRAME["Çerçeve (Entman)"]
    end

    subgraph COMPOUND["3. Bileşik İndeksler (Cümle)"]
        SBI["SBI\nSöylemsel Baskı"]
        DKI["DKI\nDiplomatik Konum"]
        ANOMALY["Anomali Skoru\n(10 Kural)"]
    end

    subgraph AGGREGATE["4. Global Metrikler (Makro)"]
        GCI["Global Çatışma İndeksi\n(GCI)"]
        DRIFT["Zamansal Drift Skoru\n(CUSUM/JSD)"]
        CRED["Aktör Güvenilirlik Puanı"]
    end

    T --> VADER & HEDGE & NER & FRAME
    S --> SBI
    VADER & NER --> SBI
    VADER & SBI & HEDGE & FRAME --> DKI
    VADER & SBI & HEDGE --> ANOMALY
    
    DKI & ANOMALY --> GCI
    VADER & FRAME --> DRIFT
    ANOMALY --> CRED

    style INPUT fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    style BASE fill:#0f2746,stroke:#60a5fa,color:#e2e8f0
    style COMPOUND fill:#052e16,stroke:#34d399,color:#e2e8f0
    style AGGREGATE fill:#422006,stroke:#f97316,color:#e2e8f0
```

---

## 7. Kalite Güvencesi ve HITL

Yapay zeka analizlerinin kalibrasyonu ve iyileştirilmesi için sisteme entegre, tam teşekküllü bir **Human-in-the-Loop (İnsanın Döngüye Katılımı)** mekanizması vardır.

### 7.1 HITL Yaşam Döngüsü

```mermaid
sequenceDiagram
    participant AI as AI Model
    participant SYSTEM as Anomaly & Uncertainty
    participant EXPERT as Alan Uzmanı
    participant CALIB as Calibration Service
    participant PROMPT as Few-Shot Injector

    AI->>SYSTEM: 1. İlk Analiz Çıktısı (Sentiment, Risk, Çerçeve)
    SYSTEM->>SYSTEM: 2. Entropi (U) Hesapla
    
    alt U > Threshold (Yüksek Belirsizlik)
        SYSTEM->>EXPERT: 3. Review Kuyruğuna Gönder
        EXPERT-->>SYSTEM: 4. Uzman Düzeltmesi (Immutable HumanReview)
    else U <= Threshold
        SYSTEM->>SYSTEM: Otomatik Onay
    end
    
    loop Haftalık
        SYSTEM->>CALIB: 5. Analiz Verilerini Besle
        CALIB->>CALIB: 6. Uyum Ölçümü (Kappa, F1, SBI MAE)
        
        alt Düşük Uyum (MAE > 10 veya F1 < 0.70)
            CALIB-->>PROMPT: 7. Alert: Prompt veya Ağırlık Güncelle
        else Yüksek Uyum
            CALIB->>PROMPT: 8. Golden Dataset'e Ekle
        end
    end
    
    PROMPT->>AI: 9. Yeni Analizlerde Few-Shot Olarak Enjekte Et
```

> [!TIP]
> **Belirsizlik (Uncertainty) Formülü:**
> $$U = H(p) = -\sum_{c} p_c \log_2 p_c$$
> AI modelinin kategori tahmin olasılıkları ($p_c$) arasındaki entropidir.

---

## 8. Altyapı ve Gözlemlenebilirlik

### 8.1 Fallback (Yedeklilik) ve JSON Kurtarma
Farklı AI backend'leri arasında (Ollama, Anthropic, Gemini, Groq) otomatik fallback (düşüş) sistemi vardır. LLM'in ürettiği bozuk JSON çıktıları için **6-Aşamalı Kurtarma Motoru (Recovery Engine)** devreye girer.

### 8.2 İzleme (Prometheus & Grafana)
Uygulama metrikleri (latency, önbellek vurma oranı, JSON kurtarma istatistikleri) düzenli olarak Prometheus üzerinden toplanır ve Grafana'da analiz edilir.

---

## 9. Bilimsel Metodoloji ve Kaynaklar

Sistem tamamen bilimsel temellere ve makalelere dayanmaktadır:

- **Sentiment:** Socher et al. (2013), Jia & Liang (2017) — Negasyon-farkında VADER + DIPLO Leksikonu.
- **Risk:** Baldwin (1985), Fearon (1995), Trager (2010) — Zorlayıcı Diplomasi ve Cheap Talk.
- **Hedging:** Hyland (1995, 2005) — Epistemik metadiscourse taksonomisi.
- **Framing:** Entman (1993) — Dört fonksiyonlu (Problem, Neden, Ahlak, Çözüm) çerçeveleme.
- **Anomaly:** Tsytsarau et al. (2017) — Duygu tabanlı çelişki tespiti.
- **Temporal Drift:** Page (1954), Lin (1991) — CUSUM tabanlı drift ve Jensen-Shannon Divergence.

<br/>

<div align="center">

![Footer](assets/footer.svg)

**[⬆ Başa Dön](#-i̇çindekiler)**

</div>
