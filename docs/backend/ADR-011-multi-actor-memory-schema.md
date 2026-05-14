# ADR-011: Multi-Actor Memory Schema for Co-Work Agents

**Status:** Proposed <br>
**Date:** 2026-05-14 <br>
**Deciders:** vanillasky <br>

## Context

ADR-007 fixed the storage choice (Postgres + pgvector) and gave us two tables:

- `memories` — episodic log, vector-indexed, queried by similarity for `CurriculumAgent` RAG.
- `skills` — learned SOPs, unique by `task_name`, queried by similarity for `SkillAgent` warm-start.

Both tables are **actor-less**: there is no column that says *which* mind owns a row. That was correct for a single-agent Voyager-style loop but breaks the moment we move to the current target game design:

- **Two agents** cooperating in the same kitchen, plus
- **One human** player sharing the world, with
- **Optional human↔agent (and agent↔agent) dialogue** coming in a later phase.

Without an actor dimension, three concrete problems appear:

1. **POV contamination in episodic memory.** Each agent stands in a different place, sees different objects, and produces different traces per frame. Writing both streams into the same `memories` table gives `CurriculumAgent.fetch_similar()` a mixed bag — Agent A's RAG retrieval may surface Agent B's memories from the other side of the kitchen.
2. **Skill library aliasing.** `skills.task_name` is globally unique today (used as the upsert key in `save_skill`). If Agent A and Agent B both learn "Cook Burger" with different specialised steps (e.g. chef vs. waiter roles), one upserts over the other.
3. **No place for messages.** When dialogue lands there is no `messages` table to anchor it to — `memories` is wrong because chat is fundamentally ordered, not similarity-searched, and conflating the two muddies retrieval.

A snippet from a prior project proposed a 7-table split (conversational / semantic / workflow / toolbox / entity / summary / tool_log). We considered it and rejected it as premature for this scope — see *Alternatives Considered*.

## Decision

We add **one new table (`actors`)**, **two columns (`actor_id`)** on the existing tables, and **scope existing queries by `actor_id`**. A `messages` table is deferred until human↔agent talk actually lands.

### Schema (Alembic migration)

```sql
-- 1. Actors: minimal identity rows for the two agents and (optionally) the human.
CREATE TABLE actors (
    id            SERIAL PRIMARY KEY,
    kind          VARCHAR NOT NULL,          -- 'human' | 'agent'
    display_name  VARCHAR NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT actors_kind_check CHECK (kind IN ('human', 'agent'))
);

-- 2. Episodic memory becomes per-actor.
ALTER TABLE memories
    ADD COLUMN actor_id INTEGER NOT NULL
        REFERENCES actors(id) ON DELETE CASCADE;
CREATE INDEX idx_memories_actor_day
    ON memories (actor_id, in_game_day DESC, time_slot DESC);

-- 3. Skill library becomes per-actor. task_name is no longer globally unique.
ALTER TABLE skills
    DROP CONSTRAINT skills_task_name_key,
    ADD COLUMN actor_id INTEGER NOT NULL
        REFERENCES actors(id) ON DELETE CASCADE,
    ADD CONSTRAINT skills_actor_task_unique UNIQUE (actor_id, task_name);
CREATE INDEX idx_skills_actor ON skills (actor_id);
```

### Deferred: `messages` (add when chat lands)

```sql
CREATE TABLE messages (
    id              BIGSERIAL PRIMARY KEY,
    from_actor_id   INTEGER NOT NULL REFERENCES actors(id),
    to_actor_id     INTEGER REFERENCES actors(id),       -- NULL => broadcast / group
    channel         VARCHAR NOT NULL DEFAULT 'global',
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_messages_channel_time
    ON messages (channel, created_at DESC);
```

Plain SQL, no vector column. Chat is ordered, not similarity-searched. If "find all times the human mentioned onions" becomes a real query later, that gets its own derived embedding column or a separate `semantic_dialogue_memory` table — *at that point*, not now.

### Python contracts

| Module / class | Change |
|---|---|
| `app/memory/models.py` — `Memory`, `Skill` | Add `actor_id` column, FK to `actors`. Add `Actor` model. |
| `app/api/schemas.py` — `CreateMemoryDTO`, `MemoryDTO`, `SkillDTO` | Add required `actor_id: int`. |
| `app/memory/base.py` — `BaseMemoryStore` | All read methods take `*, actor_id: int`. `save()` reads it from the DTO. |
| `app/memory/pgvector_repo.py` — `PostgresMemoryStore` | Every `select(...)` adds `.where(Memory.actor_id == actor_id)` / `.where(Skill.actor_id == actor_id)`. |
| `app/agents/curriculum.py`, `skill.py` | Constructor takes `actor_id`; threads it into `memory_store.fetch_*` calls. |
| `app/agents/graph.py` | Constructs **one set of agents per actor** (the existing module-level singletons become a factory keyed by `actor_id`). |
| `app/api/routes.py` | `client_id` path param resolves to an `actor_id` row at connect time (auto-create on first sight, or refuse unknown ids — see *Open questions*). |

### Skill scope: per-actor (not shared, not hybrid)

We considered three options:

| Strategy | Pros | Cons |
|---|---|---|
| **Per-agent library** (chosen) | No cross-agent contamination. Specialised roles learn distinct SOPs. Easy to merge later if both agents converge on the same skill. | 2× row count for skills the agents share. Slightly slower warm-start in early game when neither agent has many skills. |
| Shared global library | Faster learning (skills generalise across agents). | Specialised roles overwrite each other. Voyager's canonical assumption breaks once roles diverge. |
| Hybrid (`actor_id NULLABLE`, NULL = shared) | Best of both in theory. | `fetch_similar_skills` becomes a UNION with a precedence rule. Easy to get wrong. Premature. |

Picked **per-agent**. Migration from per-agent → shared is a single SQL pass; the reverse is impossible without provenance. Start with the reversible choice.

## Consequences

**Positive:**
- POV streams stay clean — no cross-agent leakage in RAG retrieval.
- The skill library compiles a distinct procedure store per agent, which fits the co-work design (chef vs. waiter, prep vs. plating).
- `messages` lands cleanly when needed without retrofitting `memories`.
- `ON DELETE CASCADE` makes "reset agent X" a single `DELETE FROM actors WHERE id=...` rather than a multi-table sweep.

**Negative / trade-offs:**
- Existing dev rows in `memories` / `skills` cannot satisfy `actor_id NOT NULL` and must be backfilled or wiped. We are pre-prod; recommended path is wipe + recreate two `actors` rows for agent_1 / agent_2.
- The module-level singletons in `app/agents/graph.py` (`curriculum_agent`, `skill_agent`, `action_agent`, `critic_agent`) currently assume one mind. They become a per-actor factory, keyed by `actor_id`. WebSocket `session_state` carries the `actor_id` so the right factory bucket is reached.
- `task_name` collisions across agents are intentional now — anyone reading `skills` must always include `actor_id` in their `WHERE` clause. This is enforced by the new composite unique key (which makes "missed scoping" surface as a constraint violation at write time, not silently wrong reads).
- If the human is ever a row in `actors`, their `actor_id` participates in FKs but never owns episodic / skill rows. Modelled by application convention, not DB constraint, to keep the schema flat.

## Alternatives Considered

### A. Keep one shared table; tag rows with `actor_id` but query un-scoped
**Rejected.** The schema enforces nothing; every caller has to remember to filter. The first forgotten `WHERE actor_id = ?` returns wrong data silently.

### B. Per-actor table proliferation (the 7-table snippet: conversational / semantic / workflow / toolbox / entity / summary / tool_log)
**Rejected — premature.** Two production stores (`memories`, `skills`) already cover Voyager's loop. The remaining five categories are speculation about what categorisation the agents will *need*; we don't have evidence yet. If `semantic` vs. `workflow` becomes a real retrieval distinction later, that is a follow-up ADR with concrete query patterns motivating it.

### C. Separate physical databases per actor
**Rejected.** Operationally heavy (two pgvector instances, two migration heads, two backup pipelines). Single-DB with `actor_id` gives the same isolation at query level with none of the overhead.

### D. Hybrid skill library (shared + per-actor with precedence)
**Rejected for now.** See decision table above. Cheap to add later if a clear "this skill is for everyone" pattern emerges in play.

## Open Questions

1. **Actor identity vs. WebSocket client.** Today `client_id` in the WS URL is opaque. After this ADR, do we (a) map `client_id` → `actor_id` 1:1 (each Unity client is one agent), or (b) keep them separate (one client can drive multiple agents)? Default: (a) — simpler, matches current Unity behaviour.
2. **Human row.** Is the human in `actors` from day one (anticipating dialogue), or only when chat lands? Default: insert at migration time so FKs are stable.
3. **Mode field on `memories`.** `mode` already encodes `reality | dream`. With multiple actors this becomes a (mode, actor) composite — confirm we don't want to split *that* into another table. Default: keep, no split.
