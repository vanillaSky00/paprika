# ADR-013: Single Compiled Graph + Stateless Agents for Multi-Actor

**Status:** Proposed <br>
**Date:** 2026-05-15 <br>
**Deciders:** vanillasky <br>

## Context

ADR-001 established LangGraph `StateGraph[AgentState]` as the orchestrator with four agents (Curriculum, Skill, Action, Critic) wired as module-level singletons in `app/agents/graph.py`. The compiled graph is invoked per perception frame from the WebSocket handler.

ADR-011 introduced the multi-actor schema: `actors` table, `actor_id NOT NULL` on `memories` and `skills`, and a per-`(actor_id, task_name)` unique key for the skill library. Its *Python contracts* section sketched the runtime side as follows:

> `app/agents/graph.py` — Constructs **one set of agents per actor** (the existing module-level singletons become a factory keyed by `actor_id`).

When we sat down to implement that paragraph, three problems surfaced that ADR-011 did not anticipate:

1. **The four agents are mostly stateless already.** `ActionAgent` and `CriticAgent` carry no per-actor data; `SkillAgent` only carries a reference to the shared memory store. The single offender is `CurriculumAgent.recent_history`, an in-process list of recent task outcomes. A per-actor *factory* exists primarily to give that one list a per-actor home — heavyweight machinery for a small variable.
2. **The compiled `StateGraph` is a pure function.** `workflow.compile()` returns a runnable that depends only on its input. There is no semantic gain from N copies of the same compiled graph; they would all dispatch to the same node functions, which all close over the same module-level agents and resources. The factory pattern would just duplicate identical structure in RAM per actor.
3. **`AgentState` already exists as the per-call container.** It threads `task`, `plan`, `retry_count`, `skill_guide`, etc. through every node. Adding `actor_id` and moving `recent_history` into it costs two fields and aligns with the abstraction that's already there. Building a parallel "per-actor factory" duplicates what `AgentState` is for.

In short: ADR-011's "factory keyed by `actor_id`" is correctly motivated (per-actor data must not leak) but mis-shaped (the leak is `recent_history`, not the agents themselves). This ADR proposes the smaller fix and supersedes that one paragraph in ADR-011.

## Decision

We adopt **one compiled graph, shared across all actors; agents are stateless services; per-actor data flows through `AgentState`.**

### Concretely

```
build_graph() ──compile──► graph_app   (module-level, built once at import)
                              │
                              ▼
            await graph_app.ainvoke({**state, "actor_id": X})
                              │
       ┌──────────────────────┴──────────────────────┐
       │ Each node reads state["actor_id"] and       │
       │ state["recent_history"]; passes actor_id    │
       │ into memory_store calls; returns partial    │
       │ state updates (including new recent_history)│
       └─────────────────────────────────────────────┘
```

### `AgentState` gains two fields

```python
class AgentState(TypedDict):
    perception: Perception
    context: str

    actor_id: int                       # NEW — required on every invocation
    
    task: str
    skill_guide: str
    plan: list[AgentAction]
    critique: CriticOutput | None
    
    recent_history: list[dict]          # NEW — was CurriculumAgent.recent_history
    retry_count: int
```

### The four agent classes become stateless services

| Class | Before | After |
|---|---|---|
| `CurriculumAgent` | held `self.recent_history`; `add_history()` mutated it | `propose_next_task(context, *, actor_id, recent_history)` — history passed in, returned via state updates from `learning_node` / `failure_node` |
| `SkillAgent` | `retrieve_skill(task)`; `learn_new_skill(...)` | `retrieve_skill(task, *, actor_id)`; `learn_new_skill(..., *, actor_id)` |
| `ActionAgent` | already stateless | unchanged |
| `CriticAgent` | already stateless | unchanged |

`curriculum_agent.add_history(...)` is deleted. `learning_node` and `failure_node` append the outcome and return `{"recent_history": history[-10:]}` so LangGraph's state merge persists it for the next frame.

### Memory store API gains `actor_id`

`BaseMemoryStore.fetch_similar`, `fetch_recent`, `fetch_similar_skills`, and `save_skill` accept `actor_id: int | None = None` as a keyword-only argument. `PostgresMemoryStore` applies the filter when set. ADR-011 will tighten the parameter from optional to required once all callers are migrated.

### WebSocket handler maps `client_id` → `actor_id`

`routes.py` resolves `actor_id` at connect time from the WebSocket path parameter (ADR-011 Open Question 1, default answer (a): 1:1 mapping). It writes `actor_id` into `session_state`, threads it into every `initial_state` passed to `graph_app.ainvoke(...)`, and rolls `recent_history` back from each `final_state` so the next frame sees the updated list.

### Module-level singletons stay — but only for *shared* resources

`graph.py` keeps module-level singletons for things that legitimately have no per-actor variant: the LLM client, the tool registry, the memory store, and the four agent instances (now stateless). These are constructed once at import. The compiled `graph_app = build_graph()` is also module-level.

## Consequences

**Positive:**
- **One source of truth for per-actor data.** Anything that varies by actor lives in `AgentState`. Anything that doesn't lives at module level. No third bucket.
- **N actors cost O(1) memory in graph structure** — only `AgentState` payloads scale with concurrency, and those are already per-call.
- **Tests are simpler.** Agents have no setup-time actor binding; the test passes `actor_id=1` like any other kwarg. Mock `BaseMemoryStore` instances accept `actor_id` without code change because they're `MagicMock(spec=...)`.
- **Easier to persist sessions.** With `recent_history` in state, dumping/restoring an `AgentState` to Redis (CLAUDE.md mentions this is scaffolded) round-trips an entire actor's working context. Previously `recent_history` would have been lost on reconnect.
- **Matches what `AgentState` was designed to do.** ADR-001 already said "no hidden state passed through closures." `recent_history` on a singleton agent was a leftover violation of that principle; this ADR fixes it.

**Negative / trade-offs:**
- **Every memory call must pass `actor_id`.** A node that forgets is silently wrong — it'll see other actors' data. Mitigated partly by `actor_id` being a keyword-only arg (less likely to drift positionally) and by the DB-level FK constraint surfacing it on writes, but read-side mistakes are still possible. ADR-011's *Negative* point about composite uniqueness applies here too.
- **Single shared `_HISTORY_WINDOW`.** All actors trim to the same length (10). Fine for the chef/waiter pair we're shipping; revisit if per-actor history depth becomes a tuning knob.
- **`AgentState` grew two fields.** LangGraph state merging is shallow per ADR-001 — node returns replace lists wholesale. Nodes that update `recent_history` must compute the *full new list* and return it, not push to the old one. Codified by always doing `history = state.get("recent_history", []) + [...]; return {"recent_history": history[-_HISTORY_WINDOW:]}`.
- **Supersedes one paragraph of ADR-011.** The `graph.py` row in ADR-011's *Python contracts* table no longer matches the implementation. ADR-011 stays accepted for the schema decision; this ADR amends the runtime-side wiring only.

## Alternatives Considered

### A. Per-actor compiled graphs (ADR-011's original proposal)
**Rejected.** N copies of an identical compiled graph for a one-list state delta is the wrong tool. The agents would still close over the same module-level resources, so isolation isn't really improved — it's only the `recent_history` field that needs separating, and a TypedDict field does that for free.

### B. Per-actor agent *instances* but one shared compiled graph (factory-of-agents pattern)
**Rejected.** Splits ownership: the graph would have to look up `agents[actor_id]` inside each node and route accordingly. Now we have *two* per-actor scopes (the agent objects and the AgentState) and they have to stay in sync. Strictly worse than one.

### C. Keep `recent_history` on `CurriculumAgent`, but key it by `actor_id` internally (`self._history_by_actor[actor_id]`)
**Rejected.** Hidden mutable state in a singleton — exactly the pattern ADR-001 ruled out. Also makes the agent harder to test (state leaks across tests) and harder to persist (no clean serialization point).

### D. Move `recent_history` to a DB table instead of `AgentState`
**Deferred.** Durable across restarts and would let the Critic query history too. But the list is bounded (10 items), the per-frame round-trip is cheap, and CLAUDE.md notes Redis session persistence is the more general mechanism scaffolded for this. Revisit if `recent_history` grows beyond a window or if cross-frame queries on it become useful.

## Open Questions

1. **Required vs. optional `actor_id` in `BaseMemoryStore`.** Today it's `int | None` to keep ADR-011's implementation step independent. When the last legacy caller is migrated (probably in the ADR-011 cleanup PR), tighten to `int`. Tracked by ADR-011.
2. **Actor bootstrap on first WebSocket connect.** `actor_id` resolves from `client_id`, but if that row doesn't exist in `actors` the first write fails with a FK violation. ADR-011 Open Question 1 covers the policy choice (auto-create vs refuse); implementing it is the natural next PR after this one lands.
3. **Stateless agents and concurrent invocations.** With one `CurriculumAgent` shared across all actors, two concurrent `propose_next_task` calls overlap. The agent now holds no mutable state, so this is safe — but the underlying LLM client (`openai_llm`) must also be safe under concurrent `generate_response` calls. `langchain_openai.ChatOpenAI` is documented as concurrency-safe; if we swap providers (Ollama, etc.) we re-check.
