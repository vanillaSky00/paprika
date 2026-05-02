# ADR-005: Action→END Graph Boundary (Backend Plans, Unity Executes)

**Status:** Accepted <br>
**Date:** 2026-02-18 <br>
**Deciders:** vanillasky <br>

## Context

In the LangGraph orchestration loop, once `ActionAgent` produces a plan, the backend faces a design choice: should it simulate plan execution internally and continue the graph, or should it stop, return the plan to Unity, and wait for real-world feedback?

If the backend simulates execution:
- The graph could continue to the Critic immediately, without waiting for Unity.
- Simulation would require maintaining a game-state model in Python that mirrors Unity's physics engine.
- Simulation errors (wrong distances, stacking physics, collision rules) would produce critic judgments based on fiction, not reality.

If the backend exits after Action:
- Unity is the sole execution engine.
- The next perception frame carries the real post-execution state.
- The graph re-enters at the Critic node only with ground-truth world state.

The kitchen simulation has non-trivial physics: objects have exact position thresholds for interaction (`move_to` must bring the agent within N units), stacking order matters for plate assembly, and Unity prefab variants can report different state field names across frames. No Python model can faithfully reproduce this.

## Decision

**The LangGraph graph exits to `END` immediately after `ActionAgent` produces a plan.** The plan is serialized to JSON and sent to Unity via WebSocket. The backend does not simulate or continue the graph until the next perception frame arrives.

```
[ACTION] ──► END   ← graph exits here
                      JSON plan sent to Unity
                      Unity executes all steps
                      Unity sends next Perception
[entry_router] reads session state → routes to [CRITIC]
[CRITIC] evaluates real post-execution world state
```

**Session state bridges the two graph invocations:**

```python
# After ACTION node exits:
session["task"]        = state["task"]
session["plan"]        = state["plan"]   # saved for critic context
session["retry_count"] = state["retry_count"]

# On next perception (critic invocation):
initial_state = {
    "perception": new_perception,
    "task": session["task"],
    "last_plan": session["plan"],
    "retry_count": session["retry_count"],
    ...
}
```

The `entry_router()` function reads `session["task"]` to decide whether to start a fresh Curriculum cycle (no current task) or a Critic cycle (task in progress):

```python
def entry_router(session: dict) -> str:
    return "critic" if session.get("task") else "curriculum"
```

## Consequences

**Positive:**
- Critic judgments are always based on Unity's real world state, never on a simulated approximation.
- The backend has zero physics model to maintain; Unity is the single source of truth for game state.
- A backend crash between plan delivery and next perception does not lose world state — Unity still executed the plan; the next perception will reflect it.

**Negative / trade-offs:**
- Every task attempt costs two WebSocket round-trips: plan delivery + perception receipt. This is unavoidable given the design goal.
- The graph compiles to a DAG, but the "loop" is implemented across two separate `ainvoke()` calls bridged by session state. This is conceptually a cycle but structurally two separate graph runs.
- If Unity crashes after receiving the plan but before sending the next perception, the session's `task` is stale. The backend will route to Critic on the reconnect perception, which may judge the incomplete execution incorrectly. Mitigation: Unity sends a reset flag on reconnect.

## Alternatives Considered

### A. Simulate execution in Python, continue graph in one invocation
**Rejected.** Unity's physics cannot be faithfully simulated in Python. A simulated Critic would judge fictional outcomes. This would make the entire feedback loop meaningless.

### B. Keep the graph running with a blocking `await` until Unity sends back execution results
**Rejected.** A blocking coroutine inside the graph would hold the WebSocket handler open without any message exchange, making it indistinguishable from a hung connection. Long-held coroutines also consume FastAPI worker resources.

### C. Use a message queue to decouple plan delivery from Critic invocation
**Considered.** Unity publishes perception to a queue; the backend subscribes. This decouples transport from graph invocation but adds operational complexity (broker, consumer process). Overkill for a single Unity client.
