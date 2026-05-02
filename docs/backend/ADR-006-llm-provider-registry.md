# ADR-006: LLM Provider Registry with Decorator-Based Late Binding

**Status:** Accepted <br>
**Date:** 2026-01-25 <br>
**Deciders:** vanillasky <br>

## Context

The project needs to support at least two LLM backends:
- **OpenAI** (cloud, GPT-4.1-mini) — default for quality and API reliability.
- **Ollama** (local, Gemma 3 4B or similar) — for development without API costs or for air-gapped environments.

The selection should be driven by a single environment variable (`LLM_PROVIDER`) without requiring code changes. Adding a third provider (e.g., Anthropic, a local vLLM endpoint) should not require touching agent code.

Additionally, a given `(provider, model)` pair should produce a singleton LLM client — instantiating a new HTTP session per planning cycle would be wasteful.

## Decision

We adopt a **registry + singleton pattern** consisting of three layers:

### Layer 1: Abstract Interface (`BaseLLMClient`)

```python
class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_response(self, system_prompt: str, user_message: str) -> str: ...

    @abstractmethod
    async def generate_structured(self, system_prompt: str, user_message: str, response_model: type[T]) -> T: ...
```

All agent code calls only these two methods — no provider-specific API leaks into agent logic.

### Layer 2: Decorator-Based Registry

```python
llm_registry = LLMRegistry()

@llm_registry.register("openai")
class OpenAIBuilder(BaseLLMBuilder):
    def build(self, settings: Settings, model: str) -> BaseLLMClient:
        return OpenAIClient(api_key=settings.OPENAI_API_KEY, model=model)

@llm_registry.register("ollama")
class OllamaBuilder(BaseLLMBuilder):
    def build(self, settings: Settings, model: str) -> BaseLLMClient:
        return OllamaClient(base_url=settings.OLLAMA_BASE_URL, model=model)
```

Builders are registered at **import time** (module-level decorator), not at startup. This means the registry is populated before `lifespan()` runs.

### Layer 3: Singleton via `@lru_cache`

```python
@lru_cache(maxsize=8)
def get_llm(provider: str = None, model: str = None) -> BaseLLMClient:
    settings = get_settings()
    provider = provider or settings.LLM_PROVIDER
    model = model or settings.LLM_MODEL
    return llm_registry.build(provider, model, settings)
```

The cache key is `(provider, model)`. The first call for a given pair instantiates the client; subsequent calls return the cached instance. This means one HTTP session per provider+model combination for the process lifetime.

### Adding a New Provider

1. Create `app/llm/anthropic_client.py` implementing `BaseLLMClient`.
2. Add `@llm_registry.register("anthropic")` decorator on a new builder class.
3. Import the module anywhere before `get_llm()` is first called (e.g., in `deps.py`).
4. Set `LLM_PROVIDER=anthropic` in `.env`.

No other file changes required.

## Consequences

**Positive:**
- Agent code is entirely provider-agnostic; swapping providers is a one-line env change.
- `@lru_cache` prevents repeated client instantiation across planning cycles.
- Builder `build()` can raise early with a clear error if required config (API key, base URL) is missing.
- Adding a provider is additive — no existing files need modification.

**Negative / trade-offs:**
- `@lru_cache` with mutable settings objects can cache stale config if settings change at runtime (unlikely but possible in test setups — tests must clear the cache explicitly with `get_llm.cache_clear()`).
- Decorator-based registration requires the provider module to be imported before the registry is queried. A missing import silently results in `KeyError` at runtime, not at startup.
- Two methods (`generate_response` / `generate_structured`) have diverging usage — agents use `generate_response` and parse JSON manually. The `generate_structured` path is under-used, creating interface debt.

## Alternatives Considered

### A. Direct `if/elif` on `LLM_PROVIDER` in `deps.py`
**Rejected.** Adding a new provider requires modifying `deps.py`. The registry pattern is open for extension without modification.

### B. Factory function per provider, no registry
**Rejected.** Achieves the same result as option A — no central extension point. Code ends up scattered across multiple `if` blocks.

### C. Use LangChain's model abstraction (`BaseChatModel`)
**Considered.** LangChain provides its own provider abstraction. Rejected because it couples agent code to LangChain's invocation API (`chain.invoke()`, `ChatMessage` types) rather than plain `str` I/O. The thin `BaseLLMClient` interface keeps agents independent of the LangChain version.
