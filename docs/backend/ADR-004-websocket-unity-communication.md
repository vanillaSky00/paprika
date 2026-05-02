# ADR-004: WebSocket for Unity–Backend Communication

**Status:** Accepted <br>
**Date:** 2026-01-20 <br>
**Deciders:** vanillasky <br>

## Context

The Unity game client must send perception frames to the Python backend and receive action plans back. The choice of transport protocol has cascading effects on session state management, latency, and the retry/feedback loop design.

Requirements:
1. **Per-client session state** — each Unity instance (game window) tracks its own `task`, `plan`, `retry_count`, and action history independently.
2. **Low-latency round-trip** — a perception frame triggers a full LangGraph planning cycle; the result must arrive before the next game tick timeout.
3. **Bidirectional framing** — the client pushes perception; the server pushes the plan back. This is inherently bidirectional, not request–response.
4. **Long-lived feedback loop** — the Voyager-style critic loop spans multiple exchanges over a single logical task (plan → execute → perceive → critic → retry). This is not a one-shot interaction.
5. **Simplicity** — a single backend developer; avoid operational complexity.

Options evaluated:

| Protocol | Session state | Latency | Bidirectional | Long-lived |
|----------|--------------|---------|---------------|------------|
| REST (polling) | Stateless (requires external store) | High (poll interval) | No | No |
| REST + SSE | Partial (SSE is one-way push) | Medium | No | Awkward |
| WebSocket | Native per-connection | Low | Yes | Yes |
| gRPC streaming | Native per-stream | Low | Yes | Yes |

## Decision

We use **WebSocket** (`ws://host:8000/api/ws/agent/{client_id}`) as the primary Unity–backend transport.

```
Unity (C# WebSocket client)
    │
    │  JSON: Perception frame
    ▼
FastAPI WebSocket handler  (routes.py)
    │
    │  Validates Perception schema (Pydantic)
    │  Builds affordance context string
    │  Calls graph_app.ainvoke(state)   ← full LangGraph cycle
    │
    │  JSON: { task, plan: [AgentAction], client_id }
    ▼
Unity (executes plan, waits, sends next perception)
```

**Per-connection session state** is maintained as a Python dict in the WebSocket handler scope:

```python
async def agent_ws_endpoint(websocket: WebSocket, client_id: str):
    session = {"task": None, "plan": None, "retry_count": 0, "skill_guide": ""}
    async for data in websocket.iter_text():
        ...  # session persists across all frames for this connection
```

The session is scoped to the WebSocket connection lifetime. Disconnect → session gone. This is intentional: each game session starts fresh.

**`ConnectionManager`** tracks all active WebSocket connections, providing a registry for potential future broadcast scenarios (e.g., multi-agent coordination or admin monitoring).

**Message validation** uses Pydantic's `Perception` model at the boundary. Invalid JSON or schema violations return a structured error response over the same WebSocket without closing the connection.

## Consequences

**Positive:**
- Session state is trivially scoped to the connection; no Redis or external session store needed for the common case.
- A single persistent connection handles the full Voyager loop (plan → execute → critic → retry) without reconnection overhead.
- FastAPI's native `WebSocket` support integrates cleanly with `asyncio`; no additional framework needed.
- Unity's `ClientWebSocket` (System.Net.WebSockets) connects directly with no third-party plugin.

**Negative / trade-offs:**
- Session state is lost on disconnect. A crash mid-task requires Unity to reconnect and restart from the current perception frame (no resume).
- Horizontal scaling requires sticky sessions (same connection to same backend pod). Not a concern for the current single-instance deployment, but relevant if we scale.
- WebSocket connections are long-lived; the backend must handle slow or stalled Unity clients without blocking other connections.
- No built-in retry framing at the protocol level — if the plan JSON is malformed, Unity may hang. Error handling must be explicit in application code.

## Alternatives Considered

### A. REST polling (Unity polls `/plan` every N ms)
**Rejected.** Polling adds latency equal to the poll interval. Session state would require a Redis-backed store keyed by `client_id`. The planning cycle is synchronous from Unity's perspective; polling defeats this.

### B. REST with Server-Sent Events
**Rejected.** SSE is server-push only; Unity still needs a POST to send perception. Two separate HTTP connections per logical exchange is more complex than one WebSocket.

### C. gRPC bidirectional streaming
**Considered.** gRPC would give typed schemas and HTTP/2 multiplexing. Rejected because Unity's gRPC support requires the `grpc-dotnet` plugin and .proto file management. WebSocket is natively supported in Unity without third-party plugins.

### D. Message queue (e.g., Redis Pub/Sub)
**Rejected.** Adds a broker, increases operational complexity, and adds latency. Appropriate if Unity and backend are on different machines without direct connectivity; not needed here.
