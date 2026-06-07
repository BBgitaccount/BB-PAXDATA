# PaxData · Graphify — Geliştirme Görev Listesi

> **Kapsam:** Rapordan çıkarılan 12 görev + araştırmayla eklenen 7 ek görev = **19 görev** **Öneri sırası:** Her görev bağımsız yürütülebilir ama önerilen sıra bölüm sonunda verilmektedir. **Gösterim:** Zorluk `S / M / L / XL` (story-point mantığıyla); Öncelik `P1 / P2 / P3` (P1 = kritik yol üzeri)

---

## I. AKADEMİ KÖKENLİ EKLEMELER

---

### TASK-A01 · Semantic Role Labeling (SRL) Enrichment Layer

**Kategori:** Akademi → Mühendislik köprüsü | **Zorluk:** M | **Öncelik:** P1

#### Teorik Zemin

PropBank (Palmer et al. 2005) çerçevesinde predicate-argument yapıları. ARG0 = ajan (kim yapıyor), ARG1 = hasta (ne yapılıyor), ARGM-MOD = modalite (might/will/must), ARGM-NEG = olumsuzlama, ARGM-TMP = zamansal, ARGM-CAU = nedensel. spaCy `en_core_web_trf` modeli (`tok2vec` + `senter` + `parser` + `ner` + SRL) bu rolleri cümle düzeyinde çıkarır.

#### Sisteme Katkısı

Mevcut NER, entity'leri bulur ama *ne yaptıklarını* tespit edemez. SRL bu boşluğu kapatır:

- `"Turkey rejected the proposal"` → `ARG0: Turkey | predicate: rejected | ARG1: the proposal`
- `"Turkey supported the proposal"` → `ARG0: Turkey | predicate: supported | ARG1: the proposal` Her iki cümlede NER aynı entity'yi görür; SRL temelden farklı ajan rollerini yakalar.
  Downstream etki: Fischer DNA ağına **actor → action → target** üçlüsü (üçlü ilişki), `CrossAnomalyService` ARG-düzeyinde çalışır, `DiscourseNetworkEdge`'e `predicate` alanı girer.

#### Teknik Yaklaşım

```
spaCy en_core_web_trf
  └── AllenNLP SRL pipeline (allennlp-models==2.11)
       veya
      spacy-transformers + custom SRL head (daha entegre)
```

Her cümle için çıktı:

```python
@dataclass
class SRLFrame:
    verb: str
    arg0_span: Span | None      # ajan
    arg1_span: Span | None      # hasta
    argm_mod: str | None        # modalite
    argm_neg: bool              # olumsuzlama var mı
    argm_tmp: Span | None       # zamansal bağlam
    argm_cau: Span | None       # nedensel bağlam
```

#### Uygulama Adımları

1. `spacy_pipeline.py`'e `extract_semantic_roles(doc) → list[SRLFrame]` fonksiyonu ekle
2. `DiscourseNetworkEdge` modelini `predicate: str | None` ve `arg1_entity: str | None` alanlarıyla genişlet
3. `cross_anomaly_service.py`'deki `ContradictionResult`'ı ARG0/ARG1 eşleşmesiyle yeniden çalıştır
4. `assemble_network.py`'de yeni üçlü ilişki (actor, predicate, target) oluştur
5. Unit test: Gerçek transkript cümlesi için ARG0/ARG1 doğruluğu `≥ 85%`

#### Etkilenen Dosyalar

`spacy_pipeline.py`, `discourse_network.py`, `cross_anomaly_service.py`, `assemble_network.py`, `domain/models/srl_frame.py` (yeni)

#### Bağımlılıklar

Hiçbir upstream göreve bağlı değil. Bu görev diğer tüm A-serisi görevlere (A02, A03, A04, A05) ham veri sağlar.

#### Başarı Kriterleri

- PropBank F1 ≥ 0.82 (CoNLL-2012 üzerinde)
- Mevcut pipeline latency artışı `< 15%`
- `DiscourseNetworkEdge` kayıtlarının `≥ 70%`'inde predicate dolu

---

### TASK-A02 · Argument Mining — Claim-Premise-Attack İlişki Katmanı

**Kategori:** Akademi | **Zorluk:** L | **Öncelik:** P1

#### Teorik Zemin

Walton (2008) argumentation schemes: her argüman tipi için kritik sorular belirler (örn. *expert opinion scheme* → "Bu uzman gerçekten yetkili mi?"). Peldszus & Stede (2013) mikro-argüman yapısı: CLAIM, SUPPORT, ATTACK, REBUTTAL ilişkilerini segment düzeyinde modelleyen bağlantılı graf. IBM Debater'ın Argument Quality Corpus (AQC, ~5000 annotated argument) fine-tune kaynağı.

#### Sisteme Katkısı

Mevcut sistemde diplomatik söylem *ne söylendiği* düzeyinde analiz edilir; argüman yapısı çıkarılmaz. Bu görev her segment için şu ilişkileri kurar:

```
[CLAIM] Turkey's sovereignty claim
  ├── [SUPPORT] "backed by historical treaty references"
  └── [ATTACK]  "EU delegation's legal reinterpretation"
      └── [REBUTTAL] "Turkey's counter-reference to 1923 treaty"
```

Bu yapı şu an hiçbir pipeline katmanında yoktur.

#### Teknik Yaklaşım

```
Model: BERT-base fine-tuned on IBM AQC + PE (Persuasive Essays corpus)
Classifier: Segment-pair relation (SUPPORT / ATTACK / NEUTRAL / REBUTTAL)
Segmenter: EDU boundaries from RST parser (→ TASK-E03 sinerji)

Pipeline akışı:
  raw_text
    → segment_splitter (sentence / EDU)
    → claim_detector (binary: is this a claim?)
    → relation_classifier (for each claim-segment pair)
    → ArgumentGraph builder
```

Çıktı modeli:

```python
@dataclass
class ArgumentNode:
    segment_id: str
    text: str
    node_type: Literal["CLAIM", "SUPPORT", "ATTACK", "REBUTTAL"]
    speaker: str
    timestamp: float

@dataclass
class ArgumentGraph:
    nodes: list[ArgumentNode]
    edges: list[tuple[str, str, str]]  # (from_id, relation, to_id)
    root_claim_id: str
```

#### Uygulama Adımları

1. `domain/services/argument_structure_pipeline.py` oluştur (`FrameDetectionPipeline`'a paralel)
2. IBM AQC + PE corpus ile BERT fine-tune (ya da `deberta-v3-base` daha güçlü)
3. `ContradictionResult` (cross_anomaly_service.py) argüman düzeyinde yeniden yorumla — ATTACK ilişkisi bir contradiction sinyali olarak ele al
4. `AIAnalysisResult`'a `argument_graph: ArgumentGraph | None` alanı ekle
5. Frontend: Argüman ağacı görselleştirme (collapsible tree)
6. Evaluation: ArgumentAnnotatedEssays-2.0 üzerinde F1 ölçümü

#### Etkilenen Dosyalar

`domain/services/argument_structure_pipeline.py` (yeni), `cross_anomaly_service.py`, `domain/models/ai_analysis_result.py`, frontend argument viewer

#### Bağımlılıklar

→ TASK-A01 (SRL: ARG1 span'ları claim tespitini besler)

#### Başarı Kriterleri

- Claim detection F1 ≥ 0.78
- Relation classification F1 ≥ 0.70
- Her session analizinde ortalama ≥ 3 argüman yapısı çıkarılıyor

---

### TASK-A03 · Appraisal Theory Vektörü — Martin & White (2005)

**Kategori:** Akademi | **Zorluk:** M | **Öncelik:** P2

#### Teorik Zemin

Martin & White'ın (2005) Appraisal Theory, değerlendirme dilini üç eksende modelleyen sistemik-fonksiyonel bir çerçevedir:

- **AFFECT:** Duygusal tepki (happiness, security, satisfaction; pozitif/negatif, güç)
- **JUDGMENT:** Ahlaki değerlendirme → *social esteem* (normalite, kapasite, kararlılık) + *social sanction* (veracity, propriety)
- **APPRECIATION:** Estetik/değersel yargı (reaction, composition, value)

Her eksenin iki ek boyutu:

- **Graduation:** force (güçlendirme: "deeply, extremely") ve focus (keskinleştirme: "a true hero")
- **Engagement:** monogloss (tek sesli: "it is the case") vs heterogloss (çok sesli: "arguably, it seems")

#### Sisteme Katkısı

`HedgingService` epistemik belirsizliği, `SentimentService` polariteyi yakalar. Appraisal, bu ikisinin yakalayamadığı şeyi tespit eder:

| İfade                          | Mevcut Sentiment | Appraisal Karşılığı                 |
| ------------------------------ | ---------------- | ----------------------------------- |
| "deeply concerning"            | Negative         | AFFECT: insecurity, high force      |
| "violates international law"   | Negative         | JUDGMENT: impropriety, monogloss    |
| "an unprecedented achievement" | Positive         | APPRECIATION: valuation, high force |

"deeply concerning" ile "violates international law" aynı polarite skorunu alır ama appraisal açısından tamamen farklı türde değerlendirmelerdir. Bu ayrım `BilateralSentiment`'ın `asymmetry_score`'unu köklü biçimde zenginleştirir.

#### Teknik Yaklaşım

```python
@dataclass
class AppraisalVector:
    affect_score: float          # [-1, +1]
    affect_type: str | None      # happiness / security / satisfaction
    judgment_score: float        # [-1, +1]
    judgment_type: str | None    # esteem / sanction
    appreciation_score: float    # [-1, +1]
    graduation_force: float      # [0, 1] — güçlendirme
    engagement_type: Literal["monogloss", "heterogloss"]
```

İki yaklaşım:

1. **Lexicon-based:** SysFan corpus (150k token, appraisal annotated) + kural tabanlı graduation
2. **Fine-tuned classifier:** DeBERTa-v3 multi-label, üç eksen aynı anda → daha iyi

#### Uygulama Adımları

1. SysFan corpus / UWA Appraisal lexicon'u indir ve temizle
2. `domain/models/appraisal_vector.py` oluştur
3. `AppraisalService` → `domain/services/` altına (HedgingService mimarisini taklit et)
4. `PowerIndex`'e `AppraisalVector` alanı ekle
5. `BilateralSentiment.asymmetry_score` hesabını appraisal judgment boyutuyla ağırlıklandır
6. `HedgingService.HEDGING_LEXICON` ile overlap analizi yap; graduation leksikonunu paylaştır

#### Etkilenen Dosyalar

`domain/services/appraisal_service.py` (yeni), `domain/models/power_index.py`, `bilateral_sentiment.py`, `hedging_service.py`

#### Bağımlılıklar

→ TASK-A01 (SRL: ARGM-MOD graduation tespitine yardımcı)

#### Başarı Kriterleri

- F1 ≥ 0.72 üç eksen ayrı ayrı (SysFan evaluation set)
- `asymmetry_score` varyansının `≥ 20%` artması (mevcut baseline'a kıyasla)
- Graduation force ile HedgingService `confidence_level` korelasyonu `r > 0.6`

---

### TASK-A04 · Speech Act Classification + ILLOCUTIONARY_DRIFT

**Kategori:** Akademi | **Zorluk:** M | **Öncelik:** P1

#### Teorik Zemin

Austin (1962) / Searle (1969) speech act theory'nin diplomatik söyleme uyarlaması. Diplomatik speech act tipleri:

| Tip             | Açıklama                   | Örnekler                                     |
| --------------- | -------------------------- | -------------------------------------------- |
| **COMMISSIVE**  | Taahhüt / vaat             | "we will / we commit to / we pledge"         |
| **DIRECTIVE**   | Talep / emir               | "must / should / demands / calls upon"       |
| **EXPRESSIVE**  | Kınama / teşekkür / tebrik | "condemns / welcomes / expresses gratitude"  |
| **DECLARATIVE** | Resmi ilan / kararname     | "hereby declares / is officially recognized" |
| **ASSERTIVE**   | Olgusal iddia / inkâr      | "is a fact / has never / evidence shows"     |

#### Sisteme Katkısı

DKI pozisyon kaymasını *ne kadar* değiştiğiyle ölçüyor, *nasıl değiştiğini* yakalamıyor. Soft commitment → hard demand geçişi (COMMISSIVE → DIRECTIVE sürüklenmesi) stratejik açıdan kritik bir sinyaldir. Bu geçiş `ILLOCUTIONARY_DRIFT` olarak tanımlanır ve mevcut drift algoritmasına eklenir:

```python
DriftType = Literal[
    "SENTIMENT",
    "TOPIC",
    "LEXICAL",
    "TONE",
    "RISK",
    "ILLOCUTIONARY"   # ← YENİ
]
```

#### Teknik Yaklaşım

```
Model: Özel diplomatik fine-tune
  Base: roberta-base veya deberta-v3-small
  Dataset:
    - DiploSAC (Diplomatic Speech Act Corpus, varsa)
    - STAC corpus (strategic conversation)
    - Manuel annotation: mevcut transkriptlerden 500 örnek

Output:
  SpeechActClassification(
      primary_type: SpeechActType,
      secondary_type: SpeechActType | None,
      confidence: float,
      force_modifier: str | None  # "strongly / categorically / respectfully"
  )
```

ILLOCUTIONARY_DRIFT tespiti:

```python
# Zaman içinde ardışık speech act type değişimi
# COMMISSIVE (t-2) → COMMISSIVE (t-1) → DIRECTIVE (t) → drift=True
def detect_illocutionary_drift(history: list[SpeechActType]) → DriftEvent | None
```

#### Uygulama Adımları

1. `domain/services/speech_act_classifier.py` oluştur
2. `five_w_one_h_extractor.py` entegrasyonu: her segment için speech act etiketi
3. `DriftEvent` modeline `drift_type: DriftType` ekle (mevcut Literal genişletme)
4. `DriftAlgorithms`'a `ILLOCUTIONARY` drift tespiti ekle (sliding window, 3-5 ardışık segment)
5. `AIAnalysisResult`'a `speech_act_sequence: list[SpeechActClassification]` ekle
6. Frontend: Zaman çizgisinde speech act tipi renk kodlaması

#### Etkilenen Dosyalar

`domain/services/speech_act_classifier.py` (yeni), `five_w_one_h_extractor.py`, `domain/models/drift_event.py`, `drift_algorithms.py`, `domain/models/ai_analysis_result.py`

#### Bağımlılıklar

→ TASK-A01 (SRL: ARG0 ajan tespiti speech act'i kime atfettiğimizi güçlendirir)

#### Başarı Kriterleri

- F1 ≥ 0.80 (COMMISSIVE/DIRECTIVE/ASSERTIVE; EXPRESSIVE/DECLARATIVE daha nadir olduğundan ≥ 0.70 kabul)
- ILLOCUTIONARY_DRIFT, gerçek yoğunlaşma anlarını ≥ 2 oturumdan 1'inde tespit ediyor
- `five_w_one_h_extractor` çıktısıyla entegrasyon latency artışı < 8%

---

### TASK-A05 · Strategic Narrative Analysis — Miskimmon, O'Loughlin & Roselle (2013)

**Kategori:** Akademi | **Zorluk:** L | **Öncelik:** P2

#### Teorik Zemin

Miskimmon et al. (2013) üç narrative katmanı tanımlar:

- **System narratives:** Dünya düzeninin hikayesi ("rules-based international order", "multipolar world")
- **Identity narratives:** Kim biz, kim onlar ("defender of sovereignty", "aggressor state")
- **Issue narratives:** Bu krizin / olayın hikayesi ("humanitarian crisis", "proxy conflict")

Her aktörün narrative *salience*'ı (belirginliği) zaman içinde değişir ve rakip narratiflerle çarpışır.

#### Sisteme Katkısı

Mevcut `DiscourseNetworkEdge` yalnızca bipartite actor→concept. Narrative analizi ağa **yön** ve **hedef** ekler: Aktör A'nın identity narrative'i, aktör B'nin issue narrative'ine mi yanıt veriyor? Bu yapı statik bipartite grafı dinamik, hedefli bir anlatı ağına dönüştürür.

```python
@dataclass
class NarrativeLayer(str, Enum):
    SYSTEM = "system"
    IDENTITY = "identity"
    ISSUE = "issue"

# DiscourseFlow'a yeni alan:
narrative_layer: NarrativeLayer | None
narrative_target_actor: str | None  # kimin narratifine yanıt veriliyor
narrative_salience: float  # [0, 1]
```

#### Teknik Yaklaşım

```
Aşama 1: Narrative Layer Classifier
  - Multi-label classification (bir segment birden fazla katmana ait olabilir)
  - Base model: deberta-v3-base, zero-shot başlangıç
  - Fine-tune: Diplomatik transkriptlerden 300 etiketli örnek (HITL)

Aşama 2: Narrative Salience Tracking
  - Zaman serisi: Her aktör için, her katmanda ne kadar konuşma yapıyor?
  - Hesap: weighted frequency × frame alignment score

Aşama 3: Counter-narrative Detection
  - Aynı zaman penceresinde rakip aktörlerin aynı konuya farklı katmandan yaklaşması
  - Identity (biz) → Issue (olay) geçişi özellikle kritik
```

#### Uygulama Adımları

1. `frame_assembler.py`'e `NarrativeClassifierStage` ekle (mevcut frame pipeline'ına ek stage)
2. `DiscourseFlow` modeline üç yeni alan ekle
3. `build_panel_network.py`'de narrative node'ları ve yönlü kenarlar oluştur
4. `NarrativeSalienceTracker` service → zaman serisi hesabı
5. `CrossAnomalyService`'e counter-narrative tespit mantığı ekle
6. Frontend: Narrative katman filtresi + zaman serisi görselleştirme

#### Etkilenen Dosyalar

`frame_assembler.py`, `domain/models/discourse_flow.py`, `build_panel_network.py`, `domain/services/narrative_salience_tracker.py` (yeni), `cross_anomaly_service.py`

#### Bağımlılıklar

→ TASK-A01 (SRL), → TASK-A04 (Speech Act: EXPRESSIVE + ASSERTIVE tipleri narrative katman tespitini besler)

#### Başarı Kriterleri

- Narrative layer F1 ≥ 0.73 (3-class)
- Farklı aktörler arasında counter-narrative tespit recall ≥ 0.65
- `DiscourseFlow` kayıtlarının ≥ 60%'ında `narrative_layer` dolu

---

### TASK-A06 · Presupposition Mining — Gizli Taahhütlerin Çıkarımı

**Kategori:** Akademi | **Zorluk:** L | **Öncelik:** P2

#### Teorik Zemin

Lewis (1979) common ground: konuşmacıların paylaştığı örtük varsayımlar. Beaver & Geurts (2014) presupposition tetikleyicileri:

| Tetikleyici Tipi        | Sözcükler                      | Presupposition            |
| ----------------------- | ------------------------------ | ------------------------- |
| **Factive verbs**       | know, realize, notice, regret  | Embedded clause = gerçek  |
| **Implicative verbs**   | manage, fail, remember, forget | "fail" → attempt was made |
| **Temporal adverbs**    | still, again, already, anymore | Önceki durum varsayımı    |
| **Change of state**     | stop, start, continue, resume  | Önceki durum değişti      |
| **Definite NPs**        | "the ceasefire"                | Entity önceden var        |
| **Cleft constructions** | "It was Turkey that..."        | Others did not            |

Örnek: *"Turkey **still** supports the ceasefire"* → presupposition: Turkey previously supported it.
Örnek: *"NATO **failed** to respond"* → presupposition: NATO attempted to respond.

#### Sisteme Katkısı

`HedgingService`, epistemik belirsizliği açık ifadelerden çıkarır. Presuppositions ise gizli commitment'lardır — söylenmeden kabul edilenlerdir. Bunlar `PowerIndex` ve `BilateralSentiment`'ı etkilediği halde şu an hiçbir pipeline katmanında yakalanmaz.

```python
@dataclass
class Presupposition:
    trigger_word: str
    trigger_type: TriggerType  # FACTIVE / IMPLICATIVE / TEMPORAL / CHANGE_STATE / DEFINITE_NP
    presupposed_content: str   # "Turkey previously supported the ceasefire"
    confidence: float
    segment_id: str
    speaker: str
```

#### Teknik Yaklaşım

```
İki katmanlı yaklaşım:

Katman 1 — Kural Tabanlı (Yüksek Precision)
  - Regex + dependency parse üzerinde trigger detection
  - spaCy dependency labels: nsubj, xcomp, advcl
  - Tetikleyici liste: ~80 kelime/kalıp

Katman 2 — LLM Doğrulama (Precision artırma)
  - Kural tespitlerini LLM (Claude Sonnet) ile filtrele
  - Prompt: "Does this use of 'still' actually presuppose previous support?"
  - False positive oranını düşürür
```

#### Uygulama Adımları

1. `linguistic_helpers.py`'e `extract_presuppositions(doc) → list[Presupposition]` ekle
2. Trigger lexicon oluştur (80+ tetikleyici, 6 kategori)
3. spaCy dependency parse entegrasyonu (factive verb → xcomp clause çıkarımı)
4. LLM doğrulama katmanı (mevcut LLM infrastructure'ı kullan)
5. `AIAnalysisResult`'a `hidden_commitments: list[Presupposition]` ekle
6. `BilateralSentiment`'ın commitment tracking modülüne bağla
7. Evaluation: Manuel annotated sample (100 segment, 3 annotator, κ ≥ 0.7)

#### Etkilenen Dosyalar

`linguistic_helpers.py`, `domain/models/presupposition.py` (yeni), `domain/models/ai_analysis_result.py`, `bilateral_sentiment.py`

#### Bağımlılıklar

→ TASK-A01 (SRL: dependency parse zaten oradan geliyor, tekrarlı parse önlenir)

#### Başarı Kriterleri

- Precision ≥ 0.82 (kural katmanı + LLM doğrulama)
- Recall ≥ 0.65 (nadir tetikleyiciler kaçabilir, kabul edilebilir)
- Session başına ortalama ≥ 5 presupposition tespit edilmesi

---

### TASK-A07 · Bayesian Pozisyon Tahmini — Morrow (1994) Sinyal Teorisi

**Kategori:** Akademi | **Zorluk:** XL | **Öncelik:** P2

#### Teorik Zemin

Morrow (1994) diplomatik signaling teorisi: aktörler sinyal gönderir, gözlemciler bu sinyallere dayanarak karşı tarafın gerçek pozisyonu hakkındaki prior inançlarını günceller. Bu Bayesian Nash Equilibrium çerçevesiyle modellenebilir.

Mevcut `RiskForecaster` EWMA + CUSUM kullanır. Geçmiş değerlere üssel ağırlık verir ama bu ağırlığın teorik temeli yoktur; model, bilgi güncellemenin mantığını yansıtmaz.

Bayesian alternatif:

```
P(θ | signal, history) ∝ P(signal | θ) × P(θ | history)
  └── posterior          likelihood     prior

θ: aktörün gerçek pozisyonu (SBI θᵢ ile aynı ölçek)
signal: yeni konuşma / transkript
```

#### Sisteme Katkısı

- `SBICalculator.θᵢ` noktasal tahmin yerine olasılık dağılımı verir
- `ForecastResult`'a `credible_interval_95` eklenir (güven aralığı)
- Non-linear diplomatik davranış için Particle Filter desteği
- Kalman Filter doğrusal durum için özel hal olarak desteklenir

```python
@dataclass
class BayesianPositionTracker:
    speaker_id: str
    prior: Distribution          # Önceki konuşmalara göre P(θ)
    likelihood_model: Callable   # P(signal | θ)
    posterior: Distribution      # Güncellenmiş P(θ | signal)
    credible_interval_95: tuple[float, float]
    particle_count: int = 1000   # Particle Filter için

@dataclass  # ForecastResult güncellemesi
class ForecastResult:
    # ... mevcut alanlar ...
    credible_interval_95: tuple[float, float]  # YENİ
    posterior_mode: float                       # YENİ — en olası pozisyon
```

#### Teknik Yaklaşım

```
Aşama 1: Kalman Filter (Doğrusal Baseline)
  - State: θᵢ (pozisyon)
  - Observation: SBI skoru
  - Process noise: diplomatik oturum sıklığına göre
  - Measurement noise: UncertaintyScorer çıktısından

Aşama 2: Particle Filter (Non-linear, Önerilen)
  - N=1000 parçacık, her biri olası bir θ
  - Likelihood: P(SBI_obs | θ_particle) — Gaussian kernel
  - Resampling: systematic resampling (düşük varyans)
  - Avantaj: bimodal posteriors (ikili strateji) yakalanabilir

Aşama 3: Sinyal Sınıflandırması
  - Costly signal (commitment yüksek maliyet): DECLARATIVE + high force → güçlü likelihood güncelleme
  - Cheap talk: ASSERTIVE + low force → zayıf güncelleme
  - Speech act tipi × appraisal graduation → likelihood ağırlığı
```

#### Uygulama Adımları

1. `domain/services/bayesian_position_tracker.py` oluştur
2. `BayesianPositionTracker`, `position_tracker` protokolünü (DKIAssembler) implement et
3. Kalman Filter: `filterpy` kütüphanesi; Particle Filter: `particles` veya özel implementasyon
4. Sinyal ağırlıklandırma: Speech Act tipi × AppraisalVector × HedgingService → `signal_strength`
5. `DKIAssembler.attach_dki()` içinde `BayesianPositionTracker`'ı opsiyonel olarak devreye al (`use_bayesian: bool = False` flag)
6. `ForecastResult` modeline güven aralığı ekle
7. Backtest: Bilinen müzakere süreçleri (JCPOA, Minsk) üzerinde posterior accuracy

#### Etkilenen Dosyalar

`domain/services/bayesian_position_tracker.py` (yeni), `dki_assembler.py`, `forecasting.py`, `domain/models/forecast_result.py`

#### Bağımlılıklar

→ TASK-A04 (Speech Act: sinyal maliyeti tespiti), → TASK-A03 (Appraisal: graduation → sinyal gücü), → TASK-A01 (SRL: ARG0 ajan tespiti)

#### Başarı Kriterleri

- Kalman Filter'ın RMSE'si EWMA baseline'dan ≥ 10% düşük
- Credible interval kalibrasyonu: %95 aralığına gerçek değer düşme oranı ≥ 0.90
- Particle Filter bimodal durum tespiti: vaka analizi ile doğrulama

---

## II. MÜHENDİSLİK / ENDÜSTRİ KÖKENLİ EKLEMELER

---

### TASK-E01 · Contrastive Analysis Engine — Delta Mode

**Kategori:** Mühendislik | **Zorluk:** M | **Öncelik:** P1

#### Açıklama

Mevcut sistem her session'ı bağımsız analiz eder. *"İki session arasında ne değişti?"* sorusunu otomatik olarak cevaplayan bir mod yoktur. Bu görev tüm analiz çıktılarını karşılaştıran bir output layer'dır — yeni model gerektirmez, mevcut modellerin çıktılarını birbirine bağlar.

#### Sisteme Katkısı

```python
@dataclass
class AnalysisDelta:
    session_a_id: str
    session_b_id: str
    delta_sbi: dict[str, float]          # speaker → ΔSBI
    delta_dki: dict[str, float]          # speaker → ΔDKI
    delta_risk: float                    # ΔRisk score
    delta_hedging: dict[str, float]      # speaker → ΔHedging rate
    delta_speech_act: dict[str, dict]    # tip dağılımı değişimi
    delta_narrative: dict[str, dict]     # narrative layer ağırlıkları
    significant_changes: list[str]       # threshold aşan değişimler

@dataclass
class ContrastReport:
    delta: AnalysisDelta
    most_drifted_speaker: str
    most_drifted_dimension: str
    narrative_summary: str   # LLM-generated
    timestamp: datetime
```

#### Teknik Yaklaşım

- Her metrik için delta hesabı: `Δ = value_b - value_a`
- Normalized delta: `Δ_norm = Δ / (|value_a| + ε)` — baseline'a oranla
- Significance threshold: metrik başına kalibre (SBI için ±0.15, Risk için ±0.10)
- LLM özeti: değişimlerin doğal dil açıklaması

#### Uygulama Adımları

1. `application/use_cases/compare_sessions.py` oluştur
2. `AnalysisDelta` ve `ContrastReport` modelleri
3. Her metrik için delta hesaplama fonksiyonları
4. LLM narrative özeti (mevcut LLM infrastructure)
5. API endpoint: `POST /sessions/compare` (body: `{session_a, session_b}`)
6. Frontend: "Session A vs B" karşılaştırma paneli — tek tuş arayüz
7. Export: Karşılaştırma raporu PDF/Markdown çıktısı

#### Etkilenen Dosyalar

`application/use_cases/compare_sessions.py` (yeni), `domain/models/analysis_delta.py` (yeni), API layer, frontend

#### Bağımlılıklar

Tüm analiz görevlerinin çıktılarını kullanır ama hiçbirine sıkı bağlı değil. Bağımsız deploy edilebilir.

#### Başarı Kriterleri

- İki session arası delta hesabı < 2 saniye
- Significant change tespiti precision ≥ 0.85 (manuel doğrulama)
- LLM özetinin coherence skoru (LLM-as-judge ile) ≥ 4/5

---

### TASK-E02 · Graph Attention Network (GAT) — Fischer DNA Üzerinde

**Kategori:** Mühendislik | **Zorluk:** XL | **Öncelik:** P2

#### Açıklama

`DiscourseNetworkEdge` statik bipartite graf. GAT uygulaması: her actor-node için bağlı concept-node'larından gelen mesajları attention ağırlıklarıyla aggregation yapar. Sonuç: her aktör için **söylem embedding'i** — Wordfish θᵢ'nin network-aware versiyonu.

#### Teknik Yaklaşım

```
Framework: PyTorch Geometric
Layer: GATConv(in_channels, out_channels, heads=4, concat=True)

Graf yapısı:
  Node tipi 1: Actor nodes (speaker embeddings)
  Node tipi 2: Concept nodes (BERTopic topic embeddings)
  Kenar: actor → concept (edge_weight: co-occurrence frequency)

Eğitim sinyali:
  - HITL verdict "anomaly" → positive
  - HITL verdict "normal" → negative
  - Contrastive loss: anomalous pairs daha uzak, normal pairs daha yakın

Çıktı:
  GATEmbedding(actor_id, embedding: tensor[256], 
               characteristic_concepts: list[str],  # yüksek attention concepts
               anomaly_score: float)
```

`SBICalculator` güncelleme:

```python
# Mevcut weights: (0.6, 0.25, 0.15) — Wordfish, DKI, Fischer DNA
# Yeni weights:   (0.5, 0.2, 0.15, 0.15) — + GAT embedding
```

#### Uygulama Adımları

1. `domain/services/gat_embedding_service.py` oluştur
2. `build_panel_network.py` → `GATEmbeddingService` entegrasyonu
3. PyTorch Geometric `GATConv` ile model tanımla
4. HITL verdict'lerinden eğitim veri seti hazırla
5. Contrastive fine-tuning döngüsü (mevcut HITL pipeline'ına bağla)
6. `SBICalculator` ağırlık güncellemesi
7. Embedding visualization (t-SNE / UMAP) — frontend actor clustering görünümü

#### Etkilenen Dosyalar

`domain/services/gat_embedding_service.py` (yeni), `build_panel_network.py`, `sbi_calculator.py`

#### Bağımlılıklar

→ TASK-A01 (SRL: predicate-enriched edges daha zengin graf), → TASK-E06 (Cross-Document Event Coreference: event node'ları grafı zenginleştirir)

#### Başarı Kriterleri

- HITL doğrulama setinde anomali tespit F1 ≥ 0.78 (baseline vs GAT karşılaştırması)
- Attention weight top-5 concept: uzman değerlendirmesiyle ≥ 4/5 anlamlı
- Eğitim yakınsama < 50 epoch, GPU saati < 2h

---

### TASK-E03 · Dense Retrieval RAG v2 — ColBERT / DPR

**Kategori:** Mühendislik | **Zorluk:** M | **Öncelik:** P2

#### Açıklama

Mevcut `rag_service.py` muhtemelen TF-IDF veya SBERT cosine similarity kullanıyor. Late-interaction dense retrieval ile değiştirmek semantik recall'u %20-40 artırır.

#### Teknik Yaklaşım

```
ColBERT (Khattab & Zaharia 2020):
  - Her token için ayrı embedding (late interaction)
  - MaxSim ile matching: max_t∈q(max_t'∈d(q_t · d_t'))
  - TF-IDF'e üstünlüğü: "strategic ambiguity" → "calculated ambiguity" → "deliberate vagueness" semantik zincirini yakalar

Alternatif — DPR (Dense Passage Retrieval):
  - Bi-encoder: query ve passage ayrı encode
  - FAISS index için uyumlu
  - Daha hızlı inference, biraz düşük recall

Öneri: ColBERT (ragatouille kütüphanesi ile kolay entegrasyon)
```

Kullanım farkı:

- Eski: *"bu konuşmada Suriye'den ne zaman bahsedildi?"*
- Yeni: *"bu aktörün Suriye krizi hakkındaki pozisyon değişimini göster"* (semantik niyet)

#### Uygulama Adımları

1. `domain/ports/embedding_port.py`'deki `EmbeddingService` protokolü değiştirmeden yeni `ColBERTEmbeddingService` implementasyonu yaz
2. `ragatouille` kütüphanesi entegrasyonu (ColBERT wrapper)
3. `rag_context_assembler.py`'de yeni servis swap'ı (feature flag: `use_colbert: bool`)
4. Index build pipeline: mevcut corpus için ColBERT index (PLAID engine)
5. A/B test: 50 sorgu üzerinde TF-IDF vs ColBERT recall@10 karşılaştırması
6. Performans: FAISS GPU index veya CPU PLAID (< 200ms/query hedef)

#### Etkilenen Dosyalar

`domain/ports/embedding_port.py`, `rag_service.py`, `rag_context_assembler.py`, `domain/services/colbert_embedding_service.py` (yeni)

#### Bağımlılıklar

Bağımsız — protokol swap tamamen izole.

#### Başarı Kriterleri

- Recall@10: ColBERT ≥ TF-IDF + 20%
- Precision@5 düşmemeli (yeni yanlış pozitif eklememeli)
- Query latency < 200ms (PLAID index, CPU)

---

### TASK-E04 · Cross-Document Event Coreference

**Kategori:** Mühendislik | **Zorluk:** L | **Öncelik:** P2

#### Açıklama

Mevcut NER within-document. "The ceasefire" ifadesi 5 farklı transkriptte geçiyor ama sistem bunların aynı event'i referans ettiğini bilmiyor. Event coreference bu cross-document bağlantıyı kurar.

#### Teknik Yaklaşım

```
Aşama 1: Event Mention Detection
  - spaCy NER + SRL ARG1 spans → event candidates
  - Event trigger words: verbs (agree, reject, announce) + nominals (ceasefire, vote, summit)

Aşama 2: Coreference Resolution (iki katmanlı)
  Katman 1 — Heuristic (hızlı):
    - Temporal overlap: ±7 gün
    - Entity overlap: aynı ülke/kurum
    - String similarity: "the ceasefire" / "this ceasefire" / "the agreed ceasefire"

  Katman 2 — LLM Verification (kalite güvencesi):
    - "Do these two event descriptions refer to the same event?" (evet/hayır + confidence)
    - Sadece threshold yakını çiftler için çağrılır (maliyet kontrolü)

@dataclass
class CanonicalEvent:
    event_id: str
    canonical_description: str
    first_mention: datetime
    mention_count: int
    participating_actors: list[str]
    related_sessions: list[str]

# DiscourseFlow güncellemesi:
referenced_events: list[CanonicalEvent] = field(default_factory=list)
```

#### Uygulama Adımları

1. `domain/services/event_coreference_service.py` oluştur
2. `NERService`'e `resolve_cross_document_events(sessions) → EventCoreferenceMap` ekle
3. Heuristic coreference → LLM verification pipeline
4. `CanonicalEvent` store (event registry — Redis veya DB tablo)
5. `assemble_network.py`'de event node'ları Fischer DNA grafına ekle
6. `DiscourseFlow` modeli güncelle
7. Event timeline görselleştirme (frontend)

#### Etkilenen Dosyalar

`domain/services/event_coreference_service.py` (yeni), `ner_service.py`, `assemble_network.py`, `domain/models/discourse_flow.py`, `domain/models/canonical_event.py` (yeni)

#### Bağımlılıklar

→ TASK-A01 (SRL: ARG1 event mention detection'ı güçlendirir)

#### Başarı Kriterleri

- ECB+ corpus üzerinde CoNLL F1 ≥ 0.72
- LLM verification false positive oranı < 0.10
- Cross-session event bağlantısı: 10 oturumlu vaka analizinde ≥ 15 event cluster

---

### TASK-E05 · Consensus/Divergence Tracker — Çok Taraflı Pozisyon Matrisi

**Kategori:** Mühendislik | **Zorluk:** M | **Öncelik:** P1

#### Açıklama

Çok taraflı panellerde analistlerin en sık sorduğu soru: *"Hangi taraflar yaklaşıyor, hangileri uzaklaşıyor?"* `SpeakerPosition.theta` zaman serisini pairwise distance matrix'e dönüştürür ve convergence/divergence tespiti yapar.

#### Teknik Yaklaşım

```python
# Pairwise mesafe matrisi
distances: dict[tuple[str,str], float] = {
    (speaker_a, speaker_b): |theta_a(t) - theta_b(t)|
    for all pairs at time t
}

# Convergence/Divergence tespiti
delta_d = d(t) - d(t-1)  # negatif → convergence, pozitif → divergence

# Clustering (dönemsel koalisyon tespiti)
# DBSCAN(eps=0.15, min_samples=2) veya hierarchical clustering

@dataclass
class ConsensusMoment:
    speakers: list[str]
    topic: str | None
    panel_range: tuple[datetime, datetime]
    convergence_type: Literal["convergence", "divergence", "stable"]
    confidence: float
    theta_spread: float  # max(theta) - min(theta)

@dataclass
class CoalitionCluster:
    cluster_id: str
    members: list[str]
    centroid_theta: float
    stability: float  # kaç oturumda aynı kaldı
    time_range: tuple[datetime, datetime]
```

#### Uygulama Adımları

1. `aggregate_bilateral_sentiment.py` use case'ini genişlet
2. Pairwise distance matrix hesaplama (scipy.spatial.distance)
3. DBSCAN clustering (sklearn)
4. `ConsensusMoment` ve `CoalitionCluster` modelleri
5. Zaman serisi delta hesabı → convergence/divergence classification
6. Frontend: Heatmap görselleştirme (pairwise mesafe matrisi) + koalisyon grupları

#### Etkilenen Dosyalar

`application/use_cases/aggregate_bilateral_sentiment.py`, `domain/services/consensus_tracker.py` (yeni), `domain/models/consensus_moment.py` (yeni), frontend

#### Bağımlılıklar

→ TASK-A07 (Bayesian Tracker: credible interval → convergence tespitinde güven kontrolü)

#### Başarı Kriterleri

- Bilinen yakınsama momentlerini ≥ 75% doğrulukla tespit
- Koalisyon tespiti: uzman değerlendirmesiyle ≥ 80% anlamlı
- Gerçek zamanlı güncelleme: her yeni session'dan sonra < 5 saniye

---

### TASK-E06 · Cross-Document Event Coreference

*[TASK-E04 ile örtüşen bölüm yukarıda — bu slot TASK-E06 için ayrıldı: Event Timeline Visualization]*

---

## III. ARAŞTIRMAYLA EKLENİLEN GÖREVLER

---

### TASK-X01 · Target-Stance Detection — Diplomatik Hedef Tutumu

**Kategori:** Ek (Akademi) | **Zorluk:** M | **Öncelik:** P1

#### Neden Eklendi

2024-2025 NLP literatürü (Chain of Stance, MPRF Framework, Cambridge Political Analysis 2025) stance detection'ı sentiment'tan net biçimde ayırıyor. Diplomatik söylemde analistlerin "tutum analizi"nde asıl ihtiyaçları budur: **X aktörü, Y konusunda ne düşünüyor?** — pozitif/negatif değil, FAVOR/AGAINST/NEUTRAL/UNRELATED.

#### Mevcut Fark

- `SentimentService`: polarite (pozitif/negatif/nötr) — duygusal ton
- `HedgingService`: epistemik belirsizlik — emin mi değil mi
- Stance Detection: belirli bir konuya/aktöre/politikaya yönelik tutum — bunların ikisinden de farklı

Örnek: *"We acknowledge the proposal"* → Sentiment: **nötr**, Stance: **AGAINST** (resmi dili diplomatik ret).

#### Teknik Yaklaşım

```
Model: DeBERTa-v3-base fine-tuned on:
  - SemEval 2016 Task 6 (stance detection)
  - VaxxStance, P-Stance (domain transfer)
  - Diplomatik fine-tune: mevcut HITL annotated data

Input: (text, target_entity/topic) pair
Output: StanceLabel {FAVOR, AGAINST, NEUTRAL, UNRELATED} + confidence

Hedef listesi: Mevcut BERTopic topic'lerinden + Fischer DNA concept'lerinden otomatik oluşturulur

@dataclass
class StanceResult:
    speaker: str
    target: str         # entity veya topic
    stance: StanceLabel
    confidence: float
    evidence_spans: list[str]
```

#### Uygulama Adımları

1. `domain/services/stance_detection_service.py` oluştur
2. SemEval + diplomatic fine-tune (HITL data)
3. Hedef listesi: BERTopic topics × Fischer DNA concepts × named entities
4. `AIAnalysisResult`'a `stance_matrix: dict[str, dict[str, StanceResult]]` ekle
5. `DKI` pozisyon hesabında stance confidence ile ağırlıklandırma (opsiyonel)
6. Frontend: Aktör × Konu stance ısı haritası

#### Etkilenen Dosyalar

`domain/services/stance_detection_service.py` (yeni), `domain/models/ai_analysis_result.py`, `dki_assembler.py` (opsiyonel entegrasyon)

#### Başarı Kriterleri

- F1 macro ≥ 0.75 (SemEval eval set)
- Diplomatik test seti: uzman anotasyonuyla ≥ 0.78 agreement (κ)
- AGAINST tespitinde özellikle recall ≥ 0.72 (diplomatik dilde ret sinyal gizlenir)

---

### TASK-X02 · RST Söylem Ayrıştırma — Retorik Yapı Teorisi

**Kategori:** Ek (Akademi) | **Zorluk:** L | **Öncelik:** P2

#### Neden Eklendi

2024 ACL SIGDIAL'de yayınlanan *"Rhetorical Structure Theory and Conflicts"* çalışması RST'yi doğrudan diplomatik çatışma ortamlarına uyguluyor. Aynı yıl *"RST discourse parsing guided by document-level content structures"* (ACL 2024) ve LLM tabanlı RST parsing performansının insan seviyesine yaklaştığı gösterildi. Argument Mining (TASK-A02) için makro-düzey söylem iskeleti sağlar.

#### Teorik Zemin

Mann & Thompson (1988) RST: metni hiyerarşik bir ağaç olarak modelleyen söylem teorisi. Elementary Discourse Unit (EDU) yaprak noktalardır; iç node'lar retorik ilişkileri (ELABORATION, CONTRAST, CONCESSION, CAUSE, CONDITION, EVIDENCE, ANTITHESIS) temsil eder. Nucleus = ana kısım, Satellite = yardımcı kısım.

#### Sisteme Katkısı

```
CONCESSION ilişkisi → "We acknowledge your concerns, however..."
  → CrossAnomalyService için yumuşatılmış contradiction sinyali

CAUSE ilişkisi → "Because of the violation, we must respond"
  → Causal chain (TASK-X03) için veri

ANTITHESIS ilişkisi → "Not X, but Y"
  → Argument Mining'de ATTACK ilişkisi için güçlü sinyal

EVIDENCE ilişkisi → "The treaty states... therefore our position is..."
  → Presupposition Mining için factive context
```

#### Teknik Yaklaşım

```
Model: NeuralRST (Nguyen et al. 2021) veya LLM-tabanlı (EACL 2024 çalışması)
  - NeuralRST: hız odaklı, düşük latency
  - LLM (Sonnet): kalite odaklı, yüksek latency — batch mode önerisi

Output:
@dataclass
class RSTTree:
    root: RSTNode

@dataclass
class RSTNode:
    span: tuple[int, int]     # EDU indeks aralığı
    relation: RSTRelation     # ELABORATION, CONTRAST, etc.
    nuclearity: Literal["N", "S", "NN"]
    left: RSTNode | None
    right: RSTNode | None
    edu_text: str | None      # Sadece yaprak node'larda
```

#### Uygulama Adımları

1. `domain/services/rst_parser_service.py` oluştur
2. NeuralRST model entegrasyonu (model hub'dan indir)
3. EDU boundary'leri mevcut segment yapısıyla hizala
4. RST ilişkilerini TASK-A02 argüman madenciliğine bridge et (CONCESSION → ATTACK, EVIDENCE → SUPPORT)
5. RST ilişkilerini TASK-X03 nedensel zincire bridge et (CAUSE → causal edge)
6. `AIAnalysisResult`'a `rst_tree: RSTTree | None` ekle
7. Frontend: Collapsible RST tree görselleştirme

#### Etkilenen Dosyalar

`domain/services/rst_parser_service.py` (yeni), `domain/models/ai_analysis_result.py`, `argument_structure_pipeline.py`, causal service entegrasyonu

#### Bağımlılıklar

→ TASK-A02 (Argument Mining: RST ilişkilerini besler), → TASK-X03 (Causal Mining: CAUSE ilişkisi)

#### Başarı Kriterleri

- RST-DT'de labeled F1 ≥ 0.72 (EACL 2024 baseline'ı geçmek)
- CONCESSION → ATTACK bridge precision ≥ 0.80
- Session başına ortalama RST tree derinliği ≥ 4 seviye

---

### TASK-X03 · Causal Chain Mining — Nedensel Zincir Çıkarımı

**Kategori:** Ek (Akademi) | **Zorluk:** M | **Öncelik:** P2

#### Neden Eklendi

Diplomatik söylemin temel mantıksal yapısı nedenseldir: "X olduğu için Y yapıyoruz", "A'nın B'ye yol açması nedeniyle C'yi talep ediyoruz". Bu nedensel zincirleri çıkarmak hem argüman yapısını güçlendirir hem de Fischer DNA ağına yeni bir kenar tipi ekler.

#### Teorik Zemin

Causal News Corpus (CASE 2022/2023): protest event haberlerinden CAUSE / EFFECT / SIGNAL span annotation. CausalTimeBank: TimeML uyumlu zamansal-nedensel ilişkiler. Discourse-level causality, propagandanın da temel taşıdır (bkz. TASK-X04).

#### Teknik Yaklaşım

```python
@dataclass
class CausalRelation:
    cause_span: str
    effect_span: str
    signal_word: str | None    # "because", "therefore", "as a result"
    cause_actor: str | None    # SRL ARG0'dan
    effect_actor: str | None
    confidence: float
    source_rst_relation: RSTRelation | None  # RST CAUSE ilişkisinden geliyorsa

# DiscourseNetworkEdge güncellemesi:
causal_edges: list[CausalRelation] = field(default_factory=list)
```

İki kaynak:

1. RST CAUSE ilişkileri (TASK-X02'den direkt)
2. Surface-level causal markers: "because / therefore / consequently / as a result / due to / which led to"

#### Uygulama Adımları

1. `domain/services/causal_mining_service.py` oluştur
2. RST bridge: TASK-X02 CAUSE ilişkilerini causal relation'a dönüştür
3. Surface marker extraction (regex + dependency parse)
4. SRL entegrasyonu: cause/effect actor tespiti
5. `DiscourseNetworkEdge`'e `causal_edges` ekle
6. Fischer DNA ağında causal edge tipi görselleştirme

#### Etkilenen Dosyalar

`domain/services/causal_mining_service.py` (yeni), `discourse_network.py`, `build_panel_network.py`

#### Bağımlılıklar

→ TASK-A01 (SRL: actor tespiti), → TASK-X02 (RST: CAUSE ilişkileri)

#### Başarı Kriterleri

- Causal News Corpus F1 ≥ 0.70
- Session başına ortalama ≥ 3 causal chain
- Graf görselleştirmede causal path uzunluğu ≥ 2 hop

---

### TASK-X04 · Propaganda Teknik Tespiti

**Kategori:** Ek (Akademi) | **Zorluk:** M | **Öncelik:** P2

#### Neden Eklendi

SemEval 2020 Task 11 ile kurumsallaşan propaganda teknik tespiti, diplomatik söylemdeki manipülatif retorik kalıpları otomatik olarak etiketler. Discourse-level propaganda (causal ve contrast ilişkileri üzerinden), CrossAnomalyService'in mevcut contradiction tespitini kritik bir boyutla tamamlar.

#### 14 Temel Propagand Tekniği (SemEval 2020)

| Teknik                     | Diplomatik Bağlam Örneği                       |
| -------------------------- | ---------------------------------------------- |
| Appeal to Authority        | "As the UN Charter clearly states..."          |
| Loaded Language            | "brutal aggression" / "freedom fighters"       |
| Name Calling               | "rogue state" / "terrorist regime"             |
| Repetition                 | Aynı talebin her paragrafta yinelenmesi        |
| Exaggeration/Minimization  | "unprecedented catastrophe" / "minor incident" |
| Whataboutism               | "But what about X's actions in Y?"             |
| Bandwagon                  | "The entire international community agrees..." |
| Appeal to Fear             | "If this continues, the region will collapse"  |
| Black-and-White Fallacy    | "Either you support us or you support them"    |
| Doubt Casting              | "There are serious questions about..."         |
| Flag Waving                | "Our nation's honor demands..."                |
| Thought-terminating Cliché | "This speaks for itself"                       |
| Reductio ad Hitlerum       | Extreme historical analogy                     |
| Straw Man                  | Rakip pozisyonun çarpıtılarak atfedilmesi      |

#### Teknik Yaklaşım

```
LLM-tabanlı (önerilen 2025 yaklaşımı):
  - GPT-4 / Claude Sonnet ile zero/few-shot sınıflandırma
  - SemEval 2020 verisinden few-shot örnekler
  - Multi-label: birden fazla teknik aynı anda

veya

Fine-tuned BERT (SemEval 2020 Task 11 baseline):
  - Span-level detection (hangi kelimeler/cümleler teknik taşıyor)
  - Daha explainable

@dataclass
class PropagandaDetection:
    technique: PropagandaTechnique
    span: str
    confidence: float
    speaker: str
    segment_id: str
```

#### Uygulama Adımları

1. `domain/services/propaganda_detection_service.py` oluştur
2. LLM-based few-shot classifier (SemEval örnekleriyle prompt)
3. `CrossAnomalyService`'e propaganda sinyali olarak entegre et
4. `PowerIndex`'e `propaganda_intensity: float` alanı ekle
5. Risk scoring: yüksek propaganda yoğunluğu → `RiskForecaster`'a sinyal
6. Frontend: Propaganda teknik etiketleri highlight görünümü

#### Etkilenen Dosyalar

`domain/services/propaganda_detection_service.py` (yeni), `cross_anomaly_service.py`, `domain/models/power_index.py`, `forecasting.py`

#### Bağımlılıklar

→ TASK-X02 (RST: CONTRAST ve CAUSE ilişkileri propaganda tespitini güçlendirir), → TASK-A03 (Appraisal: loaded language → JUDGMENT: sanction)

#### Başarı Kriterleri

- SemEval 2020 eval set F1 ≥ 0.65 (zorlu task, 14 class)
- Diplomatik test set: uzman değerlendirmesiyle ≥ 0.70 agreement
- Loaded language ve Whataboutism: en sık görülen iki teknik olarak önceliklendir (recall ≥ 0.78)

---

### TASK-X05 · Active Learning Döngüsü — HITL Akıllı Kuyruğu

**Kategori:** Ek (Mühendislik) | **Zorluk:** M | **Öncelik:** P1

#### Neden Eklendi

Mevcut HITL pipeline ve `UncertaintyScorer` ayrı çalışıyor. Anotasyon kuyruğu rastgele veya FIFO sıralanıyordur. Active learning ile `UncertaintyScorer`'ın yüksek belirsizlik çıkardığı örnekler sistematik olarak önce anotasyona gönderilirse, aynı annotation bütçesiyle modeller çok daha hızlı iyileşir.

#### Teknik Yaklaşım

```
Sorgulama stratejisi seçenekleri:
  1. Uncertainty Sampling: max entropy veya min confidence
     score = 1 - max(P(class_i))

  2. Query-by-Committee: birden fazla model aynı örneği tahmin eder, anlaşmazlık → anotasyona
     disagreement = 1 - agreement(model_1, model_2, ..., model_k)

  3. Core-set (Sener & Savarese 2018): embedding space'de en az kapsanan bölgeler
     → yeni, alışılmamış diplomatik konuşma tipleri önce anotasyona gider

Önerilen: Uncertainty Sampling başlangıç; Core-set ilerleyen fazda.

@dataclass
class AnnotationQueueItem:
    session_id: str
    segment_id: str
    uncertainty_score: float    # UncertaintyScorer'dan
    model_disagreement: float   # (varsa) query-by-committee
    priority_rank: int
    annotation_type: str        # "stance", "argument", "narrative" etc.

Otomatik Fine-tuning Tetikleyici:
  - Her N yeni anotasyon sonrası model fine-tune (N = 50, ayarlanabilir)
  - Validation set F1 izleme → regresyon varsa rollback
  - MLflow / W&B ile experiment tracking
```

#### Uygulama Adımları

1. `application/use_cases/active_learning_queue.py` oluştur
2. `UncertaintyScorer` → `AnnotationQueueItem` dönüşümü
3. Öncelik skorlama fonksiyonu (uncertainty + diversity kombinasyonu)
4. HITL arayüzüne "priority queue" görünümü ekle
5. Fine-tuning tetikleyici (her 50 anotasyon → eğitim pipeline)
6. Model performans izleme dashboard'u
7. A/B test: random sampling vs active learning — annotation efficiency karşılaştırması

#### Etkilenen Dosyalar

`application/use_cases/active_learning_queue.py` (yeni), `uncertainty_scorer.py`, HITL frontend, `domain/services/fine_tuning_scheduler.py` (yeni)

#### Bağımlılıklar

→ Tüm classifier görevler (A02, A03, A04, X01, X04): bunların uncertainty output'larını besler

#### Başarı Kriterleri

- 100 anotasyon ile active learning, 200 random anotasyonla eşit veya daha iyi F1
- Fine-tuning sonrası ortalama ≥ 3% F1 artışı
- Anotasyon kuyruğu öncelik hesabı < 100ms

---

### TASK-X06 · Temporal Relation Extraction — Diplomatik Olay Zaman Sıralaması

**Kategori:** Ek (Akademi) | **Zorluk:** M | **Öncelik:** P3

#### Neden Eklendi

Event coreference (TASK-E04) olayları kümeler ama olayların birbirine göre zamansal sırasını modellemiyor. "Turkey agreed *before* the summit" ile "Turkey agreed *after* pressure" temelden farklı yorumlara yol açar. TimeML standardı bu boşluğu diplomatik analiz için dolduruyor.

#### Teknik Yaklaşım

```
Standart: TimeML (Pustejovsky et al. 2003) — TIMEX3, EVENT, TLINK

Allen Interval Algebra ilişkileri (13 temel):
  BEFORE, AFTER, MEETS, OVERLAPS, DURING, STARTS, FINISHES, EQUALS + inverseleri

Uygulama:
  Model: BERT-base fine-tuned on TempEval-3 corpus

  Output:
  @dataclass
  class TemporalRelation:
      event_a: CanonicalEvent        # TASK-E04'ten
      event_b: CanonicalEvent
      relation: AllenRelation        # BEFORE / AFTER / OVERLAPS etc.
      confidence: float

  # CanonicalEvent güncellemesi:
  temporal_predecessors: list[TemporalRelation]
  temporal_successors: list[TemporalRelation]
```

#### Uygulama Adımları

1. `domain/services/temporal_relation_service.py` oluştur
2. TempEval-3 fine-tune (TimeBank + AQUAINT)
3. `CanonicalEvent` modeline temporal relation alanları ekle
4. Event timeline görselleştirme (Gantt chart tarzı)
5. `DKI` hesabında zaman sıralaması ağırlığı (sonraki olay daha güncel pozisyon)

#### Etkilenen Dosyalar

`domain/services/temporal_relation_service.py` (yeni), `domain/models/canonical_event.py`

#### Bağımlılıklar

→ TASK-E04 (Cross-Document Event Coreference: CanonicalEvent'ler üzerinde çalışır)

#### Başarı Kriterleri

- TempEval-3 F1 ≥ 0.68 (BEFORE/AFTER)
- Event timeline görselleştirme kullanıcı testinde ≥ 4/5 anlamlılık skoru

---

### TASK-X07 · Probability Calibration — Güven Aralığı Kalibrasyonu

**Kategori:** Ek (Mühendislik) | **Zorluk:** S | **Öncelik:** P2

#### Neden Eklendi

Sistemdeki tüm classifier'lar ve `UncertaintyScorer` 0-1 arasında confidence değerleri çıkarır. Bu değerlerin *kalibre* olup olmadığı — yani "%80 confidence" diyorsa gerçekten %80 doğru mu? — test edilmemiştir. Bayesian pozisyon tahmini (TASK-A07) ve Active Learning (TASK-X05) kalibre olmayan probabilities ile yanıltıcı sonuçlar üretir.

#### Teknik Yaklaşım

```
Kalibrasyon yöntemleri:
  1. Temperature Scaling: softmax logitlerini T skalarıyla böl, T validation set'te optimize edilir
     → Single parameter, fast, works well for overconfident models

  2. Platt Scaling: logistic regression ile post-hoc kalibrasyon
     → İki parametre, biraz daha esnek

  3. Isotonic Regression: non-parametric, daha fazla veri gerektirir

Ölçüm:
  ECE (Expected Calibration Error): M bucket, her buckette |accuracy - confidence| ağırlıklı ortalama
  MCE (Maximum Calibration Error): en kötü bucket
  Reliability diagram: görsel kalibrasyon kontrolü

@dataclass
class CalibrationResult:
    model_name: str
    ece_before: float
    ece_after: float
    method: Literal["temperature_scaling", "platt", "isotonic"]
    temperature: float | None

# Her classifier'a wrapper:
class CalibratedClassifier:
    def __init__(self, base_classifier, calibrator):
    def predict_proba(self, x) → list[float]:  # kalibre edilmiş
```

#### Uygulama Adımları

1. `domain/services/calibration_service.py` oluştur
2. Tüm classifier output'larının ECE ölçümü (baseline)
3. Temperature scaling uygula (en basit ve genellikle yeterli)
4. `UncertaintyScorer`'ı kalibre edilmiş probability kullanacak şekilde güncelle
5. Reliability diagram monitoring (Grafana/dashboard)
6. Yeni modeller için kalibrasyon zorunluluğu → CI/CD kontrolü

#### Etkilenen Dosyalar

`domain/services/calibration_service.py` (yeni), `uncertainty_scorer.py`, tüm classifier servisler

#### Bağımlılıklar

→ TASK-A07 (Bayesian Tracker: kalibre probability → doğru likelihood), → TASK-X05 (Active Learning: kalibre uncertainty → doğru önceliklendirme)

#### Başarı Kriterleri

- ECE ≤ 0.05 (kalibrasyon sonrası tüm classifierlar için)
- Reliability diagram eğrisi 45° çizgisinden ≤ 0.08 sapma
- `UncertaintyScorer` güven aralıklarının %95'i gerçek değeri kapsıyor

---

## IV. UYGULAMA SIRASI ve BAĞIMLILIK GRAFİĞİ

```
Faz 1 — Temel Altyapı (P1 görevler, ~6-8 hafta)
────────────────────────────────────────────────
[TASK-A01] SRL Enrichment Layer           ← Tüm A-serisi görevlere ham veri
[TASK-E01] Contrastive Analysis Engine    ← Bağımsız, hızlı etki
[TASK-A04] Speech Act Classification      ← DKI ve Drift'e direkt bağlı
[TASK-E05] Consensus/Divergence Tracker   ← Mevcut SBI üzerinde hızlı kazanım
[TASK-X01] Target-Stance Detection        ← Sentiment'ın eksik boyutu
[TASK-X05] Active Learning Queue          ← Diğer modellerin eğitimini hızlandırır
[TASK-X07] Probability Calibration        ← Kısa süre, yüksek etki (S zorluk)

Faz 2 — Analitik Derinlik (P2 görevler, ~10-12 hafta)
──────────────────────────────────────────────────────
[TASK-A02] Argument Mining                ← A01 gerekli
[TASK-A03] Appraisal Theory               ← A01 gerekli
[TASK-A05] Strategic Narrative            ← A01, A04 gerekli
[TASK-A06] Presupposition Mining          ← A01 gerekli
[TASK-E03] Dense Retrieval RAG v2         ← Bağımsız swap
[TASK-E04] Cross-Document Event Coref     ← A01 gerekli
[TASK-X02] RST Discourse Parsing          ← X03'e zemin
[TASK-X03] Causal Chain Mining            ← A01, X02 gerekli
[TASK-X04] Propaganda Detection           ← X02 faydalı

Faz 3 — İleri Model (P2-P3 görevler, ~8-10 hafta)
───────────────────────────────────────────────────
[TASK-A07] Bayesian Position Tracker      ← A03, A04 gerekli
[TASK-E02] GAT Fischer DNA                ← E04, A01 gerekli
[TASK-X06] Temporal Relation Extraction   ← E04 gerekli
```

### Bağımlılık Özeti

```
TASK-A01 (SRL)
  ├──→ A02 (Argument Mining)
  ├──→ A03 (Appraisal)
  ├──→ A04 (Speech Act)
  ├──→ A05 (Narrative)
  ├──→ A06 (Presupposition)
  ├──→ E04 (Event Coref)
  ├──→ X03 (Causal Mining)
  └──→ X07 (Calibration — dolaylı)

TASK-A04 (Speech Act)
  └──→ A07 (Bayesian Tracker)

TASK-A03 (Appraisal)
  └──→ A07 (Bayesian Tracker)

TASK-E04 (Event Coref)
  ├──→ E02 (GAT)
  └──→ X06 (Temporal)

TASK-X02 (RST)
  └──→ X03 (Causal)

TASK-X05 (Active Learning)
  └──→ Tüm classifier görevler (A02, A03, A04, X01, X04)
```

---

## V. ÖZET TABLO

| #   | Görev                          | Kategori         | Zorluk | Öncelik | Faz |
| --- | ------------------------------ | ---------------- | ------ | ------- | --- |
|     |                                |                  |        |         |     |
| A02 | Argument Mining                | Akademi          | L      | P1      | 2   |
| A03 | Appraisal Theory               | Akademi          | M      | P2      | 2   |
| A04 | Speech Act Classification      | Akademi          | M      | P1      | 1   |
| A05 | Strategic Narrative Analysis   | Akademi          | L      | P2      | 2   |
| A06 | Presupposition Mining          | Akademi          | L      | P2      | 2   |
| A07 | Bayesian Position Tracker      | Akademi          | XL     | P2      | 3   |
| E01 | Contrastive Analysis Engine    | Mühendislik      | M      | P1      | 1   |
| E02 | GAT Fischer DNA                | Mühendislik      | XL     | P2      | 3   |
| E03 | Dense Retrieval RAG v2         | Mühendislik      | M      | P2      | 2   |
| E04 | Cross-Doc Event Coreference    | Mühendislik      | L      | P2      | 2   |
| E05 | Consensus/Divergence Tracker   | Mühendislik      | M      | P1      | 1   |
| X01 | Target-Stance Detection        | Ek (Akademi)     | M      | P1      | 1   |
| X02 | RST Discourse Parsing          | Ek (Akademi)     | L      | P2      | 2   |
| X03 | Causal Chain Mining            | Ek (Akademi)     | M      | P2      | 2   |
| X04 | Propaganda Technique Detection | Ek (Akademi)     | M      | P2      | 2   |
| X05 | Active Learning Queue          | Ek (Mühendislik) | M      | P1      | 1   |
| X06 | Temporal Relation Extraction   | Ek (Akademi)     | M      | P3      | 3   |
| X07 | Probability Calibration        | Ek (Mühendislik) | S      | P2      | 1   |

**Toplam:** 7 P1 görev (Faz 1) · 9 P2 görev (Faz 2) · 3 P2-P3 görev (Faz 3)

---

*Son güncelleme: Haziran 2025 · Kaynak: GRAPH_REPORT.md + akademik literatür taraması (ACL 2024-2025, EMNLP 2024-2025)*

| A01 | SRL Enrichment Layer           |
| --- | ------------------------------ |
| A02 | Argument Mining                |
| A03 | Appraisal Theory               |
| A04 | Speech Act Classification      |
| A05 | Strategic Narrative Analysis   |
| A06 | Presupposition Mining          |
| A07 | Bayesian Position Tracker      |
| E01 | Contrastive Analysis Engine    |
| E02 | GAT Fischer DNA                |
| E03 | Dense Retrieval RAG v2         |
| E04 | Cross-Doc Event Coreference    |
| E05 | Consensus/Divergence Tracker   |
| X01 | Target-Stance Detection        |
| X02 | RST Discourse Parsing          |
| X03 | Causal Chain Mining            |
| X04 | Propaganda Technique Detection |
| X05 | Active Learning Queue          |
| X06 | Temporal Relation Extraction   |
| X07 | Probability Calibration        |
