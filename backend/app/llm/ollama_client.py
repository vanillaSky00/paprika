
from .base import BaseLLMClient

class OllamaClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        pass
        
    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        pass
    
    async def generate_structured(self, system_prompt: str, user_message: str, response_model: Type[T]) -> T:
        pass
         