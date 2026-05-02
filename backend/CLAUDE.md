# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

This file covers the Python **backend** under `paprika/backend/`. The repo also contains a Unity frontend (`paprika/frontend/`) and shared assets, but agent logic, API, and persistence live here. Primary working directory: `paprika/backend/`.

## Common commands

Runner is `uv`; test/lint targets are wrapped in `Makefile`.

- `make test` — pytest excluding `paid` marker (default, safe)
- `make test PYTEST_ARGS="-k weather"` — single test / filtered test (pass args via `PYTEST_ARGS`)
- `make test-s` — same as `test` but with `-s` (stdout streamed)
- `make lint` — `ruff check .` (read-only)
- `make format` / `make fix` — `ruff format` / `ruff check --fix` (rewrites files)
- `make ci` — `lint` + `test` (matches what CI runs)
- `make test-all CONFIRM_PAID=1` — includes `@pytest.mark.paid` tests that hit real APIs (costs money)
- `make update-tapes CONFIRM_PAID=1` — re-record VCR cassettes for `pytest-recording`

Run a single test file directly: `uv run pytest tests/agents/test_action_integration.py -v`

### Services / Docker

- `docker compose up -d --build` — bring up Postgres (pgvector), Redis, and the `agent-runtime` FastAPI service. Backend code is bind-mounted at `/app`, so edits hot-reload via `uvicorn --reload`.
- Backend alone (no Docker): `uv sync && uv run uvicorn app.main:app --reload`. Requires a running Postgres with the `vector` extension and Redis at `REDIS_URL`.

### DB migrations (Alembic)

- `make migration msg="add X"` — autogenerate a revision *inside* the running `agent-runtime` container (compares `app/memory/models.py` against DB).
- `make migrate` — apply head migration inside the container.
- `make migrate-ci` — apply head migration directly on host (used by GitHub Actions, no Docker).
- On FastAPI startup, `app/core/lifecycle.py` runs `alembic upgrade head` automatically in a thread, so the app self-migrates when the container boots.

### Environment

`app/core/config.py` (`Settings`) loads from `.env` via `pydantic-settings`. Key vars:
- `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4.1-mini`) — required for the default LLM path and for embeddings (`text-embedding-3-small`, 1536-dim — must match `Vector(1536)` columns).
- `DATABASE_URL` (asyncpg DSN), `REDIS_URL`
- `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `OLLAMA_MODEL` — optional alternative provider
- `OPENWEATHER_API_KEY` / `_BASE_URL` — optional; `WeatherToolBuilder` **returns `None` and silently unregisters itself** when missing (see "Tool registry" below).
- `LANGCHAIN_*` — optional LangSmith tracing; `config.py` copies these into `os.environ` so LangChain libs pick them up.

Tests inject dummy values via `[tool.pytest.ini_options].env` in `pyproject.toml` (`OPENAI_API_KEY=dummy_test_key`). Live tests guard themselves with `skip_live_tests` in `tests/conftest.py`.

## Architecture

### Brain/Body split

Unity ("Body") and FastAPI ("Brain") are decoupled and talk over a **WebSocket**: `ws://host:8000/api/ws/agent/{client_id}` (`app/api/routes.py`). Each Unity frame of perception is sent as JSON, runs one invocation of the LangGraph, and a plan JSON is returned. **`action` ends the graph** — the graph intentionally halts at `END` after producing a plan so Unity can execute steps, then the next perception message resumes the loop (entering via `critic`, not `curriculum`). Session state (`task`, `plan`, `retry_count`, `skill_guide`) is kept in-memory per WebSocket connection; Redis persistence is scaffolded but currently commented out.

### LangGraph agent loop (`app/agents/graph.py`)

Four agents compiled into one `StateGraph[AgentState]`:

1. **CurriculumAgent** (`curriculum.py`) — picks the next task. Uses RAG over past `Memory` rows (`fetch_similar`) plus in-process `recent_history`. Output: `CurriculumOutput` JSON.
2. **SkillAgent** (`skill.py`) — on new tasks, retrieves the closest learned SOP from the `skills` table (vector similarity) and injects it into the action prompt. On success, summarizes the completed action trace into a generic SOP and upserts it (`save_skill`).
3. **ActionAgent** (`action.py`) — emits a **list** of `AgentAction` tool calls (`function`, `args={"id": ...}`, `thought_trace`). Prompt includes last-plan + critique on retry (Voyager-style feedback).
4. **CriticAgent** (`critic.py`) — verifies success against *world state* from the next perception frame. Output: `CriticOutput` with `success`/`reasoning`/`feedback`.

Conditional entry router (`entry_router`): if `task` is empty or `"Decide Next Task"` → `curriculum`; otherwise → `critic` (evaluating the plan Unity just executed). `decide_next_node` on critic: success → `learning` → `curriculum`; failure and `retry_count <= 2` → `action`; else → `failure` → `curriculum`.

Module-level singletons in `graph.py`: `openai_llm`, `session_factory`, `memory_store`, `tools`, and the four agents are constructed at import time — **importing `app.agents.graph` triggers real DB engine creation and tool registry build**. Keep this in mind for tests.

### Shared agent base & JSON parsing

All agents inherit from `BaseAgent` (`agents/base.py`):
- System prompt is built from `app/prompts/templates/<template_name>.md` via `prompts/loader.py`, with tool docs (`tools_doc`) interpolated from each tool's `args_schema.model_json_schema()`.
- `_parse_json_helper` uses regex to extract the first `[...]` or `{...}` block from LLM output — agents defensively parse rather than relying on structured output. Retry loops (`max_retries`) recurse on parse failure.

### `ObservationAdapter` (`agents/adapter.py`)

**Every agent routes perception through this adapter** rather than touching `Perception` fields directly. This is the insulation layer: when the Unity-side `Perception` schema changes, update the adapter's properties (`location`, `inventory`, `visual_summary`, `prepared_items_summary`, `last_execution_summary`) rather than every agent's prompt.

### Tool registry (`app/tools/base.py`)

Decorator-based: `@tool_registry.register` on a `BaseToolBuilder` subclass. Registration is import-time side-effectful; `app/tools/__init__.py` imports `internal` and `external` packages to populate the registry. `build_all(ToolContext)` materializes `StructuredTool` instances — if `builder.build()` returns `None` (e.g. missing API key), the tool is silently skipped. Tool names in prompts come from the `StructuredTool.name`, and every action tool uses the arg key **`id`** by convention to reduce LLM confusion.

Tools come in two flavors:
- `internal/` — world-interaction stubs (`move_to`, `pickup`, `put_down`, `cook`, `chop`). They return `{"status": ..., "target": id}` — **the real execution happens in Unity**; these builders exist so the LLM sees the tool surface in its prompt.
- `external/` — real API integrations (`weather.py` is the reference example).

### Memory layer

- SQLAlchemy models (`app/memory/models.py`): `Memory` (episodic, with `pgvector.Vector(1536)` embedding) and `Skill` (SOP/learned procedure, also vector-indexed, with `task_name` as unique key so `save_skill` is an upsert).
- `PostgresMemoryStore` (`pgvector_repo.py`) is the concrete `BaseMemoryStore`; calls `embed_text` from `vector_store.py` (OpenAI `text-embedding-3-small`). Similarity uses `embedding.l2_distance`. Tests patch `embed_text` to avoid real API calls.
- Async everywhere (`asyncpg` driver, `AsyncSession`, `async_sessionmaker`); session factory is a module-level singleton in `app/core/deps.py`.

### LLM abstraction (`app/llm/`)

`BaseLLMClient` + `BaseLLMBuilder` + `LLMRegistry` (`@llm_registry.register("openai")`). `get_llm(provider, model)` is `@lru_cache`d so each (provider, model) pair is a singleton. `OpenAIClient` wraps `langchain_openai.ChatOpenAI`; `OllamaClient` is the alternative.

## Extending

When adding new behavior, remember **Unity and backend must stay in sync** on contracts (tool names, Unity GameObject `id` strings, perception shape).

- **New tool**: add input schema in `app/tools/schemas.py`, add `@tool_registry.register` builder in `app/tools/internal/` or `external/`, implement matching C# handler in Unity. Keep arg key as `id` where possible.
- **New agent / node**: subclass `BaseAgent`, add a template under `app/prompts/templates/<name>.md`, wire a node function into `graph.py` and update edges.
- **Change perception shape**: update `app/api/schemas.py` (`Perception`, `SelfState`, `Sensory`, `ObjectView`, `Statistics`, `TraceStep`) **and** the `ObservationAdapter` properties; agent prompts read through the adapter, so they usually don't need changes.
- **New mission**: rules go in `app/prompts/templates/curriculum.md`; success criteria in `critic.md`; `skill.md` controls the generated-SOP format.

## Testing notes

- `asyncio_mode = "auto"` — async tests don't need `@pytest.mark.asyncio`.
- Markers: `paid` (hits paid APIs — excluded by default), `integration` (hits real external services).
- `pytest-recording` is configured for VCR cassettes; regenerate with `make update-tapes CONFIRM_PAID=1`.
- `tests/conftest.py` defines shared `Perception` / `ObjectView` / `CreateMemoryDTO` fixtures — reuse them rather than building perception objects by hand.
- CI (`.github/workflows/backend-tests.yml`) spins up pgvector + redis service containers, runs `make migrate-ci` then `make test`. `make ci` locally mirrors this.

## Conventions from contributing.md

Branches: `<type>/<kebab-case>` where type ∈ `feature|bugfix|hotfix|refactor|test|docs|chore`. PR titles: `<type>(<scope>): <summary>` with scope matching a top-level module (`agent`, `memory`, `tools`, `llm`, `api`, `config`, `docker`, etc.). Don't push to `main`; one logical change per PR.
