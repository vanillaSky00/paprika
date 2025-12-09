from langchain_openai import ChatOpenAI
from typing import Type, TypeVar
from pydantic import BaseModel
from .base import BaseLLMClient

# “T is a generic type that must be a subclass of BaseModel.”
T = TypeVar("T", bound=BaseModel)

class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(api_key=api_key, model=model, temperature=0.7)
        
    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        message = [
            ("system", system_prompt),
            ("human", user_message)
        ]
        response = await self.llm.ainvoke(message)
        return response.content
    
    async def generate_structured(self, system_prompt: str, user_message: str, response_model: Type[T]) -> T:
        structured_llm = self.llm.with_structured_output(response_model)
        
        message = [
            ("system", system_prompt),
            ("human", user_message)
        ]
        return await structured_llm.ainvoke(message)
        