from typing import Optional
from functools import lru_cache
from .config import settings
from .llm.base import BaseLLMClient
from .llm.openai_client import OpenAIClient
from .llm.ollama_client import OllamaClient 

def _build_llm(provider: str, model: str) -> BaseLLMClient:
      
    if provider == "ollama":
        print(f"DEBUG: Config API Key is: {settings.OLLAMA_API_KEY}")
        return OllamaClient(
            model=model,
            base_url=settings.OLLAMA_BASE_URL,
            api_key=settings.OLLAMA_API_KEY
        )
    
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing in .env!")
        return OpenAIClient(
            model=model,
            api_key=settings.OPENAI_API_KEY
        )
    raise ValueError(f"Unknown provider: {provider}")

@lru_cache
def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseLLMClient:
    """
    Factory that returns the configured LLM.
    Uses lru_cache to maintain Singleton
    """
    effective_provider = provider or settings.LLM_PROVIDER
    effective_model    = model or settings.LLM_MODEL
    return _build_llm(effective_provider, effective_model)
    
def get_default_llm() -> BaseLLMClient:
    return get_llm()
