# ADR-007: PostgreSQL + pgvector for Episodic and Skill Memory

**Status:** Accepted <br>
**Date:** 2026-02-01 <br>
**Deciders:** vanillasky <br>

## Context

The Voyager-inspired design requires two persistent memory stores:

1. **Episodic memory** — a log of past observations and reflections, queryable by semantic similarity, used by `CurriculumAgent` to make context-aware task decisions.
2. **Skill memory** — a library of generalized Standard Operating Procedures (SOPs), queryable by task name similarity, used by `SkillAgent` for warm-start planning.

Both stores require:
- **Vector similarity search** (cosine or L2 distance) to retrieve relevant past records by semantic query.
- **Relational metadata** (time, location, success count, ingredient types) for filtering or aggregation.
- **Durable persistence** across backend restarts and WebSocket reconnections.
- **Upsert semantics** for skills (same task name → update, not duplicate).

Options considered:

| Store | Vector search | Relational | Upsert | Operational complexity |
|-------|--------------|------------|--------|----------------------|
| PostgreSQL + pgvector | Yes (native) | Yes | Yes | Low (single DB) |
| ChromaDB | Yes (primary) | Limited | Yes | Medium (separate service) |
| Pinecone / Weaviate | Yes (primary) | Limited | Yes | High (external SaaS) |
| Redis + RediSearch | Yes | Limited | Yes | Medium (separate service) |
| SQLite + custom cosine | Manual | Yes | Yes | Low but slow at scale |

The project already requires PostgreSQL for Alembic-managed schema migrations. Adding a separate vector database doubles the operational footprint without providing a benefit at our data scale (hundreds, not millions, of records).

## Decision

We use **PostgreSQL with the `pgvector` extension** for both memory types, running as the single database instance.

### Schema

**`memories` table** (episodic):

```sql
CREATE TABLE memories (
    id           SERIAL PRIMARY KEY,
    in_game_day  INTEGER,
    time_slot    INTEGER,
    location_id  VARCHAR,
    mode         VARCHAR,           -- 'reality' | 'dream'
    memory_type  VARCHAR,           -- 'observation' | 'reflection'
    content      TEXT NOT NULL,
    emotion_tags JSON,
    importance   FLOAT,
    embedding    VECTOR(1536),      -- OpenAI text-embedding-3-small
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON memories USING ivfflat (embedding vector_cosine_ops);
```

**`skills` table**:

```sql
CREATE TABLE skills (
    id            SERIAL PRIMARY KEY,
    task_name     VARCHAR UNIQUE NOT NULL,   -- upsert key
    description   TEXT,
    steps_text    TEXT,
    code          TEXT,                      -- reserved for future code gen
    embedding     VECTOR(1536),
    success_count INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON skills USING ivfflat (embedding vector_cosine_ops);
```

### Embedding Strategy

All embeddings use **OpenAI `text-embedding-3-small`** (1536 dimensions):
- Memory: embed the `content` field (observation text).
- Skill: embed `task_name + " " + description`.

The embedder is a singleton via `@lru_cache` on `get_embedder()` to avoid repeated client instantiation.

### Retrieval

```python
# Episodic retrieval (CurriculumAgent context)
similar = await memory_repo.fetch_similar(query=perception_summary, limit=10)

# Skill retrieval (SkillAgent warm start)
skill = await skill_repo.fetch_similar_skills(query=task_name, limit=1)
```

Both use pgvector's `<=>` (cosine distance) operator:

```sql
SELECT * FROM memories
ORDER BY embedding <=> $1
LIMIT $2;
```

### Skill Upsert

Skills are upserted on `task_name` (unique) to prevent duplicates when the same task type is completed multiple times:

```python
INSERT INTO skills (task_name, description, steps_text, embedding)
VALUES ($1, $2, $3, $4)
ON CONFLICT (task_name) DO UPDATE
SET steps_text = EXCLUDED.steps_text,
    embedding  = EXCLUDED.embedding,
    updated_at = NOW(),
    success_count = skills.success_count + 1;
```

## Consequences

**Positive:**
- Single database for relational data and vector search — one migration system (Alembic), one connection pool (asyncpg), one backup target.
- `ivfflat` index provides sub-linear similarity search; adequate for hundreds to low thousands of records.
- Upsert on `task_name` means the skill library converges over time — repeated successes refine the SOP rather than fragment it.
- pgvector is production-grade and ships with Docker images (`ankane/pgvector`).

**Negative / trade-offs:**
- `ivfflat` requires a minimum corpus size (typically ~1000 vectors) to build an efficient index. Below that, it falls back to sequential scan — acceptable for our data volumes but worth monitoring.
- Embedding cost: every new memory or skill writes one OpenAI embedding API call (pricing: ~$0.02 per 1M tokens — negligible at this scale).
- Skills identified only by `task_name` means curriculum naming must be consistent. If `CurriculumAgent` names the same task type differently on separate occasions, the skill library fragments.

## Alternatives Considered

### A. ChromaDB (embedded or server mode)
**Rejected.** Adds a second service to operate. The embedded mode (in-process) conflicts with FastAPI's async model. Server mode adds a second Docker container with no benefit at our data scale.

### B. Pinecone / Weaviate (SaaS)
**Rejected.** External API dependency, egress latency, and cost at low data volumes. Not appropriate for an academic project.

### C. In-memory vector store (no persistence)
**Rejected.** Skill library and episodic memory are lost on restart. The Voyager learning loop requires persistence to accumulate value across sessions.

### D. SQLite with manual cosine similarity
**Rejected.** SQLite does not natively support vector indices. Computing cosine similarity in Python over a full table scan becomes slow quickly, and it is a second database engine alongside PostgreSQL (already required for pgvector).
