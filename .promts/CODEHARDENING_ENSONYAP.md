Projenin amacını ve FINETUNING.md'yi bildiğim için doğrudan söyleyeyim. Dead code tespiti ve optimizasyon için sana **4 ayrı repomix paketi** hazırlamanı öneririm — hepsini tek seferde atmak yerine odak odak çalışalım.

---

## Paket 1 — Pipeline Akışı (En Öncelikli)
*"Ne çağırıyor, ne çağrılıyor" sorusunu cevaplar. Dead code'un %70'i burada çıkar.*

```
src/bb_paxdata/application/pipeline/analysis_pipeline.py
src/bb_paxdata/application/pipeline/assembler.py
src/bb_paxdata/application/pipeline/configurator.py
src/bb_paxdata/application/pipeline/dki_assembler.py
src/bb_paxdata/application/pipeline/sbi_calculator.py
src/bb_paxdata/application/pipeline/stages/assemble_network.py
src/bb_paxdata/application/pipeline/stages/base.py
src/bb_paxdata/application/pipeline/stages/collect_stage.py
src/bb_paxdata/application/pipeline/stages/country_reference_collector.py
src/bb_paxdata/application/pipeline/stages/finalize_network.py
src/bb_paxdata/application/pipeline/stages/finalize_stage.py
src/bb_paxdata/application/pipeline/frame/frame_assembler.py
src/bb_paxdata/application/pipeline/frame/episodic_themetic_classifier.py
src/bb_paxdata/application/protocols.py
```

---

## Paket 2 — Domain Servisleri (İş Mantığı Çekirdeği)
*Burada hem logic duplikasyonu hem de protokol/impl karışıklığı olması kuvvetle muhtemel.*

```
src/bb_paxdata/domain/services/cross_anomaly_service.py
src/bb_paxdata/domain/services/drift_algorithms.py
src/bb_paxdata/domain/services/forecasting.py
src/bb_paxdata/domain/services/hedging_service.py
src/bb_paxdata/domain/services/risk_scoring.py
src/bb_paxdata/domain/services/risk_service.py
src/bb_paxdata/domain/services/sentiment_service.py
src/bb_paxdata/domain/services/spacy_pipeline.py
src/bb_paxdata/domain/services/topic_service.py
src/bb_paxdata/domain/services/frame_detection.py
src/bb_paxdata/domain/services/framing_service.py
src/bb_paxdata/domain/services/ner_service.py
src/bb_paxdata/domain/services/actor_resolver.py
src/bb_paxdata/domain/services/linguistic_helpers.py
src/bb_paxdata/domain/ports/anomaly_rule.py
src/bb_paxdata/domain/ports/embedding_port.py
src/bb_paxdata/domain/ports/negation_port.py
```

---

## Paket 3 — NLP Implementasyonları
*Domain servislerinin altyapı karşılıkları. Paket 2 ile birlikte bakınca hangi protokolün gerçekten kullanıldığı, hangisinin boşta durduğu görünür.*

```
src/bb_paxdata/infrastructure/nlp/cross_anomaly_service_impl.py
src/bb_paxdata/infrastructure/nlp/dynamic_position.py
src/bb_paxdata/infrastructure/nlp/ensemble_sentiment_service.py
src/bb_paxdata/infrastructure/nlp/fischer_dna_service.py
src/bb_paxdata/infrastructure/nlp/power_index_calculator.py
src/bb_paxdata/infrastructure/nlp/risk_signal_detector.py
src/bb_paxdata/infrastructure/nlp/semantic_shift.py
src/bb_paxdata/infrastructure/nlp/wordfish_scaler.py
src/bb_paxdata/infrastructure/nlp/wordscores_calibrator.py
src/bb_paxdata/infrastructure/nlp/stance_density.py
src/bb_paxdata/infrastructure/nlp/engagement_analyzer.py
src/bb_paxdata/infrastructure/nlp/lodp_service.py
src/bb_paxdata/infrastructure/nlp/negation_detector.py
src/bb_paxdata/infrastructure/nlp/maoz_dyadic_service.py
src/bb_paxdata/infrastructure/nlp/limited_ai_analyst.py
src/bb_paxdata/infrastructure/nlp/logic_only_analyst.py
src/bb_paxdata/infrastructure/ai/frame_detection/frame_detection_pipeline.py
src/bb_paxdata/infrastructure/ai/frame_detection/five_w_one_h_extractor.py
src/bb_paxdata/infrastructure/ai/frame_detection/concept_extractor.py
src/bb_paxdata/infrastructure/ai/frame_detection/coreference_resolver.py
src/bb_paxdata/infrastructure/ai/frame_detection/embedding_matcher.py
```

---

## Paket 4 — Modeller + Enum'lar (Referans)
*Bu paketi diğerlerinden bağımsız atmana gerek yok ama model şişmesi / kullanılmayan alan tespiti için ayrı bakılabilir.*

```
src/bb_paxdata/domain/models/   ← tüm dizin
src/bb_paxdata/domain/enums/    ← tüm dizin
```

---

## Kesinlikle Atma

| Dizin/Dosya | Neden |
|---|---|
| `tests/` | Amaçla alakasız |
| `scripts/` | Tek seferlik araçlar |
| `alembic/` | Sadece migration geçmişi |
| `frontend/` | Ayrı dünya |
| `src/.../auth/` | Altyapı detayı |
| `src/.../webhooks/` | Altyapı detayı |
| `src/.../observability/` | Monitoring |
| `src/.../export/` | Output formatı |
| `src/.../legacy_migration/` | Geçmiş veri taşıma |
| `src/.../cache/` | Altyapı |

---

**Önerim:** Önce Paket 1 + Paket 2'yi birlikte at. Pipeline'ın neyi çağırdığını görünce domain servislerindeki dead code hemen belli olur. Sonra Paket 3'ü ekleriz, protokol-impl uyumsuzluklarına bakarız.