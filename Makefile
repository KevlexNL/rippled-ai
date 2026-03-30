.PHONY: test test-unit test-integration lint backfill-extraction

PYTHON := .venv/bin/python
PYTEST  := .venv/bin/pytest

# Run unit tests only (fast, no DB required)
test-unit:
	$(PYTEST) tests/ --ignore=tests/integration -v

# Run integration tests against real Supabase DB (requires DATABASE_URL in env/.env)
test-integration:
	$(PYTEST) tests/integration/ -v --tb=short

# Run full test suite (unit + integration)
test: test-unit test-integration

# Lint
lint:
	.venv/bin/ruff check app/

# Backfill detection_audit data for source_items processed before audit logging
backfill-extraction:
	$(PYTHON) scripts/backfill_extraction_data.py
