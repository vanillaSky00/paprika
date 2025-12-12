import pytest
from pydantic import BaseModel, Field

from app.config import settings
from app.deps import get_llm


@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OLLAMA_API_KEY,
    reason="OLLAMA_API_KEY not set; skipping live OpenAI test.",
)
async def test_ollama_simple_text():
    """
    test1: ensure basic connection
    use langchain to get in server
    """
    try:
        client = get_llm("ollama", settings.OLLAMA_MODEL)
        print(f"\n[Info] Connecting to: {settings.OLLAMA_BASE_URL}")
        print(f"[Info] Model: {settings.LLM_MODEL}")

        result = await client.generate_response(
            system_prompt="You are a helpful bot.",
            user_message="Say 'Hello NCKU' and nothing else.",
        )

        print(f"\n[Result] Model said: {result}")
        assert len(result) > 0

    except Exception as e:
        pytest.fail(f"Simple connection failed: {e}")
