# ADR-010: Three-Phase Curriculum Task Decomposition

**Status:** Accepted <br>
**Date:** 2026-03-05 <br>
**Deciders:** vanillasky <br>

## Context

The end goal of the restaurant simulation is to assemble a complete burger on a plate. This is a long-horizon task with roughly 15–25 individual primitive actions (move, pick up, process, put down) across 7–8 ingredient types and multiple kitchen stations.

Giving the LLM a single top-level goal ("assemble a burger") and expecting it to plan the full sequence in one shot fails for several reasons:

1. **Context length**: A complete 25-step plan for all ingredients exceeds reliable single-shot LLM planning quality.
2. **Physics sensitivity**: Unity interaction requires exact sequencing — the agent must be adjacent before pickup, must process before plating, must place ingredients in the exact stack order dictated by `AssemblyView.next_expected`. Any deviation causes failure.
3. **State dependency**: Later steps (stacking) depend on earlier steps (processing). If CurriculumAgent proposes a STACK task before the ingredient is processed, the entire plan is invalid before ActionAgent even starts.
4. **Recovery granularity**: If a 25-step plan fails at step 12, the Critic has no way to identify which of the 12 prior steps caused the issue. Smaller tasks make retry scopes smaller.

## Decision

`CurriculumAgent` decomposes burger assembly into a **three-phase pipeline** of short, concrete sub-tasks. Each sub-task is scoped to 3–6 primitive actions and has a clear observable success condition.

### Phase 1: PLATE_SETUP (one-time)

**Trigger**: `assembly.plate_location == ""` (no plate in the world yet)

**Task format**: `"Set up the assembly plate on Preparation1"`

**Action pipeline**:
1. `move_to PlateBoard`
2. `pickup PLATE`
3. `move_to Preparation1`
4. `put_down PLATE`

**Success condition (Critic)**: A plate exists at the designated preparation table with no stacked ingredients.

Once PLATE_SETUP succeeds, the assembly surface is established and the plate location is tracked by Unity's `AssemblyView`.

### Phase 2: PREP (per ingredient, parallelizable in principle)

**Trigger**: `assembly.next_expected` is not `None` (burger assembly has started or is ready to start) AND the required processed ingredient is not yet READY in `[C] KITCHEN STATE`

**Task format**: `"Prepare {ProcessedIngredient} and place it on a Preparation table"`

Examples:
- `"Prepare CookedMeat and place it on a Preparation table"`
- `"Prepare TomatoSlice and place it on a Preparation table"`

**Action pipeline** (example for TomatoSlice):
1. `move_to TomatoBox`
2. `pickup Tomato`
3. `move_to CutBoard_01`
4. `chop Tomato` → becomes `TomatoSlice`
5. `pickup TomatoSlice`
6. `move_to Preparation2`
7. `put_down TomatoSlice`

**Success condition (Critic)**: The processed ingredient is on a preparation table that is not the assembly surface.

CurriculumAgent reads `[C] KITCHEN STATE` to determine which ingredients are already READY and avoids re-prepping them.

### Phase 3: STACK (per layer, strictly ordered)

**Trigger**: The required processed ingredient is READY AND `assembly.next_expected` matches it

**Task format**: `"Stack {ProcessedIngredient} onto the plate at {plate_location}"`

Examples:
- `"Stack BreadSlice onto the plate at Preparation1"`
- `"Stack CookedMeat onto the plate at Preparation1"`

**Action pipeline**:
1. `move_to {source table where ingredient is parked}`
2. `pickup {ProcessedIngredient}`
3. `move_to {plate_location}`
4. `put_down {ProcessedIngredient}`

**Success condition (Critic)**: `assembly.stack` length has increased by one AND the new top layer matches `{ProcessedIngredient}`. The Critic trusts Unity's `AssemblyView` as authoritative — it does not try to infer stack state from object positions.

### Curriculum Decision Logic

```
Read [C] KITCHEN STATE (READY ingredients)
Read [F] ASSEMBLY (plate_location, next_expected, stack, is_done)

if plate_location == "":
    → PLATE_SETUP

elif next_expected not in READY:
    → PREP(next_expected)

else:
    → STACK(next_expected, plate_location)
```

The Curriculum agent does not track which preparation tables are used or which ingredients are ready — it reads this directly from the perception context produced by `PerceptionRenderer`. Separation of concerns: `PerceptionRenderer` computes state; `CurriculumAgent` reads it.

### Forbidden Task Forms

The curriculum prompt explicitly forbids:
- Vague tasks: `"Explore the kitchen"`, `"Look around"`, `"Wait for instructions"`
- Multi-ingredient tasks: `"Prepare all vegetables"` (too wide for single-shot planning)
- Tasks contradicting [F]: `"Stack CookedMeat"` when `next_expected == "BreadSlice"`

The prompt provides concrete examples of all three phases with exact ingredient and table names drawn from [LAYOUT].

## Consequences

**Positive:**
- Each sub-task has 3–6 actions — within reliable single-shot LLM planning range.
- Sub-task success is observable and verifiable by the Critic within one perception frame.
- Retry scope is small: if stacking fails, only the STACK task retries, not the entire burger pipeline.
- Phase order (PLATE_SETUP → PREP → STACK) ensures ingredient dependencies are always satisfied before plating.

**Negative / trade-offs:**
- The three-phase split is hard-coded to the burger recipe. A new dish type (e.g., pizza) requires new phase logic in the curriculum prompt.
- PREP and STACK are strictly sequential per ingredient — no parallelism (the game is single-agent).
- If `CurriculumAgent` names a PREP task inconsistently (`"Prepare TomatoSlice"` vs `"Slice the Tomato"`), the skill library will not find a warm-start SOP for it.

## Alternatives Considered

### A. Single top-level goal ("assemble a burger")
**Rejected.** In early testing, single-shot full planning produced sequences where raw ingredients were plated directly, stacking order was wrong, and the plan exceeded the LLM's reliable planning horizon.

### B. Dynamic hierarchical planning (plan the plan)
**Considered.** A meta-planner could generate the three-phase structure dynamically from the burger recipe. Rejected because the recipe is fixed in this simulation — dynamic planning adds complexity without benefit. If the game added multiple recipes, this would be worth revisiting.

### C. Reactive one-step planning ("what to do next?")
**Considered.** Ask the LLM for only the single next primitive action. Rejected because the LLM needs to see the full pipeline (move → pickup → move → put_down) to avoid plans that terminate mid-task (e.g., "just move to the TomatoBox" with no follow-through).
