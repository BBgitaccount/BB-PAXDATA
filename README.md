# BB-PAXDATA

## Repositories and Unit of Work

ORM tablolarına doğrudan SQL yazmak yerine `SentenceRepository`, `SegmentRepository`, `AnalysisRepository` ve `SqlAlchemyUnitOfWork` kullanın; dışarıya yalnızca Pydantic domain modelleri çıkar.

Örnek (eski `DatabaseBuilder_v5_8.py` tarzı ham `INSERT` yerine):

```python
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.enums import RiskLevel
from bb_paxdata.infrastructure.db.session import SessionLocal
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork

uow = SqlAlchemyUnitOfWork(SessionLocal)
with uow:
    sentence = uow.sentences.get("s-123")
    if sentence:
        uow.analysis.save_sentence_analysis(
            Analysis(
                id="new",
                sentence_id=sentence.id,
                segment_id=sentence.segment_id,
                risk_level=RiskLevel.MEDIUM,
                sentiment_score=0.0,
                confidence_score=0.9,
            )
        )
```

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
