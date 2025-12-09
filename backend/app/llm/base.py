from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        """
        Simple chat. 
        Used for: General reflectuins, thoughs, unformatted dialogue.
        """
        pass
    
    @abstractmethod
    async def generate_structured(self, system_prompt: str, user_message: str, response_model: Type[T]) -> T:
        """
        Structured output. Returns a Pydantic Object
        Used for: Game actions (Move, Spawn, Say... etc)
        """
        pass