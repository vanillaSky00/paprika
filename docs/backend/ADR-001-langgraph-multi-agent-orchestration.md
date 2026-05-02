# ADR-001: LangGraph for Multi-Agent Orchestration

**Status:** Accepted <br>
**Date:** 2026-02-15 <br>
**Deciders:** vanillasky <br>

## Context

The backend needs to coordinate four distinct reasoning agents — Curriculum, Skill, Action, and Critic — where the control flow between them depends on runtime state (did the last plan succeed? how many retries remain? is this a new task or a retry?).

Options considered:

1. **Sequential LangChain chains** — simple but no branching; every agent always runs.
2. **Custom `if/else` dispatcher** — full control but no graph visualization, no async node scheduling, and state threading is manual.
3. **LangGraph `StateGraph`** — graph of nodes with typed shared state and conditional edges; designed exactly for multi-agent workflows with feedback loops.
4. **Separate microservices per agent** — too much operational overhead for an academic project; adds latency per hop.

The core challenge is that the Critic's output drives the next node: success → Learning, failure → Action retry, too many retries → Curriculum re-plan. This conditional branching on mutable state is awkward to express cleanly without a graph abstraction.

## Decision

We adopt **LangGraph `StateGraph[AgentState]`** as the orchestration layer.

```
entry_router()
     │
     ├─ new task ──► [CURRICULUM] ──► [SKILL] ──► [ACTION] ──► END
     │                                                            │
     └─ next perception ──► [CRITIC]                             │ (Unity executes)
                                │                                │
                      ┌─ success ──► [LEARNING] ──► END         │
                      │                                          │
                      ├─ failure (retry < 3) ──► [ACTION] ◄─────┘
                      │
                      └─ failure (retry ≥ 3) ──► [CURRICULUM]
```

**`AgentState`** is a typed `TypedDict` threaded through every node:

```python
class AgentState(TypedDict):
    perception: Perception
    task: str
    plan: list[AgentAction]
    skill_guide: str
    last_plan: dict
    critique: str
    retry_count: int
    success: bool
    reasoning: str
    feedback: str
```

Each node receives the full state and returns a partial update. LangGraph merges the update into the shared state before routing to the next node.

**Conditional edges** implement the retry/escalation logic in `decide_next_node()`:

```python
def decide_next_node(state: AgentState) -> str:
    if state["success"]:
        return "learning"
    if state["retry_count"] <= MAX_RETRIES:
        return "action"
    return "curriculum"
```

The compiled graph is a single `app = graph.compile()` singleton, invoked per WebSocket frame via `app.ainvoke(initial_state)`.

## Consequences

**Positive:**
- Conditional routing expressed as named edge functions — readable and testable in isolation.
- `AgentState` is a single source of truth; no hidden state passed through closures.
- LangGraph's async execution model matches FastAPI's async WebSocket handler without thread-pool hacks.
- LangSmith integration (optional, gated by `LANGCHAIN_TRACING_V2`) gives free graph visualization for debugging.

**Negative / trade-offs:**
- LangGraph version pinning is critical; the API changes between minor versions.
- State merging is shallow — nested structures (e.g., `plan: list[AgentAction]`) are replaced wholesale, not merged.
- Adding a new agent requires touching the graph definition, state type, and edge logic simultaneously.

## Alternatives Considered

### A. Plain sequential chain
**Rejected.** No branching means Critic feedback can't route back to Action; every node always runs even if the task is done.

### B. Custom Python dispatcher
**Rejected.** Equivalent complexity to LangGraph but without typed state, async-native scheduling, or built-in observability hooks.

### C. Separate microservices per agent
**Rejected.** Adds network latency between agents and requires a message bus for state passing. The four agents share a large `AgentState`; serializing it over the wire on every hop is wasteful.
