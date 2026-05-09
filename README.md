# BB-PAXDATA

## Database Migrations (Alembic)

### İlk Kurulum

```bash
alembic upgrade head
```

### Yeni Migration Oluştur (ORM değişikliği sonrası)

```bash
python -m bb_paxdata.infrastructure.db.migrations make -m "add_new_column"
```

veya

```bash
alembic revision --autogenerate -m "add_new_column"
```

### Migration Uygula

```bash
python -m bb_paxdata.infrastructure.db.migrations up
```

veya

```bash
alembic upgrade head
```

### Geri Al

```bash
python -m bb_paxdata.infrastructure.db.migrations down
```

veya

```bash
alembic downgrade -1
```

### Mevcut Durum

```bash
alembic current
alembic history --verbose
```
