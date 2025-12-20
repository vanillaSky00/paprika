from functools import lru_cache
from typing import List

from langchain_openai import OpenAIEmbeddings
from app.config import settings

@lru_cache
def get_embedder() -> OpenAIEmbeddings:
    """
    Lazy create the embedder on first real use
    This will only hit OpenAI / check API key when actually called.
    """
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.OPENAI_API_KEY
    )


def embed_text(text: str) -> List[float]:
    """
    Thin wrapper used by the repo layer.
    Tests will patch this function, so they never need a real embedder.
    """
    embedder = get_embedder()
    return embedder.embed_query(text)
