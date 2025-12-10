from typing import Type, TypeVar
from pydantic import BaseModel
# from langchain_community.chat_models import ChatOllama
from langchain_ollama import ChatOllama
from .base import BaseLLMClient

T = TypeVar("T", bound=BaseModel)

class OllamaClient(BaseLLMClient):
    def __init__(self, base_url: str, model: str = "gemma3:4b", api_key: str = None):

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            #print(f"[DEBUG] Final Headers: {headers}")

        self.llm = ChatOllama(
            base_url=base_url,
            model=model,
            #temperature=0.7,
            client_kwargs={
                "headers": headers
            }
        )

    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        messages = [
            ("system", system_prompt),
            ("human", user_message)
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def generate_structured(self, system_prompt: str, user_message: str, response_model: Type[T]) -> T:

        structured_llm = self.llm.with_structured_output(response_model)
        
        messages = [
            ("system", system_prompt),
            ("human", user_message)
        ]
        return await structured_llm.ainvoke(messages)