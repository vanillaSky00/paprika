from abc import ABC, abstractmethod
from typing import List
import logging

logger = logging.getLogger(__name__)

class EmbeddingStrategy(ABC):
    def __init__(self, dim: int):
        self.dim = dim

    def get_dimension(self) -> int:
        return self.dim

    @abstractmethod
    def get_embeddings(self) -> List[float]:
        pass
