from typing import Type, TypeVar
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import Settings
from app.llm.base import BaseLLMClient, BaseLLMBuilder, llm_registry

# “T is a generic type that must be a subclass of BaseModel.”
T = TypeVar("T", bound=BaseModel)


class GenericOpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url, 
            model=model,
            temperature=0.7
        )

    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        message = [("system", system_prompt), ("human", user_message)]
        response = await self.llm.ainvoke(message)
        return response.content

    async def generate_structured(
        self, system_prompt: str, user_message: str, response_model: Type[T]
    ) -> T:
        structured_llm = self.llm.with_structured_output(response_model)

        message = [("system", system_prompt), ("human", user_message)]
        return await structured_llm.ainvoke(message)

@llm_registry.register("General") 
class GenericOpenAIBuilder(BaseLLMBuilder):
    def build(self, settings: Settings, model: str):
        if not settings.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY missing in .env!")
        if not settings.LLM_MODEL:
            raise RuntimeError("LLM_MODEL missing in .env!")
        if not settings.LLM_BASE_URL:
            raise RuntimeError("LLM_BASE_URL missing in .env!")
        
        return GenericOpenAIClient(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL
        )