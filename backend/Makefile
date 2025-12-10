# Use uv for everything
PY = uv run

.PHONY: test test-unit test-integration agent-run

# Run all tests
test:
	$(PY) pytest

# Just unit tests (no integration)
test-unit:
	$(PY) pytest -m "not integration"

# Only integration tests
test-integration:
	$(PY) pytest -m integration

# Run the agent graph debug script (Paprika agent one-shot)
agent-run:
	$(PY) python scripts/run_graph.py
