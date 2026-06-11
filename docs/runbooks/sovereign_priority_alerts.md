# Runbook: SOVEREIGN_PRIORITY Kuyruğu Uyarıları Yönetimi

Bu rehber, egemen öncelikli (`SOVEREIGN_PRIORITY`) kuyrukta tıkanma veya aşırı yüklenme uyarısı tetiklendiğinde (örneğin bekleyen inceleme sayısı > 50 veya bekleme süresi > 72 saat) denetçilerin ve sistem yöneticilerinin yapması gereken teşhis ve müdahale adımlarını tanımlar.

---

## 1. Arka Plan & Eşik Değerleri

`SOVEREIGN_PRIORITY`, Tier-1 konuşmacıların (Güç Seviyesi >= 9 olan cumhurbaşkanı, dışişleri bakanı vb.) ve kritik anomali içeren cümlelerin yer aldığı en yüksek öncelikli kuyruktur. Bu kuyruktaki gecikmeler, diplomatik kriz analizlerinde kritik bilgi kayıplarına yol açabilir.

| Metrik | Uyarı Eşiği | Seviye | Açıklama |
|---|---|---|---|
| Kuyruk Derinliği (Queue Depth) | > 50 kayıt | HIGH | İnceleme bekleyen egemen kayıtların birikmesi |
| Bekleme Süresi (Age) | > 72 saat | CRITICAL | Stale review durumuna düşen ve otomatik eskalasyon bekleyen kayıtlar |

---

## 2. Hızlı Teşhis Adımları (Diagnostics)

### Adım 2.1: Veri Tabanı İstatistiklerinin Kontrolü
Arayüzde **Sistem Sağlığı** (`/health`) sayfasına gidin veya API üzerinden veri tabanı durumunu sorgulayın:

```bash
# Admin yetkisiyle DB stats API'sini çağırın
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/v1/database/stats
```

Eğer `status` değeri `"degraded"` ise, veri tabanı kilitlenmesi veya yavaşlığı yaşanıyor olabilir.

### Adım 2.2: Celery Worker Durumu
**Pipeline Monitör** (`/monitor`) sayfasına giderek asenkron worker'ların durumunu veya Grafana Celery Worker dashboard'unu (`http://localhost:3000/d/bbpaxdata-celery-workers/celery-workers`) inceleyin.
- `celery_active_tasks` sıfır değil ama ilerleme kaydedilmiyorsa, worker kilitlenmiş olabilir.
- `celery_queue_length` kontrol edin; Redis broker kuyruğunda yığılma olup olmadığını görün.

---

## 3. Müdahale ve Çözüm Adımları (Remediation)

### Adım 3.1: Streamlit Üzerinden Triage/Karar Girişi
1. `http://localhost:8501` adresindeki Streamlit HITL Dashboard'u açın.
2. Sol taraftaki **Formül** filtresini `risk_score` veya `sbi_score` yapın, **Durum** filtresini `Bekleyen` olarak seçin.
3. Öncelikli TIER1 konuşmacıların kayıtlarını (sağ panelde `🔴 TIER1 — Sovereign Priority` olarak görünür) seçerek sırayla karara bağlayın (`AI Doğru`, `AI Yanlış` veya `Değeri Düzelt`).

### Adım 3.2: Otomatik Triage Kalibrasyonu (Sistem Ayarları)
Kuyruğa anlık cümle giriş hızını azaltmak ve eşik hassasiyetini düşürmek için settings parametrelerini kalibre edin:
1. Web arayüzünde **Ayarlar** (`/settings`) sayfasına gidin.
2. `risk_threshold` (Varsayılan: 70) değerini **80**'e çekerek risk hassasiyetini düşürün.
3. `anomaly_controller_enabled` seçeneğini pasif duruma getirerek anomali denetleyici filtrelerini esnetin.
4. Kaydedip sistemi izlemeye devam edin.

### Adım 3.3: Worker ve Stack Yeniden Başlatma
Eğer kilitlenme devam ediyorsa, compose stack'ini yenileyin:

```bash
# Sadece worker ve broker servislerini yeniden başlatın
docker compose restart celery-worker-cpu celery-worker-io redis
```
