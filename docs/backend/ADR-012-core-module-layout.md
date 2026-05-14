# ADR-012: Core Module Layout — db / deps / lifecycle / exceptions

**Status:** Accepted <br>
**Date:** 2026-05-14 <br>
**Deciders:** vanillasky <br>

## Context

`app/core/` is where the application's wiring lives: settings, logging, the database engine, FastAPI lifespan, the typed exception hierarchy, and the small set of constructed singletons (LLM client, memory store) that the rest of the code asks for by factory call.

Before this ADR the layout had drifted into three concrete name / ownership problems:

1. **Doubled names.** `app/core/db/db.py` and `app/core/db/db_repo.py`. The package name already says "db"; repeating it in the filename gives readers nothing and looks like a copy-paste artefact.
2. **Vague names.** `app/core/db/helper.py` contained two startup-only utilities (`ping_database`, `ensure_pgvector_extension`). "helper" is the worst kind of filename: it tells you nothing about what is inside, and it attracts new code that has no better home.
3. **Smeared ownership.** `app/core/deps.py` re-exported `get_db_session` and `get_session_factory` from `db/db.py`. Callers were then split between `from app.core.deps import ...` and `from app.core.db.db import ...` for the same symbol, depending on which IDE auto-import won the day. The original purpose of `deps.py` — owning the *constructed* singletons (LLM client, memory store) — was diluted.

In parallel, `app/core/exceptions.py` defined only domain-agent errors (`InvalidPerceptionError`, `ContextBuildError`, `AgentExecutionError`). The DB-layer code raised raw `SQLAlchemyError` and `Exception`, so `routes._process_frame` had no typed boundary to map onto a client-facing error message for "Postgres is down" vs. "migration broken".

`lifecycle.py` had two thin helpers (`_prepare_database` and a separate `asyncio.to_thread(_run_migrations)` call) that always ran together but were spelled apart, hiding the fact that they form one "init the database" phase.

## Decision

We adopt the following layout and naming rules for `app/core/`:

```
app/core/
  __init__.py
  config.py           — Settings (pydantic-settings); exports `settings`
  logger.py           — setup_logging(Settings)
  exceptions.py       — PaprikaError hierarchy (agent + db subtrees)
  deps.py             — constructed singletons (LLM client, memory store)
  lifecycle.py        — FastAPI `lifespan`; setup_logging + _init_database
  db/
    __init__.py       — public exports: Repository, session helpers, engine
    session.py        — engine, session factory, get_db_session, session_scope, close_db
    bootstrap.py      — ping_database, ensure_pgvector_extension (startup-only)
    repository.py     — Repository[ModelT] generic CRUD helper
```

### Naming rules

1. **No doubled names.** A file inside `app/core/db/` MUST NOT be called `db.py` or contain `db_` as a prefix. The package name already supplies that context. So: `session.py`, not `db.py`; `repository.py`, not `db_repo.py`.
2. **No `helper.py` / `utils.py` files** in `app/core/`. If two functions only share "I run at startup", they go in `bootstrap.py`. If they share "I open a connection", they go in `session.py`. If you cannot find a better name than "helper", the functions probably belong inside the class that calls them.
3. **`deps.py` owns construction, not re-export.** It contains `get_llm`, `get_default_llm`, `get_memory_store` — each `@lru_cache`'d so the factory returns a singleton. It does NOT re-export `get_db_session` or `get_session_factory`. Callers wanting those import from `app.core.db` directly.
4. **`lifecycle.py` stays narrow.** It runs setup_logging, pings the DB, ensures pgvector, runs Alembic. It does NOT construct domain objects (LLM, memory store, agents) — those are lazy via `deps.py` on first use.
5. **Public surface of `db/`** is the package re-export in `db/__init__.py`. Other modules import `from app.core.db import Repository, get_session_factory, session_scope`. Reaching into `db.session` or `db.repository` directly is allowed but discouraged.

### Exception hierarchy

```
PaprikaError                     — base
├── InvalidPerceptionError       — incoming JSON failed pydantic validation
├── ContextBuildError            — PerceptionRenderer raised
├── AgentExecutionError          — graph_app.ainvoke raised
└── DatabaseError                — db layer
    ├── DatabaseUnavailableError — ping_database failed (DB not reachable)
    ├── PgvectorExtensionError   — CREATE EXTENSION vector failed
    └── MigrationError           — Alembic upgrade failed
```

Wiring:
- `db/bootstrap.ping_database` catches `SQLAlchemyError` → raises `DatabaseUnavailableError`.
- `db/bootstrap.ensure_pgvector_extension` catches `SQLAlchemyError` → raises `PgvectorExtensionError`.
- `lifecycle._run_migrations` catches `Exception` → raises `MigrationError` (preserves cause via `raise ... from exc`).
- `api/routes._CLIENT_ERROR_MESSAGES` maps `PaprikaError` subclasses to user-facing strings. DB subtree errors are not currently mapped because they fire at startup, not per-frame — but the type is available for future code that wants to differentiate.

### `_init_database` collapse

`lifecycle.py` previously had:

```python
async def _prepare_database() -> None:
    engine = get_engine()
    await ping_database(engine)
    await ensure_pgvector_extension(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings)
    await _prepare_database()
    await asyncio.to_thread(_run_migrations)
    ...
```

These two helpers ran together every time. They are now one phase:

```python
async def _init_database() -> None:
    engine = get_engine()
    await ping_database(engine)
    await ensure_pgvector_extension(engine)
    await asyncio.to_thread(_run_migrations)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings)
    await _init_database()
    ...
```

The migration call goes through `asyncio.to_thread` because Alembic's `env.py` runs `asyncio.run()` internally, and you cannot nest event loops. Keeping that bridge inline (rather than in a separate helper) makes the threading boundary visible at the point of use.

## Consequences

**Positive:**
- File names tell readers what is in them. New contributors do not have to open `db.py` and `helper.py` to find out what they own.
- One import path per symbol. `get_session_factory` is imported from `app.core.db`, never from `app.core.deps`.
- Database failures at startup raise typed exceptions that an operator can grep for in logs (`DatabaseUnavailableError` ≠ `PgvectorExtensionError` ≠ `MigrationError`), instead of a single `Exception: ...` line.
- `_init_database` is one phase, one read.

**Negative / trade-offs:**
- The package import `app.core.db` triggers `session.py` at import time, which creates the async engine via `create_async_engine(...)`. That means importing anywhere in the test suite touches engine construction. Tests mitigate via `[tool.pytest.ini_options].env` injecting dummy DSN values. Not new — same behaviour as before the rename — but worth noting that the engine is *not* lazy.
- The `Repository` class is now a top-level public name. If a future domain repository wants to name itself `Repository` too, it will shadow this one inside that module's namespace. Convention: domain repos use `<Thing>Repository` (e.g. `MemoryRepository`), keeping the bare name reserved for the generic CRUD helper.
- `from app.core.db import ...` is now the canonical path. Code that imported from `app.core.db.db` or `app.core.db.helper` before this ADR is broken and must be migrated. There is no compat shim — the goal is a clean tree, not a forwarding layer.

## Migration applied

Renames executed in this branch:

| Before | After |
|---|---|
| `app/core/db/db.py` | `app/core/db/session.py` |
| `app/core/db/db_repo.py` | `app/core/db/repository.py` (class `DbRepository` → `Repository`) |
| `app/core/db/helper.py` | `app/core/db/bootstrap.py` |

Touched call sites:

- `app/agents/graph.py` — now imports `get_session_factory` from `app.core.db`, not `app.core.deps`.
- `app/memory/pgvector_repo.py` — now imports `Repository` from `app.core.db.repository`.
- `app/core/lifecycle.py` — imports `ping_database`/`ensure_pgvector_extension` from `app.core.db.bootstrap` and `MigrationError` from `app.core.exceptions`; `_prepare_database` collapsed into `_init_database`.
- `app/core/deps.py` — no longer re-exports `get_db_session` / `get_session_factory`.

Tests are unaffected (they import `get_llm` / `get_default_llm` from `app.core.deps`, both still present; and they patch `app.memory.pgvector_repo.embed_text`, which is now backed by `app.llm.embeddings` but the patch target — the name as imported into `pgvector_repo` — is unchanged).

## Alternatives Considered

### A. Keep `db.py` / `db_repo.py`, just rename `helper.py`
**Rejected.** Half-measure. The same readability complaint applies to all three names. Doing one rename and leaving the other two perpetuates the inconsistency.

### B. Flatten — move `session.py`, `bootstrap.py`, `repository.py` up to `app/core/` directly
**Rejected.** Three more files in the top of `app/core/` crowds the namespace. The `db/` subpackage is a useful grouping; the contents just needed better names.

### C. Move `Repository` out of `core/db` into `app/memory/`
**Rejected.** The generic CRUD helper is not memory-specific — any future domain table (e.g. `actors` from ADR-011, `messages` later) will compose it. It belongs alongside the engine that backs it.

### D. Keep `deps.py` re-exporting db symbols for ergonomics
**Rejected.** Ergonomics is not worth the price of ambiguous ownership. Two import paths for one symbol means readers second-guess which is canonical; the IDE will pick a different one tomorrow.
