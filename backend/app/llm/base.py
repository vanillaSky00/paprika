import logging
from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

from app.config import Settings

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_response(self, system_prompt: str, user_message: str) -> str:
        """
        Simple chat.
        Used for: General reflectuins, thoughs, unformatted dialogue.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self, system_prompt: str, user_message: str, response_model: Type[T]
    ) -> T:
        """
        Structured output. Returns a Pydantic Object
        Used for: Game actions (Move, Spawn, Say... etc)
        """
        pass
    

class BaseLLMBuilder(ABC):
    @abstractmethod
    def build(self, settings: Settings, model: str) -> BaseLLMClient:
        pass
    

class LLMRegistry:
    def __init__(self):
        self._builders: dict[str, type[BaseLLMBuilder]] = {}
    
    def register(self, name: str):
        """
        DECORATOR: @llm_registry.register("openai")
        """
        def decorator(cls: type[BaseLLMBuilder]):
            if name in self._builders:
                logger.warning(
                    f"Name collision detected for '{name}'. Overwrite the llm registry"
                )
            self._builders[name] = cls
        
        return decorator
    
    def get_builder(self, name: str) -> BaseLLMBuilder:
        builder_cls = self._builders.get(name)
        if not builder_cls:
            raise ValueError(f"Unknown LLM provider: {name}")
        return builder_cls()
    

llm_registry = LLMRegistry()