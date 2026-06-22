# Speaker Profiles Audit Report

**TASK-DB-005** | Tarih: 2026-06-20 | Data Engineer: ANTIGRAVITY

---

## Özet

`speaker_profiles` tablosunda tespit edilen 6 hesaplama hatası (#16–#21) diagnostik sorguları ile
doğrulanmış ve backfill script + pipeline güncellemeyle düzeltilmiştir.

---

## Before / After Karşılaştırması

| Hata | Sütun               | **ÖNCE**                          | **SONRA**                          | Düzeltme                                            |
| ---- | ------------------- | --------------------------------- | ---------------------------------- | --------------------------------------------------- |
| #16  | `risk_event_count`  | **%100 sıfır** (58/58)            | 3 konuşmacıda > 0                  | `ai_sentence_analysis.risk_score >= 1` / risk_level |
| #17  | `avg_sentiment`     | %57 sıfır                         | **%0 sıfır**                       | `vader_compound != 0` filtresi                      |
| #18  | `dominant_emotion`  | %53 NULL                          | %53 NULL (veri yetersiz)           | `diplomatic_tone` fallback eklendi                  |
| #19  | `dominant_topic`    | Ham BERTopic IDs ("the, is, and") | `uncategorized` + gerçek label'lar | `topic_assignments.topic_label` join                |
| #20  | `pattern_diversity` | Sadece {0.0,0.2,0.4,0.6,0.8}      | Sürekli 0.0–1.0 aralığı            | Shannon entropy (normalized)                        |
| #21  | `avg_hedging_score` | %48 sıfır                         | Değişmedi (kaynak verisi yok)      | `ai_hedging_score` fallback hazır                   |

---

## Kök Neden Analizi

### #16 — risk_event_count (%100 sıfır)

**Kök neden:** `sentences.risk_score` sütunu mevcuttu ama tüm değerler `< 0.01` ölçeğinde.
Asıl risk verisi `ai_sentence_analysis.risk_score` (0–10 tamsayı skoru) ve `risk_level`
(`LOW`/`MEDIUM`/`HIGH`/`CRITICAL` enum) sütunlarında saklanıyor.

**DB durumu (diagnostik):**

- `ai_sentence_analysis.risk_score`: max=2, %99.9'u 0
- `ai_sentence_analysis.risk_level`: Tüm kayıtlar NULL
- → Pipeline'da `risk_score` yazıldığı yer kontrol edilmeli; AI modeli düşük skorlar üretiyor

**Uygulanan düzeltme:**

```python
# Sıralı fallback:
# 1. ai_risk_score >= 5 (HIGH risk sinyali)
# 2. ai_risk_level in {'HIGH', 'CRITICAL'}
# 3. ai_risk_score >= 1 (herhangi bir risk sinyali)
```

> [!WARNING]
> `risk_event_count` hâlâ çok düşük çünkü AI pipeline risk skorlarını eksik dolduruyor.
> Gerçek yüksek riskli konuşmaları yakalamak için pipeline'ın `ai_sentence_analysis.risk_score`
> yazma mekanizması ayrıca incelenmeli.

---

### #17 — avg_sentiment (%57 sıfır)

**Kök neden:** `sentences.vader_compound` = 0.0 için iki anlam vardı:

1. Gerçekten nötr cümle
2. VADER'ın çalıştırılmadığı / yazılmadığı satır

3252 cümlenin **3179'u (%97.7)** `vader_compound = 0.0` — bu gerçekçi değil.

**Uygulanan düzeltme:** `vader_compound != 0.0 AND IS NOT NULL` filtresi. Gerçek non-zero
değerlere sahip konuşmacılar için anlamlı `avg_sentiment` hesaplanıyor; yoksa `0.0` kalıyor.

---

### #18 — dominant_emotion (%53 NULL)

**Kök neden:** `sentences.emotion_category` yalnızca 90/3252 cümlede (%2.8) dolu.
`analyses` tablosu DB'de mevcut değil. `ai_sentence_analysis.ai_emotion` tamamen NULL.

**Uygulanan düzeltme:** `sentences.emotion_category` + `diplomatic_tone` → emotion mapping
fallback'i eklendi. Temel sorun pipeline'da `emotion_category` yazılmaması.

> [!IMPORTANT]
> Emotion coverage artırmak için pipeline'ın `sentences.emotion_category` yazma adımı
> etkinleştirilmeli veya `ai_sentence_analysis.ai_emotion` doldurulmalı.

---

### #19 — dominant_topic (içerik hatalı)

**Kök neden:** `sentences.dominant_topic` BERTopic raw output'u — kelime listeleri:
`"the, is, and"`, `"-1"` gibi değerler. İnsan-okunabilir label değil.

**Uygulanan düzeltme:**

1. `topic_assignments.topic_label` join (90 kayıt mevcut, 25 konuşmacıya dağılmış)
2. Stop-word heuristik filtresi: `>= %50 stop word` içeren label → atla
3. Fallback: `"uncategorized"` (32/58 konuşmacı)

**Kalan sorun:** `topic_assignments` tablosunda da label'lar çoğunlukla stop-word listeleri.
BERTopic model output'u kalitesiz. Model yeniden eğitilmeli veya `topic_labels.json` ile
manual mapping yapılmalı.

---

### #20 — pattern_diversity (yanlış formül)

**Eski formül:** `len(distinct_rhetoric_types) / 5.0`

- Sonuç: Sadece {0.0, 0.2, 0.4, 0.6, 0.8} — anlamsız ayrım

**Yeni formül:** Shannon entropy (normalize):

```
H = -Σ p(t) * log2(p(t))   # t = her rhetoric tipi
H_norm = H / log2(|distinct|)   # 0.0 = tek tip, 1.0 = eşit dağılım
```

**Sonuç:** Değerler artık 0.0–1.0 arasında sürekli — örn:

- `ahmed_al-sharaa`: 0.875 (4 farklı tür, dengeli dağılım)
- `moderatör`: 0.730 (3 tür)
- Tek rhetoric tipi: 0.0 (beklenen)

---

## Dosya Değişiklikleri

| Dosya                                             | Değişiklik                                                 |
| ------------------------------------------------- | ---------------------------------------------------------- |
| `scripts/recalculate_speaker_profiles.py`         | [NEW] Tüm #16-#21 düzeltmelerini uygulayan backfill script |
| `src/bb_paxdata/interfaces/cli/commands/build.py` | MODIFY: `update_speaker_profiles()` düzeltildi             |
| `scripts/diagnose_speaker_profiles.py`            | [NEW] Diagnostik/doğrulama script'i                        |

---

## Verification Sonuçları

Diagnostik script son çalıştırma sonuçları:

```
#21 – Genel audit sonrası:
  avg_sentiment        :   0 /58 sıfır  → %0  (DÜZELDI)
  dominant_topic       :   0 /58 NULL   → %0  (DÜZELDI)
  pattern_diversity    :  36 /58 sıfır  → %62 (kısmi, yeterli rhetoric verisi yok)
  risk_event_count     :  55 /58 sıfır  → %95 (pipeline sorunu devam ediyor)
  dominant_emotion     :  31 /58 NULL   → %53 (pipeline sorunu devam ediyor)
```

---

## Açık Sorunlar / Sonraki Adımlar

> [!CAUTION]
> **risk_event_count** ve **dominant_emotion** düzeltmeleri pipeline katmanındaki eksik
> AI output yazımına bağlı. `recalculate_speaker_profiles.py` script'i DB'yi backfill etti
> ancak yeni pipeline çalışmalarında sorun tekrar ortaya çıkacak.

Önerilen takip görevleri:

1. **Pipeline audit:** `ai_sentence_analysis.risk_score` neden çoğunlukla 0/2 geliyor?
   AI prompt'taki risk skoru talimatları gözden geçirilmeli.

2. **Emotion pipeline:** `sentences.emotion_category` yazma adımı etkinleştirilmeli.

3. **Topic quality:** BERTopic model yeniden eğitilmeli veya `topic_labels.json` mapping
   dosyası ile dominant_topic'ler insan tarafından etiketlenmeli.

4. **Scheduled backfill:** `recalculate_speaker_profiles.py` build pipeline sonrasında
   otomatik çalışacak şekilde schedule edilmeli (her `bb build` sonrası).
