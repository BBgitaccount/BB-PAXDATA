# BB-PAXDATA Process Manager

Docker alternatifi olarak tasarlanmış, tüm BB-PAXDATA servislerini yöneten otomatik süreç yöneticisi.

## Özellikler

- ✅ **Tüm servislerin otomatik yönetimi** - PostgreSQL, Redis, Meilisearch, MinIO, API, Web, Celery workers, monitoring tools
- ✅ **Bağımlılık yönetimi** - Servisler doğru sırada başlatılır (postgres → redis → api → web vb.)
- ✅ **Health check monitoring** - Servislerin sağlığı sürekli kontrol edilir
- ✅ **Otomatik restart** - Çöken servisler otomatik olarak yeniden başlatılır
- ✅ **Log yönetimi** - Log rotation, compression ve otomatik temizleme
- ✅ **Windows Service desteği** - Boot'ta otomatik başlatma
- ✅ **Profilsel çalışma** - Minimal, development, full profilleri
- ✅ **Konfigürasyon dosyası** - JSON ile kolay özelleştirme

## Kurulum

### Gereksinimler

```bash
# Python dependencies
poetry install

# Ek Python paketleri
poetry add psutil httpx

# Windows Service için (opsiyonel)
poetry add pywin32
```

### Manuel servis kurulumları (Docker olmadan)

Process Manager servisleri yönetir ancak şu servislerin sistemde kurulu olması gerekir:

1. **PostgreSQL 16 + pgvector**
   - Windows: https://www.postgresql.org/download/windows/
   - pgvector extension: https://github.com/pgvector/pgvector

2. **Redis**
   - Windows: https://github.com/microsoftarchive/redis/releases
   - veya WSL2 ile Linux Redis

3. **Meilisearch**
   - Windows: https://github.com/meilisearch/meilisearch/releases
   - veya Chocolatey: `choco install meilisearch`

4. **MinIO**
   - Windows: https://min.io/download
   - veya Chocolatey: `choco install minio`

5. **Prometheus**
   - Windows: https://prometheus.io/download/

6. **Grafana**
   - Windows: https://grafana.com/grafana/download

7. **Jaeger**
   - Windows: https://www.jaegertracing.io/download/

## Kullanım

### Temel komutlar

```bash
# Tüm servisleri başlat
python scripts/process_manager/process_manager.py start

# Tüm servisleri durdur
python scripts/process_manager/process_manager.py stop

# Tüm servisleri yeniden başlat
python scripts/process_manager/process_manager.py restart

# Servis durumlarını görüntüle
python scripts/process_manager/process_manager.py status

# Servisleri başlat ve sürekli izle (monitoring mode)
python scripts/process_manager/process_manager.py monitor
```

### Windows Service olarak kurulum

```bash
# Service'i kur (boot'ta otomatik başlar)
python scripts/process_manager/windows_service.py install

# Service'i başlat
python scripts/process_manager/windows_service.py start

# Service'i durdur
python scripts/process_manager/windows_service.py stop

# Service'i kaldır
python scripts/process_manager/windows_service.py remove
```

### Log yönetimi

```bash
python scripts/process_manager/log_manager.py
```

Log manager şu işlemleri yapar:
- 100MB'den büyük logları otomatik rotate eder (compress)
- 30 günden eski logları siler
- Tüm logları tek dosyada aggregate edebilir

## Konfigürasyon

### manager_config.json

`scripts/process_manager/manager_config.json` dosyası tüm servis ayarlarını içerir:

```json
{
  "global_settings": {
    "log_directory": "logs",
    "log_max_size_mb": 100,
    "log_max_age_days": 30,
    "health_check_interval_seconds": 10,
    "restart_delay_seconds": 5,
    "max_restarts_per_service": 3
  },
  "services": {
    "postgres": {
      "enabled": true,
      "auto_restart": true,
      "env_vars": {}
    },
    ...
  },
  "profiles": {
    "minimal": ["postgres", "redis", "api", "web"],
    "full": ["postgres", "redis", "meilisearch", "minio", "api", "web", ...],
    "development": ["postgres", "redis", "meilisearch", "api", "web", ...]
  }
}
```

### Servis özelleştirme

Her servis için şu ayarları değiştirebilirsiniz:
- `enabled`: Servisin başlatılıp başlatılmayacağı
- `auto_restart`: Çökünce otomatik restart
- `port`: Port numarası
- `env_vars`: Environment variables
- `health_check_url`: Health check endpoint
- `startup_timeout`: Başlatma timeout'u (saniye)

## Servis Listesi

| Servis | Port | Description | Dependencies |
|--------|------|-------------|--------------|
| postgres | 5432 | PostgreSQL database with pgvector | - |
| redis | 6379 | Redis cache | - |
| meilisearch | 7700 | Full-text search engine | - |
| minio | 9000 | S3-compatible object storage | - |
| api | 8000 | FastAPI backend | postgres, redis, meilisearch |
| web | 5173 | React frontend | api |
| celery-worker-cpu | - | AI tasks worker | postgres, redis, api |
| celery-worker-io | - | Graph I/O worker | postgres, redis, meilisearch, api |
| celery-beat | - | Scheduled tasks | postgres, redis, api |
| flower | 5555 | Celery monitoring UI | redis |
| prometheus | 9090 | Metrics collection | - |
| grafana | 3000 | Metrics dashboard | prometheus |
| jaeger | 16686 | Distributed tracing | - |

## Profiller

### Minimal Profile
Sadece core servisler:
```bash
# API ve Web için minimum setup
postgres, redis, api, web
```

### Development Profile
Geliştirme için gerekli servisler:
```bash
postgres, redis, meilisearch, api, web, celery workers, flower
```

### Full Profile
Tüm servisler including monitoring:
```bash
Tüm servisler + prometheus + grafana + jaeger
```

## Troubleshooting

### Servis başlamıyor

1. Servis loglarını kontrol et:
```bash
cat logs/<service_name>.log
```

2. Port çakışmasını kontrol et:
```bash
netstat -ano | findstr :<port>
```

3. Bağımlılıkların çalıştığını kontrol et:
```bash
python scripts/process_manager/process_manager.py status
```

### PostgreSQL connection error

PostgreSQL'in çalıştığından ve pgvector extension'ın yüklü olduğundan emin ol:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Redis connection error

Redis'in çalıştığını kontrol et:
```bash
redis-cli ping
# Should return: PONG
```

### Memory issues

Eğer sistem yetersiz memory var, bazı servisleri devre dışı bırakabilirsiniz:

```json
{
  "services": {
    "celery-worker-io": {
      "enabled": false
    },
    "jaeger": {
      "enabled": false
    }
  }
}
```

## Docker ile Karşılaştırma

| Özellik | Docker | Process Manager |
|--------|--------|-----------------|
| Kurulum kolaylığı | ✅ Tek komut | ❌ Manuel servis kurulumu |
| Port yönetimi | ✅ Otomatik | ✅ Manuel config |
| Network izolasyonu | ✅ Container network | ❌ Local network |
| Resource limits | ✅ CPU/Memory limits | ❌ Sistem limitleri |
| Cross-platform | ✅ Her platform | ⚠️ Windows odaklı |
| Debugging | ❌ Container içi zor | ✅ Direkt process erişimi |
| Geliştirme hızı | ✅ Hızlı rebuild | ⚠️ Manual restart |
| Production ready | ✅ Endüstri standardı | ⚠️ Custom solution |

## Öneriler

### Development için
- Docker kullanmaya devam et (daha kolay)
- Process Manager sadece Docker olmadığında fallback olarak kullan

### Production için
- Docker Engine kur (Docker Desktop değil)
- Process Manager yerine Docker Compose kullan

### Eski laptop sunucu senaryosu
- Docker Engine kur (lightweight)
- Process Manager sadece Docker kurulumu zor olursa kullan

## Log Dosyaları

Tüm loglar `logs/` dizininde tutulur:
- `logs/process_manager.log` - Process manager logları
- `logs/<service>.log` - Her servisin kendi log'u
- `logs/service.log` - Windows service logları
- `logs/aggregated.log` - Tüm logların birleşimi

## Güvenlik

Production için şu ayarları değiştir:
- JWT secret key
- Database passwords
- Meilisearch master key
- MinIO access keys
- CORS allowed origins

## Lisans

BB-PAXDATA projesinin bir parçasıdır.
