# ADR-003: Affordance-Driven Perception Context (SayCan-Inspired)

**Status:** Accepted <br>
**Date:** 2026-03-01 <br>
**Deciders:** vanillasky <br>

## Context

Robotics research (Ahn et al., *SayCan*, 2022) showed that grounding LLM plans in **physical affordances** — what actions are actually possible given the current world state — dramatically reduces physically-impossible outputs. Without grounding, an LLM planner freely generates plans like "pick up the cooked meat" when the meat is still raw, or "chop the bread" when the bread is already sliced.

The naive approach is to pass the raw Unity perception JSON to the LLM and let it reason. This fails in practice for several reasons:

1. **Parsing burden**: The LLM must re-derive affordances from raw state fields (`is_cooked: false`, `is_on_board: true`) on every call. It makes mistakes.
2. **Inconsistent naming**: Unity's perception can report the same object with different naming conventions across frames (race conditions, prefab variant names). The LLM is confused by `TomatoSlice` vs `Tomato(Clone)_Sliced`.
3. **Action constraint violations**: Without explicit physical rules, the LLM stacks ingredients before they are processed, picks up items from wrong stations, or misses the mandatory raw → processed transition.
4. **No urgency signaling**: If an item is already on the CutBoard waiting to be chopped, the LLM may decide to do something else first. There is no way to signal "this is urgent — do it now" in raw JSON.

## Decision

We convert raw Unity perception into a **structured, imperative affordance context string** before passing it to any LLM agent. This is done by `PerceptionRenderer` in [context/view.py](../../backend/app/context/view.py).

The context is divided into six labeled blocks, each serving a distinct cognitive purpose:

```
[LAYOUT]          Canonical object IDs (static reference map)
[A] SELF STATE    Held item: empty / raw ingredient / processed ingredient
[B] AFFORDANCES   Per-object: what CAN and MUST be done right now
[C] KITCHEN STATE Supply check — which ingredients are READY vs still raw
[D] SHORT-TERM    Recent action trace (last 4 steps, success/fail)
[E] FAILURE CTX   Retry count + targeted correction hints
[F] ASSEMBLY      Unity-authoritative plate state, next expected layer
```

### Block [B]: The Core Affordance Layer

Rather than listing object states, each visible object is rendered with its **actionable implication**:

| Object situation | Affordance text injected |
|-----------------|--------------------------|
| CookedMeat on Oven | `"CookedMeat is ready — PICK IT UP now. Do not leave it in the Oven."` |
| Tomato on CutBoard | `"A Tomato is on the CutBoard. You MUST chop it immediately — do not leave it raw."` |
| Raw Bread in Container | `"RAW BREAD ready to pick up. It MUST be chopped on CutBoard before plating."` |
| Empty Oven | `"Oven is free. Place raw Meatball here to cook."` |
| Plate on Prep table | `"This table has a plate — use put_down here to stack an ingredient."` |

The `_affordance_for()` method in `PerceptionRenderer` contains all of these rules as explicit Python logic, not LLM inference. The LLM reads the result; it does not derive it.

### Unified Context Across All Agents

The same `build_perception_context(perception)` output is injected into the system prompt of **every agent** — Curriculum, Skill, Action, and Critic. This prevents agents from disagreeing about kitchen state:

- Curriculum reads [C] KITCHEN and [F] ASSEMBLY to choose the next task.
- Action reads [A] SELF and [B] AFFORDANCES to plan the next pipeline.
- Critic reads all blocks to judge whether the task succeeded.

### KitchenRegistry: Domain Knowledge in Code, Not LLM Memory

Processing rules, station IDs, and ingredient types are hard-coded in `KitchenRegistry`:

```python
PROCESSING_RULES = {
    "MEATBALL": ("Oven",     "cook"),
    "TOMATO":   ("CutBoard", "chop"),
    "ONION":    ("CutBoard", "chop"),
    "LETTUCE":  ("CutBoard", "chop"),
    "CHEESE":   ("CutBoard", "chop"),
    "BREAD":    ("CutBoard", "chop"),
}

HAMBURGER_STACK = ["BreadSlice", "CookedMeat", "TomatoSlice",
                   "OnionSlice", "LettuceSlice", "CheeseSlice", "BreadSlice"]
```

These are not in a prompt. They drive the Python affordance logic, which then produces the imperative text the LLM reads. If a rule changes (e.g., bread should be toasted, not chopped), we update one Python constant — not every prompt template.

## Consequences

**Positive:**
- LLM planning accuracy improves significantly; impossible actions ("chop an already-sliced tomato") are eliminated.
- Urgency signals ("MUST chop immediately") prevent the LLM from deferring processing steps.
- Canonical ID list in [LAYOUT] prevents Unity naming inconsistencies from reaching the LLM.
- Domain rules live in Python (testable, refactorable), not buried in prompt text.

**Negative / trade-offs:**
- `PerceptionRenderer` is large (~2100 lines) and requires update whenever the Unity game state schema changes.
- Affordance logic is hand-coded per object type; adding a new ingredient requires adding Python cases, not just a Unity prefab.
- The context string can be long (~600–900 tokens per frame), contributing to LLM cost.

## Alternatives Considered

### A. Pass raw JSON to the LLM
**Rejected.** In early prototypes, the LLM frequently hallucinated impossible plans (stacking raw ingredients, chopping already-processed items). The failure rate dropped substantially after introducing structured affordance text.

### B. Per-agent perception rendering
**Rejected.** If Curriculum and Critic render perception independently with different logic, they can disagree about kitchen state (Curriculum thinks tomato is raw; Critic thinks it's sliced). Unified rendering eliminates this class of bug.

### C. Use function-calling / tool outputs to query state
**Considered.** The LLM could call `query_object_state(id)` tools instead of reading a pre-rendered block. This adds round-trips and requires the LLM to know which objects to query. Pre-rendering is simpler and cheaper.
