# Runner
PY := uv run
PYTEST_ARGS ?=

.PHONY: test test-all lint format fix update-tapes ci help

help:
	@echo "make lint         - ruff check (read-only)"
	@echo "make test         - pytest excluding paid tests"
	@echo "make ci           - lint + free tests"
	@echo "make test-all     - run all tests (may cost money)"
	@echo "make update-tapes - rewrite VCR cassettes (costs money)"
	@echo "make format       - ruff format (rewrites code)"
	@echo "make fix          - ruff check --fix (rewrites some code)"

# Default: Run free tests
test:
	$(PY) pytest -m "not paid" $(PYTEST_ARGS)

# CI-safe: read-only checks + free tests
ci: lint test

lint:
	$(PY) ruff check .

# Optional targets (these DO modify files)
format:
	$(PY) ruff format .

fix:
	$(PY) ruff check --fix .

# Potentially expensive (opt-in)
test-all:
	@test "$(CONFIRM_PAID)" = "1" || (echo "Set CONFIRM_PAID=1 to run paid tests"; exit 1)
	$(PY) pytest $(PYTEST_ARGS)

# Rewrite cassettes (costs money + modifies cassette files)
update-tapes:
	@test "$(CONFIRM_PAID)" = "1" || (echo "Set CONFIRM_PAID=1 to rewrite cassettes"; exit 1)
	$(PY) pytest -m "paid" --record-mode=rewrite



# usage:
# make test PYTEST_ARGS=-s
# make test PYTEST_ARGS="-s -vv"
# make test PYTEST_ARGS="-k weather"