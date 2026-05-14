# Diagram: Unity Perception → Backend → Action Round Trip

This is the single end-to-end path one frame takes through the backend. It is
the diagram to read first when learning the codebase.

**Transport:** WebSocket at `ws://host:8000/api/ws/agent/{client_id}`
([app/main.py](../../backend/app/main.py),
[app/api/routes.py:65](../../backend/app/api/routes.py#L65)). One connection
per Unity client; session state is held in-process for the connection's
lifetime.

**Graph entry point:** `entry_router` in
[app/agents/graph.py:149](../../backend/app/agents/graph.py#L149) decides
whether this frame starts a new task (`curriculum`) or evaluates the previous
plan (`critic`).

---

## Sequence (high-level: one Unity frame)

```mermaid
sequenceDiagram
    autonumber
    participant U as Unity (C# WebSocket)
    participant WS as routes.py<br/>websocket_endpoint
    participant PF as _process_frame
    participant CTX as context.view<br/>build_perception_context
    participant G as graph_app<br/>(LangGraph)
    participant DB as Postgres<br/>(pgvector)
    participant LLM as OpenAI<br/>(LangChain)

    U->>WS: receive_json() — Perception payload
    WS->>WS: validate via Pydantic Perception
    Note over WS: ValidationError ⇒<br/>InvalidPerceptionError ⇒<br/>JSON error frame (loop continues)

    WS->>PF: _process_frame(data, session_state, client_id)
    PF->>CTX: build_perception_context(perception, retry, task)
    CTX-->>PF: "[A]…[F]" affordance block (str)

    PF->>G: await graph_app.ainvoke(initial_state)

    Note over G: state carries:<br/>perception, context, task,<br/>plan, critique, skill_guide,<br/>retry_count

    alt task is empty or "Decide Next Task" (new task)
        G->>G: entry_router → curriculum
        G->>DB: memory_store.fetch_similar(query=context, limit=10)
        DB-->>G: list[MemoryDTO]
        G->>LLM: curriculum prompt
        LLM-->>G: CurriculumOutput(task, reasoning, difficulty)
        G->>DB: memory_store.fetch_similar_skills(query="How to "+task, limit=1)
        DB-->>G: list[SkillDTO]
        G->>G: skill_node sets state.skill_guide
        G->>LLM: action prompt (task + skill_guide + context)
        LLM-->>G: list[AgentAction] (the plan)
        G->>G: END (graph halts at action)
    else task is set (we are judging the prior plan)
        G->>G: entry_router → critic
        G->>LLM: critic prompt (task vs. current perception)
        LLM-->>G: CriticOutput(success, reasoning, feedback)
        alt success
            G->>LLM: skill prompt (summarise action history → SOP)
            LLM-->>G: SkillDTO
            G->>DB: memory_store.save_skill(skill) (upsert)
            G->>G: learning → curriculum → skill → action → END
        else retry_count ≤ 2 (retry)
            G->>LLM: action prompt (with critic feedback + last plan)
            LLM-->>G: new list[AgentAction]
            G->>G: END
        else retries exhausted
            G->>G: failure_node clears plan/retry/critique
            G->>G: failure → curriculum → skill → action → END
        end
    end

    G-->>PF: final_state(task, plan, retry_count, skill_guide)
    PF->>PF: update session_state in-place
    PF->>PF: _serialize_plan → list[dict]
    PF-->>WS: {client_id, task, plan: [AgentAction.model_dump(), …]}
    WS->>U: send_json(response)

    Note over U: Unity executes plan steps,<br/>then sends the next perception frame
```

### What each numbered step proves

- **2 — Pydantic validation at the boundary.** Schema drift in Unity is caught
  here, before any agent runs. The handler converts `ValidationError` to
  `InvalidPerceptionError` ([routes.py:130](../../backend/app/api/routes.py#L130))
  so the loop has one error mode to translate, not two.
- **5 — Context built once.** `build_perception_context` runs in the handler
  (not inside an agent node). Every agent reads `state['context']` rather than
  the raw `Perception`. This is the rule that lets Unity's perception shape
  evolve without touching every prompt template — only
  [context/view.py](../../backend/app/context/view.py) needs to change.
- **9 / 18 — LangGraph halts at `action`.** The `END` edge after `action_node`
  is intentional ([graph.py:201](../../backend/app/agents/graph.py#L201)). It
  gives the plan back to Unity, which executes it physically; the next
  perception frame re-enters via `critic` (the entry router sees a non-empty
  `task`). See ADR-005.
- **15 — Skill retrieval is conditional.** It only runs on the
  curriculum-then-action branch. On retry or failure-recovery the agent uses
  the skill_guide already in `session_state` from the previous turn.
- **24 — Session state is mutable across frames.** The dict at
  [routes.py:73](../../backend/app/api/routes.py#L73) is rebound each call
  with the keys the graph cares about. Disconnect = state gone (ADR-004).

---

## The same flow as a control-flow diagram

For readers who prefer the graph view of LangGraph itself:

```mermaid
flowchart TD
    Start([WS frame arrives]) --> Validate{Pydantic<br/>valid?}
    Validate -- no --> Err1[InvalidPerceptionError<br/>→ error JSON]
    Validate -- yes --> Build[build_perception_context]
    Build --> Invoke[graph_app.ainvoke]
    Invoke --> Entry{entry_router<br/>state.task?}

    Entry -- empty / 'Decide Next Task' --> Curr[curriculum_node]
    Curr --> Skill[skill_node]
    Skill --> Action[action_node]

    Entry -- set --> Critic[critic_node]
    Critic --> Decide{success?<br/>retry_count?}
    Decide -- success --> Learn[learning_node]
    Learn --> Curr
    Decide -- fail & retry ≤ 2 --> Action
    Decide -- fail & exhausted --> Fail[failure_node]
    Fail --> Curr

    Action --> End([END — return plan])
    End --> Send[serialise plan<br/>send_json to Unity]
    Send --> Start
```

The arrow that **loops** in this diagram (`Curr → Skill → Action → END → next
frame → Critic → … → Curr`) is the Voyager-style feedback loop (ADR-002). The
arrow that **ends a Python invocation** is `Action → END` — that boundary
exists so Unity can physically execute the plan before the next critic run
(ADR-005).

---

## Concurrency: many Unity clients in parallel

```mermaid
sequenceDiagram
    participant U1 as Unity #1
    participant U2 as Unity #2
    participant L as Uvicorn<br/>event loop
    participant H1 as websocket_endpoint<br/>(coroutine #1)
    participant H2 as websocket_endpoint<br/>(coroutine #2)

    U1->>L: WS upgrade /api/ws/agent/u1
    L->>H1: spawn coroutine, await receive_json()
    U2->>L: WS upgrade /api/ws/agent/u2
    L->>H2: spawn coroutine, await receive_json()

    U1->>L: frame
    L->>H1: resume
    H1->>L: await graph_app.ainvoke(...)
    Note over L: control returns —<br/>loop is free

    U2->>L: frame
    L->>H2: resume
    H2->>L: await graph_app.ainvoke(...)
    Note over L: now BOTH ainvokes<br/>are pending; their<br/>OpenAI/Postgres awaits<br/>interleave on the loop

    L-->>H1: ainvoke resolves
    H1->>U1: send_json(plan)
    L-->>H2: ainvoke resolves
    H2->>U2: send_json(plan)
```

Each WebSocket connection has its own `session_state` dict in the handler
scope ([routes.py:73](../../backend/app/api/routes.py#L73)). The agents
themselves are module-level singletons in
[graph.py:32-50](../../backend/app/agents/graph.py#L32-L50), but they are
stateless from the request side — all per-call data lives in the
`AgentState` TypedDict passed through `ainvoke`. That is what makes parallel
ainvokes safe.

(One caveat: `CurriculumAgent.recent_history` is an in-process list on the
singleton, so today it is shared across all clients. After ADR-011 lands, the
agent factory is keyed by `actor_id` and each actor's history is its own
list.)
