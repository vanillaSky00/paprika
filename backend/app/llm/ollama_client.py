from typing import Type, TypeVar
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from app.config import Settings
from app.llm.base import BaseLLMClient, BaseLLMBuilder, llm_registry

T = TypeVar("T", bound=BaseModel)


class OllamaClient(BaseLLMClient):
    def __init__(self, base_url: str, model: str = "gemma3:4b", api_key: str = None):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.llm = ChatOllama(
            base_url=base_url,
            model=model,
            temperature=0.5,
            client_kwargs={"headers": headers} if headers else None,
        )

    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        messages = [("system", system_prompt), ("human", user_message)]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def generate_structured(
        self, system_prompt: str, user_message: str, response_model: Type[T]
    ) -> T:
        structured_llm = self.llm.with_structured_output(response_model)

        messages = [("system", system_prompt), ("human", user_message)]
        return await structured_llm.ainvoke(messages)

@llm_registry.register("ollama")    
class OllamaBuilder(BaseLLMBuilder):
    def build(self, settings: Settings, model: str):
        if not settings.OLLAMA_BASE_URL:
            raise RuntimeError("OLLAMA_BASE_URL missing in .env!")
        
        return OllamaClient(
            base_url=settings.OLLAMA_BASE_URL,
            model=model,
            api_key=settings.OLLAMA_API_KEY
        )
