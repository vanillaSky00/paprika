from functools import lru_cache
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.llm.base import BaseLLMClient, llm_registry


@lru_cache
def get_llm(
    provider: str | None= None,
    model: str | None= None,
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



_async_engine = create_async_engine(settings.DATABASE_URL, echo=False)

_AsyncSessionLocal = sessionmaker(
    _async_engine,
    class_=AsyncSession, 
    expire_on_commit=False
)

def get_session_factory():
    return sessionmaker(_AsyncSessionLocal)