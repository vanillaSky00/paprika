from typing import TypedDict, List, Optional
from app.api.schemas import Perception, AgentAction, MemoryDTO

class AgentState(TypedDict):
    """
    Input from unity -> fetch memory with postgres -> make decision
    """
    perception: Perception
    
    memories: List[MemoryDTO]
    
    final_action: Optional[AgentAction]