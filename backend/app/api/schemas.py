# Define how Unity talks to Python


# paprika_agent_backend/api/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class MemoryDTO(BaseModel):
    """
    Data Transfer Object. 
    Safe to pass around anywhere (Graph, API, Unity).
    """
    id: int
    day: int
    time: int
    mode: str          # "reality" or "dream"
    location: str
    content: str
    memory_type: str
    emotion_tags: List[str] = []
    importance: float
    created_at: datetime
    
    # Allows mapping from SQLAlchemy object to Pydantic automatically
    class Config:
        from_attributes = True 

class CreateMemoryDTO(BaseModel):
    """
    Input schema for saving new memories.
    """
    day: int
    time: int
    mode: str
    location: str
    content: str
    memory_type: str
    emotion_tags: List[str] = []
    importance: float = 0.5