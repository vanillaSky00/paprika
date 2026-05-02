# ADR-009: Decorator-Based Tool Registry with Late Binding

**Status:** Accepted <br>
**Date:** 2026-02-05 <br>
**Deciders:** vanillasky <br>

## Context

The agent system needs a set of **tools** — actions the LLM can "call" — documented in system prompts so the LLM knows what functions are available, what arguments they take, and what they return. The tool surface must be:

1. **Discoverable**: A new tool should self-register without modifying a central list.
2. **Conditionally available**: Some tools (e.g., weather lookup) require external API keys. If the key is absent, the tool should be silently skipped, not crash the server.
3. **Context-aware**: Some tools need runtime config (API keys, LLM clients) at build time, not at import time.
4. **Documented**: Tool names, descriptions, and arg schemas must be injectable into LLM system prompts.

Python's `langchain.tools.StructuredTool` provides the docstring → schema path, but doesn't solve registration or conditional availability.

## Decision

We implement a **decorator-based registry with late binding via a `build()` protocol**.

### Registry

```python
class ToolRegistry:
    _builders: dict[str, type[BaseToolBuilder]] = {}

    def register(self, cls: type[BaseToolBuilder]) -> type[BaseToolBuilder]:
        self._builders[cls.__name__] = cls
        return cls   # returns class unchanged so decorator is transparent

    def build_all(self, context: ToolContext) -> list[StructuredTool]:
        tools = []
        for name, builder_cls in self._builders.items():
            tool = builder_cls().build(context)
            if tool is not None:         # None = skip this tool
                tools.append(tool)
        return tools

tool_registry = ToolRegistry()
```

### Builder Protocol

```python
class BaseToolBuilder(ABC):
    @abstractmethod
    def build(self, context: ToolContext) -> StructuredTool | None: ...
```

Each tool is a class decorated with `@tool_registry.register`:

```python
@tool_registry.register
class MoveToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        def move_to(id: str) -> dict:
            return {"status": "pending", "target": id}
        return StructuredTool.from_function(
            func=move_to,
            name="move_to",
            description="Move the agent to the object with the given canonical ID.",
            args_schema=MoveArgs,
        )

@tool_registry.register
class WeatherToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool | None:
        if not context.settings.OPENWEATHER_API_KEY:
            return None    # silently skip; tool absent from prompt
        ...
```

### Registration Timing

Builder classes register themselves at **import time** (module-level decorator execution). The `build()` call happens once at application startup in `lifespan()`:

```python
context = ToolContext(settings=get_settings(), llm=get_llm())
tools = tool_registry.build_all(context)
```

The resulting `tools` list is passed to each `BaseAgent` constructor and rendered into the `{tools_doc}` placeholder in every system prompt.

### Unified Argument Convention

All action tools use a single `id` parameter (not `target_id`, `location`, `object_name`):

```python
class MoveArgs(BaseModel):
    id: str = Field(..., description="Canonical object ID from the [LAYOUT] block")

class PickupArgs(BaseModel):
    id: str = Field(..., description="Canonical object ID to pick up")
```

This reduces LLM confusion — the model always uses `{"id": "..."}` regardless of which tool it is calling.

### Internal vs External Tools

| Category | Examples | Execution |
|----------|---------|-----------|
| **Internal** | `move_to`, `pickup`, `put_down`, `cook`, `chop` | Stub returns `{"status": "pending"}`; real execution is in Unity |
| **External** | `get_current_weather` | Real async HTTP call to OpenWeather API |

Internal tools exist so the LLM sees the tool surface in the prompt and generates correct `function` + `args` JSON. Unity reads the plan and executes the actual physics. The Python stub is never invoked in production; it is called in tests to verify the tool's schema and registration.

## Consequences

**Positive:**
- Adding a new tool is fully additive: create a new file, decorate the builder, import it. No existing file needs modification.
- Conditional `None` return cleanly handles missing API keys without try/except at call sites.
- `ToolContext` passed to `build()` gives each builder access to config and clients without global state.
- `StructuredTool.from_function()` derives the JSON schema from the Pydantic `args_schema` automatically.

**Negative / trade-offs:**
- Registration is side-effectful at import time. If a builder module is not imported, its tool is silently absent from the registry — no startup warning.
- Internal tool stubs are dead code in production (Unity executes). They must be kept in sync with Unity's action API or the LLM will generate wrong function names.
- The `build_all()` call happens at startup, not lazily per request. Adding a tool requires restarting the server.

## Alternatives Considered

### A. Hard-coded tool list in `deps.py`
**Rejected.** Adding a tool requires modifying the central file. The decorator pattern is open for extension without modification.

### B. Use LangChain's `@tool` decorator directly on functions
**Considered.** `@tool` is simpler for basic cases. Rejected because: (a) no conditional availability without wrapping, (b) no `ToolContext` injection, (c) registration is still manual in a list somewhere.

### C. Dynamic tool loading from a YAML config file
**Considered.** Allows non-code tool definitions. Rejected because: (a) external tools need real Python code for async HTTP calls, (b) internal stubs need exact Pydantic schemas, (c) YAML config adds a second source of truth to maintain.
