# Değişken Tanımlamaları
PYTHON = poetry run python
PYTEST = poetry run pytest

.PHONY: build analyze test clean lint

# FAZ 0: Zemin Hazırlığı - Bağımlılıkların ve ortamın kurulumu
build:
	@echo "Sistem inşa ediliyor..."
	poetry install
	cp .env.example .env || true
	poetry run alembic upgrade head
	@echo "İnşa tamamlandı."

# FAZ 7: Application Use Cases - Analiz sürecini başlatır
analyze:
	@echo "Diplomatik söylem analizi başlatılıyor..."
	$(PYTHON) -m BB-PAXDATA.interfaces.cli.main analyze

# FAZ 8: Test Tamamlama - Tüm test suitini çalıştırır
test:
	@echo "Testler koşturuluyor..."
	$(PYTEST) tests/ --cov=src/BB-PAXDATA --cov-report=term-missing

# Ekstra: Kod kalitesi ve temizlik
lint:
	poetry run ruff check src/
	poetry run black --check src/
	poetry run mypy src/

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +