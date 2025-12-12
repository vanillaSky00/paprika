# Use uv for everything
PY = uv run

.PHONY: test test-all lint format

# Run only free tests (Default)
test:
	$(PY) pytest -m "not paid"

# Run ALL tests, including those that cost money
test-all:
	$(PY) pytest

# Format code (using ruff, which uv often pairs with)
format:
	$(PY) ruff format .

# Check for linting errors
lint:
	$(PY) ruff check .

# Re-run against real API and update cassettes (Costs money)
update-tapes:
    $(PY) pytest --record-mode=rewrite