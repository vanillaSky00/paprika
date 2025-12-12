from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.llm.openai_client import OpenAIClient


class FakeAction(BaseModel):
    action: str
    reason: str


@pytest.mark.asyncio
async def test_openai_client_structure():
    # Patch the ChatOpenAI class used *inside* OpenAIClient
    with patch("app.llm.openai_client.ChatOpenAI") as MockChat:
        # ChatOpenAI(...) should return a *sync* object
        mock_internal_llm = MagicMock()
        MockChat.return_value = mock_internal_llm

        # with_structured_output(...) should return an object
        # with an async ainvoke(...) method
        mock_structured = AsyncMock()
        mock_internal_llm.with_structured_output.return_value = mock_structured

        # When ainvoke is awaited, return a FakeAction instance
        expected_output = FakeAction(action="jump", reason="testing")
        mock_structured.ainvoke.return_value = expected_output

        # Use our client
        client = OpenAIClient(api_key="fake-key")
        result = await client.generate_structured(
            system_prompt="Act like a game",
            user_message="Jump!",
            response_model=FakeAction,
        )

        # Assert behavior + wiring
        assert result.action == "jump"
        assert result.reason == "testing"

        mock_internal_llm.with_structured_output.assert_called_once_with(FakeAction)
        mock_structured.ainvoke.assert_awaited_once()
