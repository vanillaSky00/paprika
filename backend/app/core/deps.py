from functools import lru_cache

from app.core.config import settings
from app.core.db import get_session_factory
from app.llm.base import BaseLLMClient, llm_registry
from app.memory.base import BaseMemoryStore
from app.memory.pgvector_repo import PostgresMemoryStore


@lru_cache
def get_llm(
    provider: str | None = None,
    model: str | None = None,
) -> BaseLLMClient:
    """
    Factory that returns the configured LLM.
    Uses lru_cache to maintain Singleton
    """
    effective_provider = provider or settings.LLM_PROVIDER
    effective_model = model or settings.LLM_MODEL

    builder = llm_registry.get_builder(effective_provider)
    return builder.build(settings, effective_model)


def get_default_llm() -> BaseLLMClient:
    return get_llm()


@lru_cache
def get_memory_store() -> BaseMemoryStore:
    return PostgresMemoryStore(get_session_factory())


__all__ = [
    "get_default_llm",
    "get_llm",
    "get_memory_store",
]
