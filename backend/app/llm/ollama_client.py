from .base import BaseLLMClient
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class OllamaClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = ""):
        pass
        
    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        pass
    
    async def generate_structured(self, system_prompt: str, user_message: str, response_model: Type[T]) -> T:
        pass