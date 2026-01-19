from functools import lru_cache
from typing import List
from langchain_core.embeddings import Embeddings

from app.config import settings
from app.memory.embedding.strategy import get_embedding_strategy

@lru_cache
def embed_dim() -> int:
    return get_embedding_strategy().get_dimension()


@lru_cache
def get_embedder() -> Embeddings :
    """
    Lazy create the embedder on first real use
    This will only hit OpenAI / check API key when actually called.
    """
    return get_embedding_strategy().get_embeddings()


def embed_text(text: str) -> List[float]:
    """
    Thin wrapper used by the repo layer.
    Tests will patch this function, so they never need a real embedder.
    """
    embedder = get_embedder()
    return embedder.embed_query(text)
