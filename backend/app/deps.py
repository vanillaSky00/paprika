from functools import lru_cache
from .config import settings
from .llm.base import BaseLLMClient
from .llm.openai_client import OpenAIClient
from .llm.ollama_client import OllamaClient # for future switch

@lru_cache
def get_llem_client() -> BaseLLMClient:
    """
    Factory that returns the configured LLM.
    Uses lru_cache to maintain Singleton
    """
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing in .env!")
        return OpenAIClient(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY
            )
        
    if settings.LLM_PROVIDER == "ollama":
            return OllamaClient(
                model=settings.LLM_MODEL,
                base_url=settings.OLLAMA_BASE_URL
            )
    
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")