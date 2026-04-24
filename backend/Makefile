PY := uv run
PYTEST_ARGS ?=

.PHONY: test test-all lint format fix update-tapes ci help migration migrate migrate-ci

help:
	@echo "make lint         - ruff check (read-only)"
	@echo "make test         - pytest excluding paid tests"
	@echo "make ci           - lint + free tests"
	@echo "make test-all     - run all tests (may cost money)"
	@echo "make update-tapes - rewrite VCR cassettes (costs money)"
	@echo "make format       - ruff format (rewrites code)"
	@echo "make fix          - ruff check --fix (rewrites some code)"

test:
	$(PY) pytest -m "not paid" $(PYTEST_ARGS)

test-s:
	$(PY) pytest -m "not paid" -s

ci: lint test

lint:
	$(PY) ruff check .

format:
	$(PY) ruff format .

fix:
	$(PY) ruff check --fix .

test-all:
	@test "$(CONFIRM_PAID)" = "1" || (echo "Set CONFIRM_PAID=1 to run paid tests"; exit 1)
	$(PY) pytest $(PYTEST_ARGS)

update-tapes:
	@test "$(CONFIRM_PAID)" = "1" || (echo "Set CONFIRM_PAID=1 to rewrite cassettes"; exit 1)
	$(PY) pytest -m "paid" --record-mode=rewrite



# usage:
# make test PYTEST_ARGS=-s
# make test PYTEST_ARGS="-s -vv"
# make test PYTEST_ARGS="-k weather"

# ------------------------------------------------------------------
# DB Migrations (Docker Integration)
# ------------------------------------------------------------------

migration:
	@test -n "$(msg)" || (echo "Error: msg is undefined. Usage: make migration msg='your message'"; exit 1)
	docker compose exec agent-runtime alembic revision --autogenerate -m "$(msg)"

migrate:
	docker compose exec agent-runtime alembic upgrade head

migrate-ci:
	$(PY) alembic upgrade head