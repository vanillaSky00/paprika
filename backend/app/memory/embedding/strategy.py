from typing import List
from app.config import settings
from app.memory.embedding.base import EmbeddingStrategy
import logging

class OpenAIEmbeddingStrategy(EmbeddingStrategy):
    def __init__(self, dim: int):
        super().__init__(dim)
    
    def get_embeddings(self) -> List[float]:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            check_embedding_ctx_length=False
        )      

class HuggingFaceEmbeddingStrategy(EmbeddingStrategy):
    def __init__(self, dim: int):
        super().__init__(dim)
    
    def get_embeddings(self) -> List[float]:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            raise ImportError("langchain_huggingface not installed. Please install it to use HuggingFaceEmbeddingStrategy.")

        return HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'} 
        )

def get_embedding_strategy() -> EmbeddingStrategy:
    if not settings.EMBEDDING_PROVIDER:
        raise ValueError("EMBEDDING_PROVIDER missing in .env!")
    if not settings.EMBEDDING_DIMENSION:
        raise ValueError("EMBEDDING_DIMENSION missing in .env!")
    
    provider = settings.EMBEDDING_PROVIDER
    
    strategies = {
        # append here if needed
        "openai": OpenAIEmbeddingStrategy,
        "huggingface": HuggingFaceEmbeddingStrategy,
    }
    
    if provider not in strategies:
        raise ValueError(f"Embedding Provider: {provider} is not supported, try editting EMBEDDING_PROVIDER in .env file")
    
    return strategies[provider](dim=settings.EMBEDDING_DIMENSION)
