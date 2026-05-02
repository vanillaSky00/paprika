# ADR-002: Voyager-Inspired Critic–Retry–Learn Feedback Loop

**Status:** Accepted <br>
**Date:** 2026-02-20 <br>
**Deciders:** vanillasky <br>

## Context

MineCraft's Voyager paper (Wang et al., 2023) demonstrated that an LLM agent can accumulate a growing skill library through an outer loop of: **propose task → execute → verify → generalize into skill → repeat**. The key insight is that verified successes become reusable skills that bootstrap future planning, while failures feed corrective context back into the planning step.

Paprika faces the same challenge in a restaurant sim: the action space is large (pick up, chop, cook, assemble), ingredient combinations vary, and the LLM alone cannot reason perfectly about Unity's physics engine quirks (distance thresholds, stacking order). A single-shot planner fails too often.

We need:
1. A way to give the planner feedback from the real execution environment (Unity), not just LLM reasoning.
2. A retry mechanism that uses that feedback rather than re-generating blindly.
3. A way to accumulate verified task procedures so future identical tasks don't require re-planning from scratch.

## Decision

We implement a **three-phase outer loop** mirroring Voyager's architecture:

### Phase 1 — Action (Plan Generation)

`ActionAgent` generates a full ordered pipeline as a JSON list of `AgentAction` objects:

```json
[
  {"thought_trace": "need to reach TomatoBox first", "function": "move_to", "args": {"id": "TomatoBox"}},
  {"thought_trace": "pick up the tomato", "function": "pickup", "args": {"id": "Tomato"}},
  {"thought_trace": "move to cutting board", "function": "move_to", "args": {"id": "CutBoard_01"}},
  {"thought_trace": "chop into slices", "function": "chop", "args": {"id": "Tomato"}}
]
```

The plan is returned to Unity via WebSocket. **The backend does not simulate execution** — Unity is the authoritative physics engine.

### Phase 2 — Critic (Execution Verification)

On the next perception frame (after Unity executes), `CriticAgent` receives:
- The original `task` string
- The full updated `Perception` (world state post-execution)
- The `execution_trace` (each step's success/failure + message from Unity)

Critic outputs:
```python
class CriticOutput:
    success: bool
    reasoning: str  # why it judged success or failure
    feedback: str   # actionable correction, e.g., "Move closer before pickup"
```

**Retry path (failure, retry_count ≤ 2):** `ActionAgent` is called again with `last_plan` and `critique` injected into its context, allowing targeted correction rather than full re-generation.

**Escalation path (failure, retry_count > 2):** `CurriculumAgent` re-plans the task entirely, possibly breaking it into smaller sub-tasks.

### Phase 3 — Learning (Skill Generalization)

On success, `SkillAgent.learn_new_skill()` is called:
- Input: task name + raw execution trace (concrete IDs, coordinates)
- Output: Generalized SOP (Standard Operating Procedure) stored in the `skills` table

```
Raw: "move_to TomatoBox_01 at x:12.5 y:0 z:3.2 → pickup Tomato_3 → move_to CutBoard_01 → chop Tomato_3"
SOP: "1. Go to TomatoBox.\n2. Pick up the Tomato.\n3. Move to the CutBoard.\n4. Chop the Tomato."
```

### Warm-Start via Skill Retrieval

`SkillAgent` performs vector similarity search over the `skills` table on each new task:

```python
similar = await skill_repo.fetch_similar_skills(task, limit=1)
skill_guide = similar[0].steps_text if similar else ""
```

If a guide is found, it is injected into `ActionAgent`'s context:
> *"I have done this task before. Here is the guide: [steps]. Follow if it matches your current situation."*

This gives the planner a warm start without forcing exact reuse (the caveat "if it matches" lets it adapt).

## Consequences

**Positive:**
- Execution feedback comes from Unity's real physics, not LLM simulation — eliminates hallucinated success.
- Retry context (last_plan + critique) produces targeted corrections, not random re-tries.
- Skill library grows with each successful task; later runs plan faster.
- Generalization step prevents overfitting to specific object IDs or coordinates.

**Negative / trade-offs:**
- One planning cycle now spans **two WebSocket messages** (plan → execute → perceive → critic), adding one round-trip latency per task attempt.
- Skill retrieval is a vector search on every new task, adding DB latency.
- Generalization quality depends on the LLM; poorly generalized SOPs degrade warm-start quality.
- `skills` table uses `UNIQUE(task_name)` — if curriculum names the same task differently each time, the library never grows.

## Alternatives Considered

### A. Single-shot planner, no retry
**Rejected.** Unity physics failures (distance, occlusion) are frequent enough that a non-retrying planner fails too often to be useful.

### B. Re-generate plan from scratch on failure
**Rejected.** The LLM has no memory of what it just tried; it is likely to repeat the same failure without the `last_plan + critique` context.

### C. Hardcode task scripts (no LLM planning)
**Rejected.** Hardcoded scripts cannot adapt to dynamic kitchen layout (ingredient positions, table assignment) and defeat the purpose of an agentic system.

### D. Use Voyager's exact JS code generation
**Considered but not adopted.** Voyager generates executable Mineflayer JS code. Paprika's game client is Unity (C#), not a Node.js bot, so code generation would require a Unity scripting bridge. Structured JSON actions are simpler and less error-prone.
