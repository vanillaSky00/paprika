from langchain_openai import OpenAIEmbeddings
# OR use sentence-transformers for local dev

# Setup standard OpenAI Embeddings
# Ensure OPENAI_API_KEY is in your environment variables
_embedder = OpenAIEmbeddings(model="text-embedding-3-small")

def embed_text(text: str) -> list[float]:
    return _embedder.embed_query(text)