.PHONY: install lint typecheck test migrate validate clean

install:
	poetry install --with dev

lint:
	poetry run ruff check src tests
	poetry run ruff format --check src tests

typecheck:
	poetry run mypy --strict src

test:
	poetry run pytest tests/ -v --tb=short

test-cov:
	poetry run pytest tests/ --cov=src/bb_paxdata --cov-report=term-missing

migrate:
	poetry run bbpaxdata migrate run --legacy-db $(LEGACY_DB)

migrate-dry:
	poetry run bbpaxdata migrate run --legacy-db $(LEGACY_DB) --dry-run

validate:
	poetry run bbpaxdata validate db --strict

validate-json:
	poetry run bbpaxdata validate db --json --output reports/validation.json

install-completion-bash:
	poetry run bbpaxdata completions install bash

install-completion-zsh:
	poetry run bbpaxdata completions install zsh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete