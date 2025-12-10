from enum import Enum
from pydantic import BaseModel, ConfigDict # Import ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- 1. ENUMS (The Shared Vocabulary) ---

class GameMode(str, Enum):
    REALITY = "reality"
    DREAM = "dream"

class AgentActionType(str, Enum):
    SAY = "say"
    MOVE = "move"
    IDLE = "idle"
    SPAWN = "spawn"

# --- 2. MEMORY SCHEMAS (Internal Brain Data) ---

class MemoryDTO(BaseModel):
    """
    Data Transfer Object. 
    Safe to pass around anywhere (Graph, API, Unity).
    """
    in_game_day: int  
    time_slot: int    
    mode: str          # "reality" or "dream"
    location_id: str
    content: str
    memory_type: str
    emotion_tags: List[str] = []
    importance: float
    created_at: datetime
    
    # Allows mapping from SQLAlchemy object to Pydantic automatically
    model_config = ConfigDict(from_attributes=True)

class CreateMemoryDTO(BaseModel):
    """
    Input schema for saving new memories.
    """
    day: int
    time: int
    mode: str
    location_id: str
    content: str
    memory_type: str
    emotion_tags: List[str] = []
    importance: float = 0.5
    
# --- 3. UNITY API SCHEMAS (The Network Contract) ---

class Perception(BaseModel):
    """
    INPUT: What Unity sends to Python every 5 seconds
    """
    time_hour: int
    day: int
    mode: GameMode
    location_id: str
    player_nearby: Optional[bool] = None
    recent_events: List[str] = []
    
    current_mood: Optional[str] = None
    
class SpawnDetails(BaseModel):
    """
    Helper for dream object spawning.
    """
    prefab_id: str
    location_x: float
    location_y: float
    
class AgentAction(BaseModel):
    """
    OUTPUT: What Python sends back to Unity
    """
    action_type: AgentActionType
    text: Optional[str] = None
    target_location: Optional[str] = None
    spawn: Optional[SpawnDetails] = None
    
    thoguht_trace: Optional[str] = None